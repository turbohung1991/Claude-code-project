"""Douyin video downloader.

Uses the Douyin_TikTok_Download_API service as the primary method.
Falls back to Playwright browser automation.
"""

import re
import os
import json
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

# API service URL (runs alongside Gradio)
DOUYIN_API_BASE = "http://127.0.0.1:80/api"

SHORT_LINK_RE = re.compile(r"https?://v\.douyin\.com/[\w\-_]+/?")
VIDEO_ID_RE = re.compile(r"douyin\.com/(?:video|note)/(\d+)")
URL_EXTRACT_RE = re.compile(
    r"https?://(?:v\.douyin\.com/[\w\-_]+/?|(?:www\.)?douyin\.com/(?:video|note)/\d+)"
)


def _extract_url(text: str) -> str:
    m = URL_EXTRACT_RE.search(text)
    return m.group(0) if m else text.strip()


def _extract_aweme_id(url: str) -> str:
    """Extract aweme_id from a Douyin URL. Follows short links if needed."""
    # If it's a full video URL, extract directly
    m = VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)

    # Short link - follow redirect to get video ID
    req = Request(url, headers={"User-Agent": USER_AGENT})
    resp = urlopen(req, timeout=15)
    final = resp.geturl()
    m = VIDEO_ID_RE.search(final)
    if m:
        return m.group(1)

    raise ValueError(f"无法提取视频 ID: {final}")


def _download_via_api(aweme_id: str):
    """Strategy A: Use Douyin_TikTok_Download_API service (handles a_bogus signing)."""
    api_url = f"{DOUYIN_API_BASE}/douyin/web/fetch_one_video?aweme_id={aweme_id}"

    try:
        req = Request(api_url, headers={"User-Agent": USER_AGENT})
        resp = urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
    except Exception:
        return None

    if data.get("code") != 200:
        return None

    aweme = data.get("data", {}).get("aweme_detail", {})
    if not aweme:
        return None

    # Find the best video download URL (no watermark preferred)
    video_url = ""
    for key in ("download_addr", "play_addr", "play_addr_h264"):
        addr = aweme.get("video", {}).get(key, {})
        url_list = addr.get("url_list", []) if isinstance(addr, dict) else []
        if url_list:
            video_url = url_list[0]
            break

    if not video_url:
        # Try alternative fields
        video_url = (
            aweme.get("video", {}).get("play_addr_265", {}).get("url_list", [""])[0]
            or aweme.get("video", {}).get("download_addr", {}).get("url_list", [""])[0]
        )

    if not video_url:
        return None

    # Download the video
    output_dir = Path(tempfile.mkdtemp())
    output_path = output_dir / f"douyin_{aweme_id}.mp4"

    dl_req = Request(video_url, headers={"User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/"})
    with urlopen(dl_req, timeout=120) as f:
        output_path.write_bytes(f.read())

    size = output_path.stat().st_size
    if size < 10000:
        output_path.unlink()
        return None

    title = aweme.get("desc") or ""
    if not title:
        title = aweme.get("share_info", {}).get("share_title") or ""
    duration = int(aweme.get("duration", 0)) // 1000

    return {
        "video_id": aweme_id,
        "title": title,
        "description": aweme.get("desc", ""),
        "duration": duration,
        "file_path": str(output_path),
        "output_dir": str(output_dir),
    }


def _download_via_playwright(page_url: str):
    """Strategy B: Playwright browser automation fallback."""
    import shutil

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    aweme_id = _extract_aweme_id(page_url)
    output_dir = Path(tempfile.mkdtemp())
    output_path = output_dir / f"douyin_{aweme_id}.mp4"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent=MOBILE_UA,
                viewport={"width": 390, "height": 844},
            )
            page = context.new_page()
            page.goto(page_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            video_src = page.evaluate("""() => {
                const v = document.querySelector('video');
                if (!v) return '';
                const src = v.src || v.getAttribute('src') || '';
                const sources = v.querySelectorAll('source');
                if (!src && sources.length > 0) {
                    const s = sources[0].getAttribute('src');
                    return s || '';
                }
                return src;
            }""")

            if not video_src:
                browser.close()
                return None

            # Follow playwm redirect
            page.goto(video_src, wait_until="load", timeout=15000)
            cdn_url = page.url

            if cdn_url == video_src:
                browser.close()
                return None

            dl_resp = context.request.get(cdn_url)
            if dl_resp.status in (200, 206):
                output_path.write_bytes(dl_resp.body())

            browser.close()
    except Exception:
        return None

    if output_path.stat().st_size < 10000:
        output_path.unlink()
        return None

    return {
        "video_id": aweme_id,
        "title": "",
        "description": "",
        "duration": 0,
        "file_path": str(output_path),
        "output_dir": str(output_dir),
    }


def download_video(url: str, cookie_file: str = None) -> dict:
    """Download a Douyin video. Returns dict with video_id, title, file_path, etc."""
    url = _extract_url(url)

    # For short links, resolve to full URL first
    if SHORT_LINK_RE.search(url):
        req = Request(url, headers={"User-Agent": USER_AGENT})
        full_url = urlopen(req, timeout=15).geturl()
    else:
        full_url = url

    aweme_id = _extract_aweme_id(full_url)
    errors = []

    # Strategy 1: API service (fast, handles a_bogus signing natively)
    try:
        result = _download_via_api(aweme_id)
        if result and result.get("file_path"):
            return result
    except Exception as e:
        errors.append(f"API: {e}")

    # Strategy 2: Playwright (slower, but works as fallback)
    try:
        result = _download_via_playwright(full_url)
        if result and result.get("file_path"):
            return result
    except Exception as e:
        errors.append(f"Playwright: {e}")

    raise RuntimeError(
        "下载失败。\n"
        + "\n".join(errors)
        + "\n\n提示：确保 Douyin API 服务已启动 (端口 8000)"
    )
