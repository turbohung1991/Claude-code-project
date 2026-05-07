"""Extract subtitles from video using speech-to-text (faster-whisper).

Optimized for Apple Silicon. Speed/quality presets for different use cases.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Speed presets: (model_size, beam_size, cpu_threads)
PRESETS = {
    "fast":    ("tiny",  1, 6),   # ~30s  per min of audio
    "default": ("small", 3, 6),   # ~60s  per min of audio
    "best":    ("small", 5, 6),   # ~90s  per min of audio
}


def _extract_audio(video_path: str, output_dir: str) -> str:
    out_path = os.path.join(output_dir, "audio.wav")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def extract_subtitles(video_path: str, preset: str = "default", **kwargs) -> str:
    """Transcribe video audio to text using faster-whisper.

    Args:
        video_path: Path to the video file.
        preset: 'fast' (tiny, greedy), 'default' (small, beam=3), 'best' (small, beam=5).

    Returns:
        Transcribed text in Simplified Chinese.
    """
    from faster_whisper import WhisperModel
    import zhconv

    model_size, beam_size, cpu_threads = PRESETS.get(preset, PRESETS["default"])

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        audio_path = _extract_audio(video_path, str(tmp_dir))

        model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
            num_workers=2,
        )
        segments, _ = model.transcribe(
            audio_path,
            language="zh",
            beam_size=beam_size,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=400,
            ),
        )

        lines = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                lines.append(zhconv.convert(text, "zh-cn"))

        return "\n".join(lines)
    finally:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
