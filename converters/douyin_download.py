"""Douyin video downloader.

Calls Douyin API directly with a_bogus signing. No external service required.
"""

import json
import re
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote

from converters.abogus import ABogus

DOUYIN_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

POST_DETAIL_URL = "https://www.douyin.com/aweme/v1/web/aweme/detail/"

SHORT_LINK_RE = re.compile(r"https?://v\.douyin\.com/[\w\-_]+/?")
VIDEO_ID_RE = re.compile(r"douyin\.com/(?:video|note)/(\d+)")
URL_EXTRACT_RE = re.compile(
    r"https?://(?:v\.douyin\.com/[\w\-_]+/?|(?:www\.)?douyin\.com/(?:video|note)/\d+)"
)

# Base params Douyin expects — mirrors BaseRequestModel from the API project
BASE_PARAMS = {
    "device_platform": "webapp",
    "aid": "6383",
    "channel": "channel_pc_web",
    "pc_client_type": "1",
    "version_code": "290100",
    "version_name": "29.1.0",
    "cookie_enabled": "true",
    "screen_width": "1920",
    "screen_height": "1080",
    "browser_language": "zh-CN",
    "browser_platform": "Win32",
    "browser_name": "Chrome",
    "browser_version": "130.0.0.0",
    "browser_online": "true",
    "engine_name": "Blink",
    "engine_version": "130.0.0.0",
    "os_name": "Windows",
    "os_version": "10",
    "cpu_core_num": "12",
    "device_memory": "8",
    "platform": "PC",
    "downlink": "10",
    "effective_type": "4g",
    "from_user_page": "1",
    "locate_query": "false",
    "need_time_list": "1",
    "pc_libra_divert": "Windows",
    "publish_video_strategy_type": "2",
    "round_trip_time": "0",
    "show_live_replay_strategy": "1",
}


def _extract_url(text: str) -> str:
    m = URL_EXTRACT_RE.search(text)
    return m.group(0) if m else text.strip()


def _extract_aweme_id(url: str) -> str:
    m = VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)

    # Short link — follow redirect
    req = Request(url, headers={"User-Agent": DOUYIN_UA})
    resp = urlopen(req, timeout=15)
    final = resp.geturl()
    m = VIDEO_ID_RE.search(final)
    if m:
        return m.group(1)
    raise ValueError(f"无法提取视频 ID: {final}")


def _build_signed_url(aweme_id: str) -> str:
    """Build the Douyin API URL with a_bogus signing."""
    params = dict(BASE_PARAMS)
    params["aweme_id"] = aweme_id
    params["msToken"] = ""

    # Generate a_bogus
    a_bogus = ABogus().get_value(params)

    # Encode — ABogus returns a quote()-ed value, so we re-encode the params
    query = urlencode(params, safe="")
    return f"{POST_DETAIL_URL}?{query}&a_bogus={quote(a_bogus, safe='')}"


def _fetch_video_info(aweme_id: str) -> dict:
    """Call Douyin API directly with a_bogus signing to get video metadata."""
    url = _build_signed_url(aweme_id)

    req = Request(url, headers={
        "User-Agent": DOUYIN_UA,
        "Referer": "https://www.douyin.com/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })

    resp = urlopen(req, timeout=30)
    data = json.loads(resp.read().decode())

    if data.get("status_code") != 0:
        raise RuntimeError(f"Douyin API 返回错误: {data.get('status_msg', 'unknown')}")

    aweme = data.get("aweme_detail", {})
    if not aweme:
        raise RuntimeError("无法获取视频信息: aweme_detail 为空")
    return aweme


def _find_video_url(aweme: dict) -> str:
    """Extract the best downloadable video URL from an aweme detail dict."""
    video = aweme.get("video", {})
    for key in ("download_addr", "play_addr", "play_addr_h264"):
        addr = video.get(key, {})
        url_list = addr.get("url_list", [])
        if url_list:
            return url_list[0]

    # Last resort
    for key in ("play_addr_265",):
        addr = video.get(key, {})
        url_list = addr.get("url_list", [])
        if url_list:
            return url_list[0]

    raise RuntimeError("未找到可下载的视频地址")


def download_video(url: str, cookie_file: str = None) -> dict:
    """Download a Douyin video.

    Returns dict with video_id, title, file_path, output_dir, duration.
    Works standalone — no external API service needed.
    """
    url = _extract_url(url)

    # Resolve short link
    if SHORT_LINK_RE.search(url):
        req = Request(url, headers={"User-Agent": DOUYIN_UA})
        full_url = urlopen(req, timeout=15).geturl()
    else:
        full_url = url

    aweme_id = _extract_aweme_id(full_url)

    # Fetch video metadata from Douyin API
    aweme = _fetch_video_info(aweme_id)
    video_url = _find_video_url(aweme)

    # Download
    output_dir = Path(tempfile.mkdtemp())
    output_path = output_dir / f"douyin_{aweme_id}.mp4"

    dl_req = Request(video_url, headers={
        "User-Agent": MOBILE_UA,
        "Referer": "https://www.douyin.com/",
    })
    with urlopen(dl_req, timeout=120) as f:
        output_path.write_bytes(f.read())

    size = output_path.stat().st_size
    if size < 10000:
        output_path.unlink()
        raise RuntimeError("下载的视频文件过小，可能失败")

    title = aweme.get("desc") or aweme.get("share_info", {}).get("share_title") or ""
    duration = int(aweme.get("duration", 0)) // 1000

    return {
        "video_id": aweme_id,
        "title": title,
        "description": aweme.get("desc", ""),
        "duration": duration,
        "file_path": str(output_path),
        "output_dir": str(output_dir),
    }
