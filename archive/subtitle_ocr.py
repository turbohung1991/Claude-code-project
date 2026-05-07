import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from difflib import SequenceMatcher


def _extract_frames(video_path: str, output_dir: str, fps: int = 2) -> list[str]:
    """Extract frames from the bottom subtitle region of a video.

    Crops the bottom 35% of the frame where Douyin hardcoded subtitles typically appear.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_pattern = os.path.join(output_dir, "frame_%04d.png")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"crop=iw:ih*0.35:0:ih*0.65, fps={fps}",
        "-q:v", "2",
        out_pattern,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    frames = sorted(Path(output_dir).glob("frame_*.png"))
    if not frames:
        raise RuntimeError("No frames extracted from video")
    return [str(f) for f in frames]


def _ocr_frames(frame_paths: list[str]) -> list[tuple[int, str, float]]:
    """Run PaddleOCR on frames, return (frame_index, text, confidence)."""
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(lang="ch", text_det_thresh=0.3, text_rec_score_thresh=0.5)
    results = []

    for idx, path in enumerate(frame_paths):
        try:
            ocr_result = ocr.predict(path)
        except Exception as e:
            print(f"[OCR] frame {idx} predict error: {e}", flush=True)
            continue

        if not ocr_result:
            continue

        try:
            # PaddleOCR 3.x returns list of OCRResult (dict-like) objects
            res = ocr_result[0]
            texts = res["rec_texts"] if "rec_texts" in res else []
            scores = res["rec_scores"] if "rec_scores" in res else []
        except (IndexError, KeyError, TypeError) as e:
            print(f"[OCR] frame {idx} result parse error: {e}, result={ocr_result!r:.200}", flush=True)
            continue

        lines = []
        conf_sum = 0.0
        count = 0
        for text, conf in zip(texts, scores):
            if conf > 0.5:
                lines.append(text)
                conf_sum += conf
                count += 1

        if lines:
            combined = " ".join(lines)
            avg_conf = conf_sum / count if count else 0.0
            results.append((idx, combined, avg_conf))

    return results


def _deduplicate(results: list[tuple[int, str, float]], threshold: float = 0.8) -> list[str]:
    """Remove near-duplicate consecutive OCR results."""
    if not results:
        return []

    merged = [results[0]]
    for r in results[1:]:
        prev_text = merged[-1][1]
        curr_text = r[1]
        similarity = SequenceMatcher(None, prev_text, curr_text).ratio()
        if similarity < threshold:
            merged.append(r)

    return [text for _, text, _ in merged]


def extract_subtitles(
    video_path: str, fps: int = 2, dedup_threshold: float = 0.8
) -> str:
    """Extract hardcoded subtitles from a video using OCR.

    Returns the full subtitle text as a single string.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        frames = _extract_frames(video_path, str(tmp_dir), fps=fps)
        ocr_results = _ocr_frames(frames)
        subtitle_lines = _deduplicate(ocr_results, threshold=dedup_threshold)
        return "\n".join(subtitle_lines)
    finally:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)


def extract_subtitles_with_timestamps(
    video_path: str, fps: int = 2, dedup_threshold: float = 0.8
) -> tuple[str, str]:
    """Extract subtitles and also produce a basic SRT file.

    Returns (plain_text, srt_content).
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        frames = _extract_frames(video_path, str(tmp_dir), fps=fps)
        ocr_results = _ocr_frames(frames)

        plain_lines = _deduplicate(ocr_results, threshold=dedup_threshold)

        # Build SRT
        srt_parts = []
        seq = 0
        for idx, text, _ in ocr_results:
            # Check if this text is in the deduplicated set
            is_unique = any(
                SequenceMatcher(None, text, line).ratio() >= dedup_threshold
                for line in plain_lines
            )
            if not is_unique and len(ocr_results) > 1:
                continue

            start_sec = idx / fps
            end_sec = (idx + 1) / fps

            start_ts = f"{int(start_sec//3600):02d}:{int((start_sec%3600)//60):02d}:{int(start_sec%60):02d},{int((start_sec%1)*1000):03d}"
            end_ts = f"{int(end_sec//3600):02d}:{int((end_sec%3600)//60):02d}:{int(end_sec%60):02d},{int((end_sec%1)*1000):03d}"

            seq += 1
            srt_parts.append(f"{seq}\n{start_ts} --> {end_ts}\n{text}\n")

        return "\n".join(plain_lines), "\n".join(srt_parts)
    finally:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
