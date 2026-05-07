"""Standalone test for douyin download + OCR pipeline."""
import sys
import traceback
import os

# Use the already-downloaded video to skip the slow download step
existing = None
for root, dirs, files in os.walk("/var/folders"):
    for f in files:
        if f.startswith("douyin_") and f.endswith(".mp4"):
            existing = os.path.join(root, f)
            break
    if existing:
        break

if not existing:
    print("No cached video found. Downloading...")
    from converters.douyin_download import download_video
    try:
        info = download_video("https://www.douyin.com/video/7635209075587845427")
        video_path = info["file_path"]
        print(f"Downloaded: {video_path}")
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
else:
    video_path = existing
    print(f"Using cached video: {video_path}")

print(f"File size: {os.path.getsize(video_path):,} bytes")
print()

# Step 2: OCR
print("Running OCR...")
try:
    from converters.subtitle_ocr import extract_subtitles
    text = extract_subtitles(video_path, fps=1)
    print(f"OK! {len(text.splitlines())} subtitle lines")
    print("---SUBTITLES---")
    print(text[:2000])
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
