"""Douyin video downloader — Playwright browser automation.

Uses a real browser to bypass anti-bot protections (a_bogus signing).
The browser handles all encryption; we intercept the API response.
"""

import json
import os
import re
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

VIDEO_ID_RE = re.compile(r"douyin\.com/(?:video|note)/(\d+)")
SHORT_LINK_RE = re.compile(r"https?://v\.douyin\.com/[\w\-_]+/?")
URL_EXTRACT_RE = re.compile(
    r"https?://(?:v\.douyin\.com/[\w\-_]+/?|(?:www\.)?douyin\.com/(?:video|note)/\d+)"
)
RAW_ID_RE = re.compile(r"^(\d{15,20})$")

# Link type regexen
ALL_ID_PATTERNS = [
    re.compile(r"douyin\.com/video/(\d+)"),
    re.compile(r"douyin\.com/note/(\d+)"),
    re.compile(r"iesdouyin\.com/share/video/(\d+)"),
    re.compile(r"douyin\.com/share/video/(\d+)"),
    re.compile(r"douyin\.com/user/.*?video/(\d+)"),
    re.compile(r"douyin\.com/user/\S*\?.*modal_id=(\d+)"),
]

RENDER_DATA_RE = re.compile(
    r'<script\s+id="RENDER_DATA"\s+type="application/json">(.*?)</script>',
    re.DOTALL,
)


def _extract_url(text: str) -> str:
    m = URL_EXTRACT_RE.search(text)
    return m.group(0) if m else text.strip()


def _extract_video_id(url: str) -> str:
    """Sync video ID extraction from all known URL formats."""
    if RAW_ID_RE.match(url):
        return url

    for pattern in ALL_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)

    m = VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)

    raise ValueError(f"无法提取视频 ID: {url}")


def _resolve_short_link(url: str) -> str:
    """Follow short link redirect."""
    req = Request(url, headers={"User-Agent": DESKTOP_UA})
    resp = urlopen(req, timeout=15)
    return resp.geturl()


def _get_video_info_playwright(video_id: str) -> dict:
    """Fetch video metadata using Playwright browser automation."""
    from playwright.sync_api import sync_playwright
    import time

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            user_agent=DESKTOP_UA,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
        )
        page = context.new_page()

        video_data = {}

        def on_response(resp):
            url = resp.url
            if "aweme/v1/web/aweme/detail" in url or (
                "aweme/v2" in url and "detail" in url
            ):
                try:
                    body = resp.json()
                    detail = body.get("aweme_detail", {})
                    if detail.get("aweme_id"):
                        video_data["detail"] = detail
                        print(f"[douyin] API intercepted: aweme_id={detail.get('aweme_id')}")
                except Exception:
                    pass

        page.on("response", on_response)

        # Go directly to video page (skip homepage — saves time)
        try:
            page.goto(
                f"https://www.douyin.com/video/{video_id}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            print(f"[douyin] Page load warning: {e}")

        # Poll for API data up to 15 seconds
        deadline = time.time() + 15
        while time.time() < deadline and not video_data:
            page.wait_for_timeout(500)

        # If still no data, try RENDER_DATA in page source
        if not video_data:
            try:
                html = page.content()
                match = RENDER_DATA_RE.search(html)
                if match:
                    from urllib.parse import unquote
                    decoded = unquote(match.group(1))
                    data = json.loads(decoded)
                    detail = _extract_from_render_data(data)
                    if detail:
                        video_data["detail"] = detail
                        print("[douyin] Got data from RENDER_DATA")
            except Exception as e:
                print(f"[douyin] RENDER_DATA fallback failed: {e}")

        # JS final fallback
        if not video_data:
            try:
                detail = page.evaluate("""() => {
                    try {
                        const el = document.querySelector('#RENDER_DATA');
                        if (!el) return null;
                        const d = JSON.parse(decodeURIComponent(el.textContent));
                        function find(obj, depth) {
                            if (depth > 10 || !obj || typeof obj !== 'object') return null;
                            if (obj.video && (obj.video.play_addr || obj.video.playAddr)) return obj;
                            for (const k in obj) {
                                const r = find(obj[k], depth + 1);
                                if (r) return r;
                            }
                            return null;
                        }
                        return find(d, 0);
                    } catch(e) { return null; }
                }""")
                if detail:
                    video_data["detail"] = detail
                    print("[douyin] Got data from JS fallback")
            except Exception as e:
                print(f"[douyin] JS fallback failed: {e}")

        context.close()
        browser.close()

    aweme = video_data.get("detail")
    if not aweme:
        raise RuntimeError(
            "无法获取视频信息。可能原因:\n"
            "1. 视频不存在或已删除\n"
            "2. 抖音反爬拦截了请求\n"
            "3. 网络连接超时\n"
            "请检查链接是否有效，或稍后重试。"
        )
    return aweme


def _extract_from_render_data(data, depth=0):
    """Recursively extract video info from RENDER_DATA JSON."""
    if depth > 10 or not isinstance(data, dict):
        return None
    if "video" in data and isinstance(data["video"], dict):
        v = data["video"]
        if "play_addr" in v or "playAddr" in v:
            return data
    for value in data.values():
        if isinstance(value, dict):
            r = _extract_from_render_data(value, depth + 1)
            if r:
                return r
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    r = _extract_from_render_data(item, depth + 1)
                    if r:
                        return r
    return None


def _find_best_video_url(aweme: dict) -> str:
    """Extract the best quality downloadable video URL."""
    video = aweme.get("video", {})

    # 1) download_addr — direct mp4, most reliable
    for key in ("download_addr", "play_addr_h264", "play_addr"):
        addr = video.get(key, {})
        url_list = addr.get("url_list", [])
        if url_list:
            return url_list[0]

    # 2) bit_rate options — highest quality first
    bit_rates = video.get("bit_rate", [])
    if bit_rates:
        bit_rates.sort(key=lambda x: x.get("bit_rate", 0), reverse=True)
        for br in bit_rates:
            addr = br.get("play_addr", {}) or br.get("playAddr", {})
            url_list = addr.get("url_list", []) or addr.get("urlList", [])
            if url_list:
                return url_list[0]

    raise RuntimeError("未找到可下载的视频地址")


def _extract_captions(aweme: dict) -> str:
    """Extract subtitle text from API metadata (desc, stickers, hashtags, etc.)."""
    parts = []

    desc = aweme.get("desc", "")
    if desc:
        parts.append(f"【描述】{desc}")

    stickers = aweme.get("interaction_stickers") or []
    for s in stickers:
        text = s.get("text_content", "") or s.get("text", "")
        if text:
            parts.append(f"【贴纸】{text}")

    text_extra = aweme.get("text_extra") or []
    for extra in text_extra:
        tag = extra.get("hashtag_name", "") or extra.get("tag", "")
        if tag:
            parts.append(f"#话题# {tag}")

    music = aweme.get("music") or {}
    if music:
        mt = music.get("title", "") or music.get("author", "")
        if mt:
            parts.append(f"【音乐】{mt}")

    author = aweme.get("author") or {}
    nickname = author.get("nickname", "")
    if nickname:
        parts.append(f"【作者】{nickname}")

    return "\n".join(parts) if parts else ""


def download_video(url: str, cookie_file: str = None) -> dict:
    """Download a Douyin video using Playwright browser automation.

    Returns dict with: video_id, title, description, duration, file_path,
    output_dir, captions, thumbnail_url.
    """
    url = _extract_url(url)

    # Resolve short link
    if SHORT_LINK_RE.search(url):
        full_url = _resolve_short_link(url)
    else:
        full_url = url

    video_id = _extract_video_id(full_url)

    # Fetch video metadata via Playwright
    aweme = _get_video_info_playwright(video_id)
    video_url = _find_best_video_url(aweme)

    # Download video file
    output_dir = Path(tempfile.mkdtemp())
    output_path = output_dir / f"douyin_{video_id}.mp4"

    dl_req = Request(video_url, headers={
        "User-Agent": MOBILE_UA,
        "Referer": "https://www.douyin.com/",
    })
    with urlopen(dl_req, timeout=120) as f:
        output_path.write_bytes(f.read())

    if output_path.stat().st_size < 10000:
        output_path.unlink()
        raise RuntimeError("下载的视频文件过小，可能被 CDN 拒绝")

    title = aweme.get("desc") or ""
    captions = _extract_captions(aweme)

    return {
        "video_id": video_id,
        "title": title,
        "description": aweme.get("desc", ""),
        "duration": int(aweme.get("duration", 0)) // 1000,
        "file_path": str(output_path),
        "output_dir": str(output_dir),
        "captions": captions,
    }
