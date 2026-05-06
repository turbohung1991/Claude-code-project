"""Content analysis using DashScope API (Anthropic-compatible endpoint)."""

import os
import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError


DASHSCOPE_API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
DASHSCOPE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://coding.dashscope.aliyuncs.com/apps/anthropic") + "/v1/messages"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "qwen3.6-plus")

AVAILABLE_MODELS = [DEFAULT_MODEL]

# Section accent colors
SECTION_COLORS = {
    "主题": "#7c3aed", "类型": "#7c3aed",
    "钩子": "#2563eb", "开头": "#2563eb",
    "节奏": "#0891b2", "情绪": "#0891b2",
    "互动": "#d97706", "引导": "#d97706",
    "爆款": "#dc2626", "要素": "#dc2626",
    "优化": "#059669", "建议": "#059669", "改进": "#059669",
}


def _detect_section_color(header_text):
    for keyword, color in SECTION_COLORS.items():
        if keyword in header_text:
            return color
    return "#6b7280"


def _md_to_html(md_text):
    """Convert analysis markdown to styled HTML with highlighted sections."""
    lines = md_text.strip().split("\n")
    html_parts = []
    in_list = False
    current_color = "#6b7280"

    for line in lines:
        stripped = line.strip()

        # H3 headers → styled section headers
        if stripped.startswith("### "):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            title = stripped[4:].strip()
            current_color = _detect_section_color(title)
            html_parts.append(
                f'<div style="margin:18px 0 10px 0; padding:10px 14px; '
                f'background:linear-gradient(135deg, {current_color}12 0%, {current_color}08 100%); '
                f'border-left:3px solid {current_color}; border-radius:0 8px 8px 0;">'
                f'<h3 style="margin:0; font-size:1.05em; font-weight:700; color:{current_color};">'
                f'{title}</h3></div>'
            )
            continue

        # H2 headers
        if stripped.startswith("## "):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            title = stripped[4:].strip()
            html_parts.append(
                f'<div style="margin:20px 0 12px 0; padding:8px 14px; '
                f'background:#1a1a2e; border-radius:8px;">'
                f'<h2 style="margin:0; font-size:1.15em; font-weight:700; color:#fff;">'
                f'{title}</h2></div>'
            )
            continue

        # Bullet points
        if re.match(r"^[-*]\s", stripped):
            if not in_list:
                html_parts.append('<ul style="margin:4px 0; padding-left:20px;">')
                in_list = True
            text = re.sub(r"^[-*]\s+", "", stripped)
            # Bold → highlighted
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#1a1a2e;">\1</strong>', text)
            html_parts.append(
                f'<li style="margin:4px 0; line-height:1.65; color:#475569; font-size:0.95em;">'
                f'{text}</li>'
            )
            continue

        # Numbered list items
        if re.match(r"^\d+[\.\)]\s", stripped):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            text = re.sub(r"^\d+[\.\)]\s+", "", stripped)
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#1a1a2e;">\1</strong>', text)
            html_parts.append(
                f'<div style="margin:6px 0; padding:8px 14px; background:#f8f9fb; '
                f'border-radius:8px; border:1px solid #edf0f4; line-height:1.6; font-size:0.95em;">'
                f'<span style="color:{current_color}; font-weight:700; margin-right:6px;">●</span>'
                f'{text}</div>'
            )
            continue

        # Regular paragraph
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue

        if in_list:
            html_parts.append('</ul>')
            in_list = False

        text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#1a1a2e; background:#fef3c7; padding:1px 4px; border-radius:3px;">\1</strong>', stripped)
        html_parts.append(
            f'<p style="margin:6px 0; line-height:1.7; color:#4b5563; font-size:0.95em;">{text}</p>'
        )

    if in_list:
        html_parts.append('</ul>')

    html_body = "\n".join(html_parts)
    return f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
            max-height: 600px; overflow-y: auto; padding-right: 8px;
            scrollbar-width: thin; scrollbar-color: #c8cdd6 #f2f4f7;">
{html_body}
</div>"""

ANALYSIS_PROMPT = """你是一位资深的抖音短视频内容运营专家。请分析以下从抖音视频中提取的字幕文本，给出专业的内容策略分析。

## 字幕文本：
{subtitle_text}

## 请从以下维度分析：

### 1. 内容主题和类型
- 这个视频属于什么赛道/领域？
- 内容的核心主题是什么？

### 2. 开头钩子策略
- 视频开头（前几行字幕）用了什么方式吸引观众？
- 钩子类型：悬念/痛点/共鸣/反差/好奇/利益？

### 3. 信息/情绪节奏
- 内容的节奏如何？密集输出还是渐入佳境？
- 情绪变化曲线是怎样的？

### 4. 互动引导方式
- 是否有点赞/评论/关注等引导？
- 引导方式是否自然？

### 5. 爆款要素分析
- 这段内容有哪些做得好的地方？
- 是否符合抖音的流量推荐逻辑？

### 6. 优化建议
- 给出 3 条具体可执行的改进建议

请用简洁专业的中文输出分析结果。"""


def list_available_models():
    """Return list of available models for content analysis."""
    return AVAILABLE_MODELS


def analyze_content(subtitle_text: str, model: str = None) -> str:
    """Analyze video content strategy using DashScope API.

    Returns highlighted HTML string.
    """
    if not subtitle_text.strip():
        return '<div style="color:#dc2626; padding:16px;">错误: 字幕文本为空，无法分析。</div>'

    if not DASHSCOPE_API_KEY:
        return '<div style="color:#dc2626; padding:16px;">错误: 未设置 DashScope API Key。</div>'

    model = model or DEFAULT_MODEL

    if len(subtitle_text) > 8000:
        subtitle_text = subtitle_text[:8000] + "\n...(文本过长已截断)"

    prompt = ANALYSIS_PROMPT.format(subtitle_text=subtitle_text)

    body = json.dumps({
        "model": model,
        "max_tokens": 4000,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "user", "content": "你是专业的短视频内容运营分析助手。\n\n" + prompt},
        ],
    }).encode("utf-8")

    req = Request(
        DASHSCOPE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        resp = urlopen(req, timeout=120)
        data = json.loads(resp.read().decode())

        content_blocks = data.get("content", [])
        for block in content_blocks:
            if block.get("type") == "text":
                raw_text = block.get("text", "")
                return _md_to_html(raw_text)
        return f'<div style="color:#dc2626; padding:16px;">分析失败: 无法解析响应</div>'

    except URLError as e:
        return f'<div style="color:#dc2626; padding:16px;">分析失败: 网络错误 - {str(e.reason)}</div>'
    except Exception as e:
        return f'<div style="color:#dc2626; padding:16px;">分析失败: {str(e)}</div>'
