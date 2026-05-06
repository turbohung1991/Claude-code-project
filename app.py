import gradio as gr
from converters.pdf_to_ppt import pdf_to_ppt
from converters.ppt_to_images import ppt_to_images
from converters.pdf_to_images import pdf_to_images
from converters.images_to_pdf import images_to_pdf
from converters.bg_remove import remove_background, MODELS, get_credits_info
from converters.douyin_download import download_video
from converters.subtitle_stt import extract_subtitles, PRESETS as STT_PRESETS
from converters.content_analyze import analyze_content, list_available_models, AVAILABLE_MODELS, DEFAULT_MODEL


# ── Handlers ──────────────────────────────────────────────

def handle_pdf_to_ppt(pdf_file, dpi):
    if pdf_file is None:
        return None
    return pdf_to_ppt(pdf_file.name, dpi=int(dpi))


def handle_ppt_to_images(ppt_file, dpi):
    if ppt_file is None:
        return None
    return ppt_to_images(ppt_file.name, dpi=int(dpi))


def handle_pdf_to_images(pdf_file, dpi, fmt):
    if pdf_file is None:
        return None
    return pdf_to_images(pdf_file.name, dpi=int(dpi), fmt=fmt)


def handle_images_to_pdf(image_files):
    if not image_files:
        return None
    return images_to_pdf([f.name for f in image_files])


def handle_bg_remove(image_file, model_label, alpha_matting, bg_color, feather):
    if image_file is None:
        return None, None, get_credits_info()
    model_name = MODELS[model_label]
    nobg, result = remove_background(
        image_file.name,
        model_name=model_name,
        alpha_matting=alpha_matting,
        bg_color=bg_color,
        feather=feather,
    )
    return result, nobg, get_credits_info()


def handle_douyin_download(url, preset, progress=gr.Progress()):
    if not url or not url.strip():
        return None, "", "请输入抖音链接", None
    try:
        progress(0.1, desc="正在获取视频信息...")
        info = download_video(url.strip(), cookie_file=None)
        progress(0.6, desc="正在语音识别字幕...")
        subtitle_text = extract_subtitles(info["file_path"], preset=preset)
        progress(1.0, desc="完成")
        summary = f"下载成功\n标题: {info['title']}\n时长: {int(info['duration'])}秒\n字幕: {len(subtitle_text.splitlines())} 行"
        return info["file_path"], subtitle_text, summary, info["file_path"]
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[ERROR] handle_douyin_download:\n{tb}", flush=True)
        return None, "", f"错误: {str(e)}\n\n{tb[-500:]}", None


def handle_content_analysis(subtitle_text, model_name):
    if not subtitle_text or not subtitle_text.strip():
        return "请先从「抖音下载」标签页提取字幕文本"
    if not model_name:
        return "请选择分析模型"
    return analyze_content(subtitle_text, model=model_name)


def get_analysis_models():
    models = list_available_models()
    if not models:
        return gr.update(choices=["(无可用模型)"], value="(无可用模型)")
    return gr.update(choices=models, value=models[0])


# ── CSS ───────────────────────────────────────────────────

PREMIUM_CSS = """
footer {display: none !important;}

body, .gradio-container {
    background: #f8f9fb !important;
}

.gradio-container {
    max-width: 1160px !important;
    margin: 0 auto !important;
    padding: 16px 20px !important;
}

/* Tabs */
.tabs { margin-top: 16px !important; border: none !important; background: transparent !important; }
.tab-nav {
    background: #fff !important;
    border-radius: 14px !important;
    padding: 6px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04) !important;
    gap: 2px !important;
    flex-wrap: wrap !important;
}
.tab-nav button {
    border-radius: 10px !important;
    padding: 10px 16px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: #5f6b7a !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.2s ease !important;
    margin: 0 !important;
}
.tab-nav button:hover { background: #f2f4f7 !important; color: #2d3748 !important; }
.tab-nav button.selected {
    background: #1a1a2e !important;
    color: #fff !important;
    box-shadow: 0 2px 8px rgba(26,26,46,0.25) !important;
}

/* Tab content */
.tabitem {
    background: #fff !important;
    border-radius: 14px !important;
    padding: 6px !important;
    margin-top: 8px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03), 0 8px 24px rgba(0,0,0,0.04) !important;
}

/* Section cards inside tabs */
.section-card {
    background: #fafbfc !important;
    border: 1px solid #edf0f4 !important;
    border-radius: 12px !important;
    padding: 20px !important;
    margin-bottom: 14px !important;
}

/* Inputs */
input, textarea, select, .file-preview {
    border-radius: 10px !important;
    border: 1.5px solid #e8ecf1 !important;
    background: #fafbfc !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    font-size: 14px !important;
}
input:focus, textarea:focus, select:focus {
    border-color: #6c5ce7 !important;
    box-shadow: 0 0 0 3px rgba(108,92,231,0.08) !important;
    outline: none !important;
}

label, .label-text {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #3a3f51 !important;
}

/* Primary button */
button.primary, .primary {
    background: linear-gradient(135deg, #1a1a2e 0%, #2d3561 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    color: #fff !important;
    letter-spacing: 0.02em !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 2px 8px rgba(26,26,46,0.2) !important;
}
button.primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(26,26,46,0.3) !important;
    background: linear-gradient(135deg, #2d3561 0%, #434e8a 100%) !important;
}

button.sm {
    border-radius: 8px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
    background: #f2f4f7 !important;
    border: 1px solid #e2e6ed !important;
    color: #5f6b7a !important;
}
button.sm:hover { background: #e8ecf1 !important; color: #2d3748 !important; }

.file-preview {
    border-radius: 10px !important;
    border: 1.5px dashed #d8dde6 !important;
    background: #fafbfc !important;
}

.slider input[type=range] { accent-color: #6c5ce7 !important; }

.video-container video { border-radius: 12px !important; }
.image-container img { border-radius: 12px !important; }

textarea[data-testid="textbox"] {
    scrollbar-width: thin !important;
    scrollbar-color: #c8cdd6 #f2f4f7 !important;
}
textarea[data-testid="textbox"]::-webkit-scrollbar { width: 6px !important; }
textarea[data-testid="textbox"]::-webkit-scrollbar-track { background: #f2f4f7 !important; border-radius: 8px !important; }
textarea[data-testid="textbox"]::-webkit-scrollbar-thumb { background: #c8cdd6 !important; border-radius: 8px !important; }
textarea[data-testid="textbox"]::-webkit-scrollbar-thumb:hover { background: #a0a8b4 !important; }

.credits-info textarea {
    font-size: 12px !important;
    color: #6b7280 !important;
    padding: 4px 10px !important;
    min-height: 28px !important;
    background: #f8f9fb !important;
    border-radius: 6px !important;
    border: 1px solid #e8ecf1 !important;
}

/* Convert-type radio — pill selector */
.convert-radio {
    margin-bottom: 20px !important;
}
.convert-radio .wrap {
    display: flex !important;
    gap: 8px !important;
    flex-wrap: wrap !important;
}
.convert-radio label {
    display: inline-flex !important;
    align-items: center !important;
    padding: 10px 20px !important;
    border-radius: 10px !important;
    border: 1.5px solid #e2e6ed !important;
    background: #fff !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #5f6b7a !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}
.convert-radio label:hover {
    border-color: #6c5ce7 !important;
    background: #f8f7ff !important;
}
.convert-radio label.selected {
    background: #1a1a2e !important;
    border-color: #1a1a2e !important;
    color: #fff !important;
    box-shadow: 0 2px 8px rgba(26,26,46,0.25) !important;
}
.convert-radio input[type="radio"] {
    display: none !important;
}

/* Section icon headers */
.section-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    margin-right: 10px;
    font-size: 16px;
    flex-shrink: 0;
}
"""

HEADER_HTML = """
<div style="text-align:center; padding:32px 0 20px 0;">
    <h1 style="margin:0; font-size:2.1em; font-weight:700; color:#1a1a2e; letter-spacing:-0.02em;">
        格式转换工具箱
    </h1>
    <p style="color:#98a0b0; margin:10px 0 0 0; font-size:0.95em; font-weight:400;">
        格式转换 · 智能抠图 · 抖音下载 · 内容分析
    </p>
</div>
"""



# ── UI ────────────────────────────────────────────────────

with gr.Blocks(
    title="格式转换工具箱",
    theme=gr.themes.Soft(
        primary_hue="slate",
        secondary_hue="slate",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),
        spacing_size="sm",
    ),
    css=PREMIUM_CSS,
) as app:
    gr.HTML(HEADER_HTML)

    with gr.Tabs():
        # ════════════════════════════════════════════════════
        # Tab 1: 一键转换
        # ════════════════════════════════════════════════════
        with gr.Tab("一键转换"):
            convert_type = gr.Radio(
                choices=["PDF → PPT", "PPT → 图片", "PDF → 图片", "图片 → PDF", "智能抠图"],
                value="PDF → PPT",
                label="选择转换类型",
                interactive=True,
                elem_classes=["convert-radio"],
            )

            # ── PDF → PPT ──
            with gr.Column(visible=True) as panel_1:
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        pdf_input_1 = gr.File(label="上传 PDF 文件", file_types=[".pdf"])
                        dpi_1 = gr.Slider(72, 300, value=200, step=10, label="清晰度 (DPI)")
                        btn_1 = gr.Button("转换为 PPTX", variant="primary")
                    with gr.Column(scale=1):
                        ppt_output = gr.File(label="下载 PPTX")

            # ── PPT → 图片 ──
            with gr.Column(visible=False) as panel_2:
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        ppt_input = gr.File(label="上传 PPTX 文件", file_types=[".pptx"])
                        dpi_2 = gr.Slider(72, 300, value=200, step=10, label="清晰度 (DPI)")
                        btn_2 = gr.Button("转换为图片 ZIP", variant="primary")
                    with gr.Column(scale=1):
                        images_zip_output = gr.File(label="下载图片 ZIP")

            # ── PDF → 图片 ──
            with gr.Column(visible=False) as panel_3:
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        pdf_input_2 = gr.File(label="上传 PDF 文件", file_types=[".pdf"])
                        with gr.Row():
                            dpi_3 = gr.Slider(72, 300, value=200, step=10, label="清晰度 (DPI)", scale=1)
                            fmt_3 = gr.Dropdown(["PNG", "JPEG"], value="PNG", label="格式", scale=1)
                        btn_3 = gr.Button("转换为图片 ZIP", variant="primary")
                    with gr.Column(scale=1):
                        pdf_images_zip = gr.File(label="下载图片 ZIP")

            # ── 图片 → PDF ──
            with gr.Column(visible=False) as panel_4:
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        images_input = gr.File(label="上传多张图片", file_types=["image"], file_count="multiple")
                        btn_4 = gr.Button("合并为 PDF", variant="primary")
                    with gr.Column(scale=1):
                        combined_pdf = gr.File(label="下载 PDF")

            # ── 智能抠图 ──
            with gr.Column(visible=False) as panel_5:
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        bg_input = gr.File(label="上传图片", file_types=["image"])
                        bg_model = gr.Dropdown(
                            list(MODELS.keys()), value="Clipdrop API (云端高精)", label="模型选择"
                        )
                        bg_credits = gr.Textbox(
                            value=get_credits_info(), label="API 额度", interactive=False, lines=1,
                            elem_classes=["credits-info"],
                        )
                        with gr.Row():
                            bg_alpha = gr.Checkbox(value=False, label="Alpha Matting", scale=1)
                            bg_feather = gr.Checkbox(value=True, label="边缘羽化", scale=1)
                        bg_color = gr.Dropdown(
                            ["transparent", "#FFFFFF", "#000000", "#FF0000", "#00FF00", "#0000FF"],
                            value="transparent", label="替换背景色"
                        )
                        btn_5 = gr.Button("去除背景", variant="primary")
                    with gr.Column(scale=1):
                        bg_output_img = gr.Image(label="处理后预览", type="filepath")
                        bg_output_dl = gr.File(label="下载 PNG")

            # Panel visibility switch
            panels = [panel_1, panel_2, panel_3, panel_4, panel_5]
            panels_map = {
                "PDF → PPT": panel_1, "PPT → 图片": panel_2,
                "PDF → 图片": panel_3, "图片 → PDF": panel_4,
                "智能抠图": panel_5,
            }

            def switch_panel(choice):
                return [gr.update(visible=(p == panels_map[choice])) for p in panels]

            convert_type.change(
                fn=switch_panel, inputs=[convert_type],
                outputs=panels,
            )

            # Event bindings
            btn_1.click(fn=handle_pdf_to_ppt, inputs=[pdf_input_1, dpi_1], outputs=ppt_output)
            btn_2.click(fn=handle_ppt_to_images, inputs=[ppt_input, dpi_2], outputs=images_zip_output)
            btn_3.click(fn=handle_pdf_to_images, inputs=[pdf_input_2, dpi_3, fmt_3], outputs=pdf_images_zip)
            btn_4.click(fn=handle_images_to_pdf, inputs=images_input, outputs=combined_pdf)
            btn_5.click(
                fn=handle_bg_remove,
                inputs=[bg_input, bg_model, bg_alpha, bg_color, bg_feather],
                outputs=[bg_output_img, bg_output_dl, bg_credits],
            )

        # ════════════════════════════════════════════════════
        # Tab 2: 抖音下载
        # ════════════════════════════════════════════════════
        with gr.Tab("抖音下载"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=2, min_width=280):
                    dy_url = gr.Textbox(
                        label="抖音链接", placeholder="粘贴抖音分享链接...", lines=1,
                    )
                    with gr.Row():
                        dy_preset = gr.Dropdown(
                            choices=list(STT_PRESETS.keys()),
                            value="default",
                            label="识别模式",
                            info="fast=最快 | default=均衡 | best=最准",
                            scale=2,
                        )
                        btn_7 = gr.Button("下载并提取字幕", variant="primary", scale=1)
                    dy_status = gr.Textbox(label="下载状态", lines=2, interactive=False)
                    dy_video = gr.Video(label="视频预览")
                with gr.Column(scale=3, min_width=320):
                    dy_subtitle_text = gr.Textbox(
                        label="提取的字幕文本", lines=22, max_lines=22,
                        placeholder="字幕内容将显示在这里...",
                        elem_classes=["subtitle-scroll"],
                    )
                    dy_video_dl = gr.File(label="下载视频文件", visible=False)

            btn_7.click(
                fn=handle_douyin_download,
                inputs=[dy_url, dy_preset],
                outputs=[dy_video, dy_subtitle_text, dy_status, dy_video_dl],
            )

        # ════════════════════════════════════════════════════
        # Tab 3: 内容分析
        # ════════════════════════════════════════════════════
        with gr.Tab("内容分析"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=1, min_width=280):
                    ca_models = gr.Dropdown(
                        choices=AVAILABLE_MODELS, value=DEFAULT_MODEL,
                        label="分析模型", info="DashScope AI 模型",
                    )
                    ca_refresh_btn = gr.Button("刷新模型", size="sm")
                    ca_text = gr.Textbox(
                        label="字幕文本", lines=18, max_lines=18,
                        placeholder="粘贴字幕文本，或先在「抖音下载」页提取...",
                        elem_classes=["subtitle-scroll"],
                    )
                    btn_8 = gr.Button("分析内容策略", variant="primary")
                with gr.Column(scale=1, min_width=320):
                    ca_output = gr.HTML(value="""
<div style="color:#98a0b0; text-align:center; padding:60px 20px; font-size:0.95em;">
等待分析...
</div>""")

            ca_refresh_btn.click(fn=get_analysis_models, inputs=[], outputs=[ca_models])
            btn_8.click(
                fn=handle_content_analysis,
                inputs=[ca_text, ca_models],
                outputs=[ca_output],
            )

    # Cross-tab: auto-fill subtitle into content analysis
    dy_subtitle_text.change(fn=lambda s: s, inputs=[dy_subtitle_text], outputs=[ca_text])


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
