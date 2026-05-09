#!/usr/bin/env python3
"""
Vibecoding — 抖音下载分析 + 格式转换工具箱
Flask + SSE + Playwright + DeepSeek
"""

import os
import sys
import json
import uuid
import asyncio
import threading
import time
import tempfile
import zipfile
from queue import Queue
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Load .env ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS

# ── Douyin modules (from douyin-tool-clean) ──
from src.core import DouyinParser
from src.downloader import VideoDownloader
from src.subtitle import SubtitleExtractor
from src.strategy import StrategyAnalyzer

# ── Converter modules ──
from converters.pdf_to_ppt import pdf_to_ppt
from converters.ppt_to_images import ppt_to_images
from converters.pdf_to_images import pdf_to_images
from converters.images_to_pdf import images_to_pdf
from converters.bg_remove import remove_background, MODELS, get_credits_info
from src.batch_manager import batch_manager
from src.comment_analyzer import comment_analyzer

app = Flask(__name__)
CORS(app)

# ── Config ──
PORT = int(os.environ.get("PORT", 7860))
DEBUG = os.environ.get("DEBUG", "0") == "1"
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

tasks = {}
_comment_cache = {}

# ── Playwright auto-install on startup ──
def _ensure_playwright():
    for cache_dir in ("~/.cache/ms-playwright", "~/Library/Caches/ms-playwright"):
        cache = os.path.expanduser(cache_dir)
        if os.path.isdir(cache) and os.listdir(cache):
            return
    print("[setup] Installing Playwright Chromium (one-time, ~300MB)...")
    import subprocess
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
                   check=False, timeout=300)

_ensure_playwright()


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def create_task():
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {"queue": Queue(), "status": "created", "result": {}}
    return task_id

def push_event(task_id, event_type, data):
    if task_id in tasks:
        tasks[task_id]["queue"].put({"event": event_type, "data": data})


# ═══════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/convert")
def convert_page():
    return render_template("convert.html")

@app.route("/bgremove")
def bgremove_page():
    return render_template("bgremove.html")


@app.route("/batch")
def batch_page():
    return render_template("batch.html")


# ═══════════════════════════════════════════════════════════════
# Douyin API (100% douyin-tool-clean)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/parse", methods=["POST"])
def parse_url():
    url = request.json.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "请输入抖音链接"})

    link_type = DouyinParser.detect_link_type(url)
    video_id = asyncio.run(DouyinParser.parse_url(url))

    if not video_id:
        return jsonify({
            "success": False,
            "error": f"链接解析失败（{DouyinParser.link_type_label(link_type)}），请检查链接是否有效"
        })

    try:
        video_data = asyncio.run(DouyinParser.get_video_info(video_id))
    except Exception:
        video_data = None

    if not video_data:
        return jsonify({
            "success": False,
            "error": "无法获取视频信息。可能原因：链接已失效、视频已删除或网络异常。",
            "video_id": video_id,
        })

    quality_options = DouyinParser.parse_quality_options(video_data)
    subtitles = DouyinParser.extract_captions(video_data) or ""

    return jsonify({
        "success": True,
        "video_id": video_id,
        "link_type": link_type,
        "info": {
            "desc": video_data.get("desc", "无"),
            "author": video_data.get("author", {}).get("nickname", "未知"),
            "duration": (video_data.get("duration", 0) or 0) // 1000,
            "cover": (video_data.get("video", {}).get("cover", {}).get("url_list", [""])[0] or
                      video_data.get("video", {}).get("origin_cover", {}).get("url_list", [""])[0] or ""),
            "stats": {
                "digg": video_data.get("statistics", {}).get("digg_count", 0) or
                        video_data.get("statistics", {}).get("admire_count", 0),
                "comment": video_data.get("statistics", {}).get("comment_count", 0),
                "share": video_data.get("statistics", {}).get("share_count", 0),
            },
            "hashtags": [
                e.get("hashtag_name", "") or e.get("tag", "")
                for e in video_data.get("text_extra", [])
            ],
            "music": {
                "title": video_data.get("music", {}).get("title", ""),
                "author": video_data.get("music", {}).get("author", ""),
            }
        },
        "qualities": [
            {"label": q["label"], "gear_name": q["gear_name"],
             "bit_rate": q["bit_rate"], "width": q["width"], "height": q["height"]}
            for q in (quality_options or [])
        ] or [{"label": "默认", "gear_name": "default", "bit_rate": 0, "width": 0, "height": 0}],
        "subtitles_preview": subtitles[:500],
    })


@app.route("/api/process", methods=["POST"])
def process_video():
    data = request.json
    url = data.get("url", "")
    quality_index = data.get("quality_index", 0)
    run_ai = data.get("ai", True)

    task_id = create_task()

    def process():
        try:
            push_event(task_id, "progress", {"step": "parse", "message": "正在解析...", "percent": 5})
            link_type = DouyinParser.detect_link_type(url)
            video_id = asyncio.run(DouyinParser.parse_url(url))

            if not video_id:
                push_event(task_id, "error", {"message": f"链接解析失败（{DouyinParser.link_type_label(link_type)}）"})
                return

            push_event(task_id, "progress", {"step": "parse", "message": "正在加载视频信息...", "percent": 10})
            video_data = asyncio.run(DouyinParser.get_video_info(video_id))
            if not video_data:
                push_event(task_id, "error", {"message": "无法获取视频信息，链接可能已失效"})
                return

            push_event(task_id, "progress", {"step": "parse", "message": "视频信息已获取", "percent": 15})

            quality_options = DouyinParser.parse_quality_options(video_data)
            if not quality_options:
                play_addr = video_data.get("video", {}).get("play_addr", {}) or video_data.get("video", {}).get("playAddr", {})
                url_list = play_addr.get("url_list", []) or play_addr.get("urlList", [])
                quality_options = [{"label": "默认", "gear_name": "default", "bit_rate": 0,
                                    "url": url_list[0] if url_list else "", "url_list": url_list}]

            selected = quality_options[min(quality_index, len(quality_options) - 1)]

            push_event(task_id, "progress", {"step": "download", "message": f"正在下载 ({selected['label']})...", "percent": 20})

            desc = video_data.get("desc", "douyin_video")
            filename = desc[:30]
            for ch in "#?&= ，。！？、；：""''【】《》\t\n\r":
                filename = filename.replace(ch, "_")
            filename = filename.replace("/", "_").replace("\\", "_").strip() or video_id
            save_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp4")

            try:
                import requests as req
                video_url = selected.get("url") or selected.get("url_list", [""])[0]
                if not video_url:
                    push_event(task_id, "error", {"message": "无法获取视频下载地址"})
                    return

                headers = {
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                    "Referer": "https://www.douyin.com/",
                }
                resp = req.get(video_url, headers=headers, stream=True, timeout=120)
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))

                downloaded = 0
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = 20 + int(downloaded * 25 / total)
                                push_event(task_id, "progress", {
                                    "step": "download",
                                    "message": f"{downloaded//1024//1024}MB / {total//1024//1024}MB",
                                    "percent": min(pct, 45)
                                })

                file_size = os.path.getsize(save_path)
                push_event(task_id, "progress", {"step": "download", "message": f"下载完成 ({file_size/1024/1024:.1f}MB)", "percent": 45})
                safe_filename = quote(f"{filename}.mp4", safe="")
                download_url = f"/api/download/{safe_filename}"

                push_event(task_id, "video_ready", {
                    "filename": f"{filename}.mp4",
                    "size": file_size,
                    "size_display": f"{file_size/1024/1024:.1f}MB",
                    "quality": selected["label"],
                    "url": download_url,
                })

            except Exception as e:
                push_event(task_id, "error", {"message": f"下载失败: {str(e)}"})
                return

            # Subtitle
            push_event(task_id, "progress", {"step": "subtitle", "message": "正在提取字幕...", "percent": 50})
            extractor = SubtitleExtractor(output_dir=DOWNLOAD_DIR)
            subtitle_result = extractor.extract(video_data, save_path)
            push_event(task_id, "subtitle_ready", {
                "text": subtitle_result.get("text", ""),
                "source": subtitle_result.get("source", "none"),
            })
            push_event(task_id, "progress", {"step": "subtitle", "message": "字幕提取完成", "percent": 55})

            # AI analysis
            if run_ai:
                subtitle_text = subtitle_result.get("text", "")
                push_event(task_id, "progress", {"step": "ai", "message": "AI策略分析中...", "percent": 60})
                try:
                    analyzer = StrategyAnalyzer()
                    analysis = analyzer.analyze(video_data, subtitles=subtitle_text)
                    if analysis["success"]:
                        push_event(task_id, "ai_ready", {
                            "analysis": analysis["analysis"],
                            "model": analysis["metadata"].get("model", ""),
                            "tokens": analysis["metadata"].get("usage", {}),
                        })
                        push_event(task_id, "progress", {"step": "ai", "message": "策略分析完成", "percent": 100})
                        _save_analysis(filename, video_data, analysis)
                    else:
                        push_event(task_id, "ai_ready", {"analysis": f"分析失败: {analysis['analysis']}", "error": True})
                except Exception as e:
                    push_event(task_id, "ai_ready", {"analysis": f"AI分析异常: {str(e)}", "error": True})
            else:
                push_event(task_id, "progress", {"step": "done", "message": "处理完成", "percent": 100})

            push_event(task_id, "complete", {"message": "全部完成！"})

        except Exception as e:
            push_event(task_id, "error", {"message": f"处理异常: {str(e)}"})

    threading.Thread(target=process, daemon=True).start()
    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/stream/<task_id>")
def stream(task_id):
    queue = None

    # Check global tasks dict first
    if task_id in tasks:
        queue = tasks[task_id]["queue"]
    else:
        # Check batch manager's tasks
        for batch in batch_manager.batches.values():
            for t in batch.get('tasks', []):
                if t['task_id'] == task_id:
                    queue = t['queue']
                    break
            if queue:
                break

    if queue is None:
        return jsonify({"error": "任务不存在"}), 404

    def generate():
        while True:
            try:
                event = queue.get(timeout=30)
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                if event["event"] in ("complete", "error"):
                    break
            except Exception:
                yield f"event: heartbeat\ndata: {json.dumps({})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/download/<filename>")
def serve_video(filename):
    path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="video/mp4")
    return jsonify({"error": "文件不存在"}), 404


@app.route("/api/videos")
def list_videos():
    videos = []
    for f in sorted(os.listdir(DOWNLOAD_DIR), reverse=True):
        if f.endswith(".mp4"):
            path = os.path.join(DOWNLOAD_DIR, f)
            videos.append({
                "filename": f,
                "size": os.path.getsize(path),
                "size_display": f"{os.path.getsize(path)/1024/1024:.1f}MB",
                "url": f"/api/download/{quote(f, safe='')}",
            })
    return jsonify({"videos": videos})


@app.route("/api/videos/<filename>", methods=["DELETE"])
def delete_video(filename):
    path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "文件不存在"}), 404
    os.remove(path)
    # Also delete associated analysis if exists
    analysis_file = filename.rsplit(".", 1)[0] + "_analysis.json"
    analysis_path = os.path.join(DOWNLOAD_DIR, analysis_file)
    if os.path.exists(analysis_path):
        os.remove(analysis_path)
    return jsonify({"success": True})


@app.route("/api/analyses/<filename>", methods=["DELETE"])
def delete_analysis(filename):
    path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "文件不存在"}), 404
    os.remove(path)
    return jsonify({"success": True})


@app.route("/api/analyses")
def list_analyses():
    analyses = []
    for f in sorted(os.listdir(DOWNLOAD_DIR), reverse=True):
        if f.endswith("_analysis.json"):
            path = os.path.join(DOWNLOAD_DIR, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except Exception:
                data = {}
            analyses.append({
                "file": f,
                "filename": data.get("filename", f.replace("_analysis.json", "")),
                "desc": data.get("desc", "")[:80],
                "author": data.get("author", "未知"),
                "duration": data.get("duration", 0),
                "model": data.get("model", ""),
                "created_at": data.get("created_at", 0),
                "preview": data.get("analysis", "")[:200],
                "video_url": f"/api/download/{quote(f.replace('_analysis.json', '.mp4'), safe='')}",
            })
    return jsonify({"analyses": analyses})


@app.route("/api/analyses/<filename>")
def get_analysis(filename):
    path = os.path.join(DOWNLOAD_DIR, filename)
    if not filename.endswith("_analysis.json") or not os.path.exists(path):
        return jsonify({"error": "报告不存在"}), 404
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


def _save_analysis(filename, video_data, analysis):
    report_path = os.path.join(DOWNLOAD_DIR, filename + "_analysis.json")
    report = {
        "filename": filename,
        "desc": video_data.get("desc", "").strip()[:200] or filename[:60],
        "author": video_data.get("author", {}).get("nickname", "未知"),
        "duration": (video_data.get("duration", 0) or 0) // 1000,
        "created_at": int(time.time()),
        "model": analysis.get("metadata", {}).get("model", ""),
        "analysis": analysis.get("analysis", ""),
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# Batch Download API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/batch/create", methods=["POST"])
def batch_create():
    urls = request.json.get("urls", [])
    if not urls:
        return jsonify({"success": False, "error": "请提供至少一个链接"})
    if len(urls) > 50:
        return jsonify({"success": False, "error": "单次最多50个链接"})

    batch_id = batch_manager.create_batch(urls)
    batch_manager.start(batch_id)
    status = batch_manager.get_status(batch_id)

    return jsonify({
        "success": True,
        "batch_id": batch_id,
        "tasks": status["tasks"] if status else [],
    })


@app.route("/api/batch/status/<batch_id>")
def batch_status(batch_id):
    status = batch_manager.get_status(batch_id)
    if not status:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(status)


@app.route("/api/batch/pause", methods=["POST"])
def batch_pause():
    batch_id = request.json.get("batch_id", "")
    batch_manager.pause(batch_id)
    return jsonify({"success": True})


@app.route("/api/batch/resume", methods=["POST"])
def batch_resume():
    batch_id = request.json.get("batch_id", "")
    batch_manager.resume(batch_id)
    return jsonify({"success": True})


@app.route("/api/batch/retry/<task_id>", methods=["POST"])
def batch_retry(task_id):
    for batch_id, batch in batch_manager.batches.items():
        for task in batch['tasks']:
            if task['task_id'] == task_id:
                batch_manager.retry_task(batch_id, task_id)
                return jsonify({"success": True})
    return jsonify({"error": "任务不存在"}), 404


# ═══════════════════════════════════════════════════════════════
# Comment Analysis API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/comments/fetch", methods=["POST"])
def comments_fetch():
    video_id = request.json.get("video_id", "")
    if not video_id:
        return jsonify({"success": False, "error": "缺少 video_id"})

    def do_fetch():
        import traceback
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = comment_analyzer.fetch_and_analyze(video_id)
            print(f"[comments] fetch complete: {result.get('total_fetched', 0)} comments")
            _comment_cache[video_id] = result
        except Exception as e:
            print(f"[comments] fetch error: {e}")
            traceback.print_exc()
            _comment_cache[video_id] = {"error": str(e), "total_fetched": 0}

    threading.Thread(target=do_fetch, daemon=True).start()
    return jsonify({"success": True, "message": "评论抓取已启动"})


@app.route("/api/comments/result/<video_id>")
def comments_result(video_id):
    result = _comment_cache.get(video_id)
    if not result:
        return jsonify({"status": "fetching"})
    if result.get("error"):
        return jsonify({"status": "error", "error": result["error"]})
    return jsonify(result)


@app.route("/api/comments/export/<video_id>")
def comments_export(video_id):
    data = _comment_cache.get(video_id)
    if not data or data.get("error"):
        return jsonify({"error": "无分析数据"}), 404

    analysis = data.get("analysis", {})
    sentiment = analysis.get("sentiment", {})
    keywords = analysis.get("keywords", [])
    summary = analysis.get("summary", "")

    kw_html = ''.join(
        f'<span style="display:inline-block;background:rgba(108,92,231,0.15);color:#a78bfa;padding:4px 12px;border-radius:20px;margin:3px;font-size:0.85rem;">{k["word"]} ({k["count"]})</span>'
        for k in keywords
    )

    body_html = f"""<h2>评论分析报告</h2>
<p>视频ID: {video_id} | 评论数: {data.get('total_fetched', 0)}</p>
<h3>情感分布</h3>
<table><tr><th>正面</th><th>中性</th><th>负面</th></tr>
<tr>
<td style="color:#00d68f;">{sentiment.get('positive', 0)}% ({sentiment.get('positive_count', 0)})</td>
<td style="color:#ffa502;">{sentiment.get('neutral', 0)}% ({sentiment.get('neutral_count', 0)})</td>
<td style="color:#ff6b6b;">{sentiment.get('negative', 0)}% ({sentiment.get('negative_count', 0)})</td>
</tr></table>
<h3>高频关键词</h3><div>{kw_html}</div>
<h3>AI 综合总结</h3><p>{summary}</p>"""

    return jsonify({"html": body_html, "title": f"评论分析_{video_id}"})


# ═══════════════════════════════════════════════════════════════
# Export API (PDF / Image via Playwright)
# ═══════════════════════════════════════════════════════════════

EXPORT_STYLE = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;min-height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#0f0f13;color:#e0e0e0;padding:36px 40px;line-height:1.8}
"""


@app.route("/api/export/pdf", methods=["POST"])
def export_pdf():
    body_html = request.json.get("html", "")
    title = request.json.get("title", "分析报告")
    if not body_html.strip():
        return jsonify({"error": "内容为空"}), 400

    html = _build_export_html(body_html, title)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 900, "height": 800})
            page.set_content(html, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(500)
            # Ensure full content is laid out before PDF
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(200)
            pdf_bytes = page.pdf(
                format="A4", print_background=True,
                margin={"top": "15mm", "bottom": "15mm", "left": "12mm", "right": "12mm"}
            )
            browser.close()

        import io
        return send_file(
            io.BytesIO(pdf_bytes), mimetype="application/pdf",
            as_attachment=True, download_name=f"{title}.pdf"
        )
    except Exception as e:
        return jsonify({"error": f"PDF 生成失败: {str(e)}"}), 500


@app.route("/api/export/image", methods=["POST"])
def export_image():
    body_html = request.json.get("html", "")
    title = request.json.get("title", "分析报告")
    if not body_html.strip():
        return jsonify({"error": "内容为空"}), 400

    html = _build_export_html(body_html, title)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 900, "height": 800})
            page.set_content(html, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(500)
            # Capture true full height
            height = page.evaluate("document.body.scrollHeight")
            page.set_viewport_size({"width": 900, "height": max(height + 60, 800)})
            page.wait_for_timeout(200)
            png_bytes = page.screenshot(full_page=True, type="png")
            browser.close()

        import io
        return send_file(
            io.BytesIO(png_bytes), mimetype="image/png",
            as_attachment=True, download_name=f"{title}.png"
        )
    except Exception as e:
        return jsonify({"error": f"图片生成失败: {str(e)}"}), 500


def _build_export_html(body_html, title):
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{title}</title>
<style>{EXPORT_STYLE}</style></head><body>{body_html}</body></html>"""


def _simple_md_to_html(text):
    """Basic markdown → HTML conversion."""
    import re
    lines = text.strip().split("\n")
    out = []
    in_list = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if s.startswith("### "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{s[4:]}</h3>")
        elif s.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h1>{s[2:]}</h1>")
        elif re.match(r"^[-*]\s", s):
            if not in_list: out.append("<ul>"); in_list = True
            txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s[2:])
            out.append(f"<li>{txt}</li>")
        elif re.match(r"^\d+[\.\)]\s", s):
            if in_list: out.append("</ul>"); in_list = False
            txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", re.sub(r"^\d+[\.\)]\s+", "", s))
            out.append(f"<p>{txt}</p>")
        else:
            if in_list: out.append("</ul>"); in_list = False
            txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            out.append(f"<p>{txt}</p>")
    if in_list: out.append("</ul>")
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════
# Format Conversion API
# ═══════════════════════════════════════════════════════════════

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "vibecoding_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route("/api/convert/pdf-to-ppt", methods=["POST"])
def api_pdf_to_ppt():
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "请上传 PDF 文件"})
    dpi = int(request.form.get("dpi", 200))
    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    try:
        result = pdf_to_ppt(path, dpi=dpi)
        return send_file(result, as_attachment=True, download_name=Path(result).name)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/convert/ppt-to-images", methods=["POST"])
def api_ppt_to_images():
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "请上传 PPTX 文件"})
    dpi = int(request.form.get("dpi", 200))
    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    try:
        result = ppt_to_images(path, dpi=dpi)
        return send_file(result, as_attachment=True, download_name=Path(result).name)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/convert/pdf-to-images", methods=["POST"])
def api_pdf_to_images():
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "请上传 PDF 文件"})
    dpi = int(request.form.get("dpi", 200))
    fmt = request.form.get("format", "PNG")
    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    try:
        result = pdf_to_images(path, dpi=dpi, fmt=fmt)
        return send_file(result, as_attachment=True, download_name=Path(result).name)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/convert/images-to-pdf", methods=["POST"])
def api_images_to_pdf():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"success": False, "error": "请上传图片"})
    paths = []
    for f in files:
        p = os.path.join(UPLOAD_DIR, f.filename)
        f.save(p)
        paths.append(p)
    try:
        result = images_to_pdf(paths)
        return send_file(result, as_attachment=True, download_name=Path(result).name)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# Background Removal API
# ═══════════════════════════════════════════════════════════════

@app.route("/api/bgremove", methods=["POST"])
def api_bg_remove():
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "请上传图片"})
    model_label = request.form.get("model", "Clipdrop API (云端高精)")
    alpha_matting = request.form.get("alpha_matting", "false") == "true"
    bg_color = request.form.get("bg_color", "transparent")
    feather = request.form.get("feather", "true") == "true"

    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    try:
        model_name = MODELS.get(model_label, "bria_rmbg")
        nobg, result = remove_background(
            path, model_name=model_name,
            alpha_matting=alpha_matting, bg_color=bg_color, feather=feather
        )
        return jsonify({
            "success": True,
            "result_url": f"/api/bgremove/download/{Path(result).name}",
            "credits": get_credits_info(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/bgremove/download/<filename>")
def serve_bgremove(filename):
    # Look in temp dir and parent dirs for the result file
    for root, _, files in os.walk(UPLOAD_DIR):
        if filename in files:
            return send_file(os.path.join(root, filename), mimetype="image/png")
    # Check parent of upload dir
    parent = Path(UPLOAD_DIR).parent
    for root, _, files in os.walk(parent):
        if filename in files:
            return send_file(os.path.join(root, filename), mimetype="image/png")
    return jsonify({"error": "文件不存在"}), 404


# ═══════════════════════════════════════════════════════════════
# Start
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"Vibecoding 启动中...")
    print(f"  访问地址: http://0.0.0.0:{PORT}")
    print(f"  下载目录: {DOWNLOAD_DIR}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG, threaded=True)
