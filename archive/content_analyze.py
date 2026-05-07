"""Content strategy analysis — DeepSeek API via OpenAI SDK.

Matches douyin-tool-clean/strategy.py approach:
- 6-dimension structured analysis
- Rich video metadata for context
- MD → styled HTML output
"""

import json
import os
from openai import OpenAI

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.deepseek.com/v1"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL") or "deepseek-chat"

AVAILABLE_MODELS = [DEFAULT_MODEL]

ANALYSIS_PROMPT = """你是一位顶尖的抖音内容策略分析师。请根据提供的视频信息，进行专业的策略分析。

## 视频信息
- 标题/描述: {desc}
- 作者: {author}
- 音乐: {music}
- 话题标签: {hashtags}
- 时长: {duration}秒
- 清晰度: {resolution}
- 字幕/文案内容: {subtitles}

## 分析要求
请从以下维度进行深度分析，输出结构化的策略报告：

### 1. 内容定位
- 赛道/领域分类
- 目标受众画像
- 内容核心价值点

### 2. 爆款要素拆解
- 黄金前3秒吸引力分析
- 节奏把控与完播率设计
- 情绪价值/信息价值/娱乐价值的配比
- BGM选择策略

### 3. 文案与话术
- 标题钩子技巧
- 正文/字幕的文案结构
- 互动引导方式（点赞/评论/关注话术）

### 4. 视觉呈现
- 拍摄手法与机位
- 剪辑节奏与转场
- 滤镜/特效/贴纸运用

### 5. 数据潜力评估
- 预估受众共鸣度 (1-10)
- 传播潜力评分 (1-10)
- 商业化可行性 (1-10)

### 6. 可复制策略
- 如果要做同类内容，应该怎么执行？
- 这个视频可以怎么迭代优化？
- 有哪些可以直接用的技巧？

请用中文输出，要有洞察、有数据、有可执行的建议。不要空泛。"""


def _md_to_html(md_text: str) -> str:
    """Convert analysis markdown to dark-themed styled HTML."""
    import re
    lines = md_text.strip().split("\n")
    html = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append('<div style="height:8px;"></div>')
            continue

        # H2 headers
        if stripped.startswith("## "):
            if in_list:
                html.append("</ul>")
                in_list = False
            title = stripped[3:].strip()
            html.append(
                f'<h2 style="font-size:1.15rem; color:#ff6b9d; margin:20px 0 10px; '
                f'padding-bottom:6px; border-bottom:1px solid #2a2a3a;">{title}</h2>'
            )
            continue

        # H3 headers
        if stripped.startswith("### "):
            if in_list:
                html.append("</ul>")
                in_list = False
            title = stripped[4:].strip()
            html.append(
                f'<h3 style="font-size:1rem; color:#4ecdc4; margin:14px 0 8px;">{title}</h3>'
            )
            continue

        # Bullet points
        if re.match(r"^[-*]\s", stripped):
            if not in_list:
                html.append('<ul style="margin:4px 0; padding-left:20px;">')
                in_list = True
            text = re.sub(r"^[-*]\s+", "", stripped)
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#e0e0e0;">\1</strong>', text)
            html.append(
                f'<li style="margin:4px 0; line-height:1.7; color:#b0b0b0; font-size:0.9rem;">{text}</li>'
            )
            continue

        # Numbered items
        if re.match(r"^\d+[\.\)]\s", stripped):
            if in_list:
                html.append("</ul>")
                in_list = False
            text = re.sub(r"^\d+[\.\)]\s+", "", stripped)
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#e0e0e0;">\1</strong>', text)
            html.append(
                f'<div style="margin:6px 0; padding:10px 14px; background:#14101e; '
                f'border-radius:8px; border:1px solid #2a2a3a; line-height:1.7; font-size:0.9rem; '
                f'border-left:3px solid #6c5ce7;">{text}</div>'
            )
            continue

        # Regular paragraph
        if in_list:
            html.append("</ul>")
            in_list = False
        text = re.sub(r"\*\*(.+?)\*\*",
                       r'<span style="background:rgba(255,107,157,0.15); padding:1px 6px; border-radius:4px;">\1</span>',
                       stripped)
        html.append(
            f'<p style="margin:6px 0; line-height:1.8; color:#b0b0b0; font-size:0.9rem;">{text}</p>'
        )

    if in_list:
        html.append("</ul>")

    body = "\n".join(html)
    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            max-height:65vh; overflow-y:auto; padding-right:8px;
            scrollbar-width:thin; scrollbar-color:#2a2a3a #111119;">
{body}
</div>"""


def list_available_models():
    return AVAILABLE_MODELS


def analyze_content(subtitle_text: str = "", model: str = None, video_meta: dict = None) -> str:
    """Analyze video content strategy using DeepSeek API.

    Args:
        subtitle_text: Caption/subtitle text (optional, enriched with video_meta).
        model: Model name.
        video_meta: dict with desc, author, music, hashtags, duration, resolution.

    Returns:
        Styled HTML analysis report.
    """
    meta = video_meta or {}

    desc = meta.get("desc") or meta.get("title") or "无"
    author = meta.get("author", {}).get("nickname", "未知") if isinstance(meta.get("author"), dict) else (meta.get("author") or "未知")
    music_info = meta.get("music", {}) or {}
    music = music_info.get("title", "") or music_info.get("author", "无") if isinstance(music_info, dict) else "无"

    hashtag_str = meta.get("hashtags", "") or ""
    duration = (meta.get("duration", 0) or 0) // 1000 if isinstance(meta.get("duration"), int) else int(meta.get("duration", 0))
    width = (meta.get("video", {}) or {}).get("width", 0) if isinstance(meta.get("video"), dict) else 0
    height = (meta.get("video", {}) or {}).get("height", 0) if isinstance(meta.get("video"), dict) else 0
    resolution = f"{width}x{height}" if width and height else "未知"

    if not DEEPSEEK_API_KEY:
        return '<div style="color:#ff6b6b; padding:16px;">未配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量。</div>'

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    model = model or DEFAULT_MODEL

    prompt = ANALYSIS_PROMPT.format(
        desc=desc[:200],
        author=author,
        music=music,
        hashtags=hashtag_str,
        duration=duration,
        resolution=resolution,
        subtitles=subtitle_text[:2000] if subtitle_text else "无",
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位专业的抖音内容策略分析师，输出必须结构化、有深度、可执行。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=3000,
        )
        text = response.choices[0].message.content
        return _md_to_html(text)
    except Exception as e:
        return f'<div style="color:#ff6b6b; padding:16px;">分析失败: {str(e)}</div>'
