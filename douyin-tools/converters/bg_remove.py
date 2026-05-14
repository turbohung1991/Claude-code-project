"""Background removal — Clipdrop / remove.bg APIs + local rembg models."""

import os
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from PIL import Image, ImageFilter
from rembg import remove, new_session

# Config file for user-configured API keys
_CONFIG_DIR = Path.home() / ".vibecoding"
_CONFIG_FILE = _CONFIG_DIR / "bgremove_keys.json"


def _load_config():
    """Load API keys from config file."""
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(data):
    """Save API keys to config file."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_api_keys():
    """Get configured API keys (config file > env vars)."""
    config = _load_config()
    return {
        "clipdrop": config.get("clipdrop") or os.environ.get("CLIPDROP_API_KEY", ""),
        "remove_bg": config.get("remove_bg") or os.environ.get("REMOVE_BG_API_KEY", ""),
    }


def _get_api_key(service):
    """Get API key for a given service (config > env)."""
    keys = get_api_keys()
    return keys.get(service, "")

REMOVE_BG_URL = "https://api.remove.bg/v1.0/removebg"
CLIPDROP_URL = "https://clipdrop-api.co/remove-background/v1"

# Track API usage (keyed by api name)
_credits_state = {}

MODELS = {
    "Clipdrop API (云端高精)": "__clipdrop_api__",
    "remove.bg API (云端高精)": "__remove_bg_api__",
    "bria_rmbg (本地推荐)": "bria_rmbg",
    "isnet (通用)": "isnet-general-use",
    "u2net (风景)": "u2net",
    "u2net_human (人像)": "u2net_human_seg",
    "u2net_cloth (服饰)": "u2net_cloth_seg",
    "silueta (快速)": "silueta",
}

ALPHA_MATTING_DEFAULTS = dict(
    foreground_threshold=200,
    background_threshold=40,
    erode_size=6,
)

EDGE_FEATHER_RADIUS = 2


def get_credits_info() -> str:
    """Return formatted credits status for UI display."""
    if not _credits_state:
        return ""
    # Show each API's status
    parts = []
    for api_name, state in _credits_state.items():
        if state.get("remaining") is not None:
            parts.append(f"{api_name}: 剩余 {state['remaining']} 次")
    return " · ".join(parts) if parts else ""


def _build_multipart(fields: list, boundary: str = None) -> tuple:
    """Build multipart/form-data body. fields is list of (name, value, filename_or_None)."""
    boundary = boundary or "----Boundary" + os.urandom(8).hex()
    boundary_bytes = boundary.encode("ascii")
    parts = []
    for name, value, filename in fields:
        parts.append(b"--" + boundary_bytes)
        if filename:
            disp = f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
            parts.append(disp.encode("utf-8"))
            parts.append(b"Content-Type: application/octet-stream")
            parts.append(b"")
            parts.append(value if isinstance(value, bytes) else value.encode("utf-8"))
        else:
            parts.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
            parts.append(b"")
            parts.append(value if isinstance(value, bytes) else value.encode("utf-8"))
    parts.append(b"--" + boundary_bytes + b"--")
    return b"\r\n".join(parts), boundary


def _remove_via_clipdrop(image_bytes: bytes) -> bytes:
    """Call Clipdrop (Stability AI / Jasper) API."""
    api_key = _get_api_key("clipdrop")
    if not api_key:
        raise RuntimeError("未配置 Clipdrop API Key。请在页面设置中填入 API Key，或设置 CLIPDROP_API_KEY 环境变量。")

    body, boundary = _build_multipart([
        ("image_file", image_bytes, "image.png"),
    ])

    req = Request(
        CLIPDROP_URL,
        data=body,
        headers={
            "x-api-key": api_key,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
        method="POST",
    )

    try:
        resp = urlopen(req, timeout=60)
        result = resp.read()

        # Track credits from response headers
        remaining = resp.headers.get("x-remaining-credits") or resp.headers.get("RateLimit-Remaining") or "?"
        _credits_state["Clipdrop"] = {"remaining": remaining}
        print(f"[Clipdrop] 成功。剩余额度: {remaining} 次")

        return result
    except URLError as e:
        if hasattr(e, "read"):
            err_body = e.read().decode(errors="replace")
            try:
                err_data = json.loads(err_body)
                msg = err_data.get("error", err_body)[:300]
            except Exception:
                msg = err_body[:300]
        else:
            msg = str(e.reason)
        raise RuntimeError(f"Clipdrop API 错误: {msg}")


def _remove_via_removebg(image_bytes: bytes) -> bytes:
    """Call remove.bg API."""
    api_key = _get_api_key("remove_bg")
    if not api_key:
        raise RuntimeError("未配置 remove.bg API Key。请在页面设置中填入 API Key，或设置 REMOVE_BG_API_KEY 环境变量。")

    body, boundary = _build_multipart([
        ("image_file", image_bytes, "image.png"),
        ("size", "auto", None),
    ])

    req = Request(
        REMOVE_BG_URL,
        data=body,
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
            "User-Agent": "ClaudeCodeConverter/1.0",
        },
        method="POST",
    )

    try:
        resp = urlopen(req, timeout=60)
        result = resp.read()

        remaining = resp.headers.get("X-RateLimit-Remaining", "?")
        total = resp.headers.get("X-RateLimit-Limit", "?")
        _credits_state["remove.bg"] = {"remaining": remaining, "total": total}
        print(f"[remove.bg] 成功。剩余额度: {remaining}/{total} 次")

        return result
    except URLError as e:
        if hasattr(e, "read"):
            err_body = e.read().decode(errors="replace")
            try:
                err_data = json.loads(err_body)
                msg = err_data.get("errors", [{}])[0].get("title", err_body)
            except Exception:
                msg = err_body[:300]
        else:
            msg = str(e.reason)
        raise RuntimeError(f"remove.bg API 错误: {msg}")


def _refine_edges(image_bytes: bytes, feather_radius: int = EDGE_FEATHER_RADIUS) -> bytes:
    """Apply edge feathering on alpha channel."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    if feather_radius > 0:
        r, g, b, alpha = img.split()
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=feather_radius))
        img = Image.merge("RGBA", (r, g, b, alpha))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def remove_background(
    image_path: str,
    model_name: str = "bria_rmbg",
    alpha_matting: bool = False,
    bg_color: str = "transparent",
    feather: bool = True,
) -> tuple:
    """Remove background. Routes to Clipdrop, remove.bg, or local rembg.

    Returns (nobg_path, result_path).
    """
    with open(image_path, "rb") as f:
        input_bytes = f.read()

    # ── Cloud API paths ──
    if model_name == "__clipdrop_api__":
        output_bytes = _remove_via_clipdrop(input_bytes)
        if feather:
            output_bytes = _refine_edges(output_bytes, feather_radius=1)
    elif model_name == "__remove_bg_api__":
        output_bytes = _remove_via_removebg(input_bytes)
        if feather:
            output_bytes = _refine_edges(output_bytes, feather_radius=1)
    # ── Local rembg path ──
    else:
        session = new_session(model_name)
        if alpha_matting:
            output_bytes = remove(
                input_bytes,
                session=session,
                alpha_matting=True,
                alpha_matting_foreground_threshold=ALPHA_MATTING_DEFAULTS["foreground_threshold"],
                alpha_matting_background_threshold=ALPHA_MATTING_DEFAULTS["background_threshold"],
                alpha_matting_erode_size=ALPHA_MATTING_DEFAULTS["erode_size"],
            )
        else:
            output_bytes = remove(input_bytes, session=session)
        if feather:
            output_bytes = _refine_edges(output_bytes)

    stem = Path(image_path).stem
    parent = Path(image_path).parent

    nobg_path = parent / f"{stem}_nobg.png"
    with open(nobg_path, "wb") as f:
        f.write(output_bytes)

    if bg_color == "transparent":
        return str(nobg_path), str(nobg_path)

    fg = Image.open(nobg_path).convert("RGBA")
    bg = Image.new("RGBA", fg.size, bg_color)
    composited = Image.alpha_composite(bg, fg)
    composited_path = parent / f"{stem}_{bg_color.replace('#', '')}.png"
    composited.save(str(composited_path), "PNG")
    return str(nobg_path), str(composited_path)
