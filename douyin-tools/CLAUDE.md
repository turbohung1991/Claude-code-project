# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 本地开发启动（自动检测端口7860，下载目录 ~/.vibecoding/downloads）
cd douyin-tools && python3 app.py

# 指定端口和调试模式
PORT=5002 DEBUG=1 python3 app.py

# 安装依赖
pip install -r requirements.txt

# Docker 构建与运行
docker build -t vibecoding . && docker run -p 7860:7860 vibecoding

# 推送到 GitHub（需使用正确的 SSH 密钥）
GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_turbohung1991 -o IdentitiesOnly=yes' git push origin main

# 推送到 HuggingFace Space（需要代理）
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push origin main
```

## 项目架构

- **Flask 单文件应用**：`app.py` 是主入口，约 900 行，路由、SSE、任务队列全部集中在其中。所有重型模块（playwright/rembg/onnxruntime）均为延迟导入，避免启动耗时。
- **SSE 任务通信**：前端通过 `/api/process` 创建任务获取 `task_id`，再连接 `/api/stream/<task_id>` 的 EventSource 流接收进度、错误和结果事件。每个任务有一个 `queue.Queue` 作为事件总线。
- **PDF/图片导出**：`/api/export/pdf` 和 `/api/export/image` 使用 Playwright headless Chromium 将 HTML 渲染为 PDF/PNG，HTML 由 `_build_export_html()` 包装。
- **下载目录**：`~/.vibecoding/downloads/`，视频和导出文件均在此处。`/api/download/<filename>` 直接从此目录提供文件。
- **上传目录**：`/tmp/vibecoding_uploads/`，转换和抠图的临时文件上传位置。处理完成后保留，由系统清理。

## 路由分类

| 类别 | 路由前缀 | 功能 |
|------|---------|------|
| 页面 | `/` `/convert` `/bgremove` `/batch` | 4个独立HTML页面 |
| 抖音核心 | `/api/parse` `/api/process` `/api/stream` | 链接解析 → 任务处理 → SSE推送 |
| 文件服务 | `/api/download` `/api/videos` `/api/analyses` | 下载/历史管理 |
| 文档转换 | `/api/convert/*` | PDF↔PPT↔图片互转 |
| 背景抠图 | `/api/bgremove` `/api/bgremove/config` | 抠图处理 + API Key密钥配置 |
| 评论分析 | `/api/comments/*` | 抓取、分析、导出评论数据 |
| 批量下载 | `/api/batch/*` | 多链接批量处理与状态管理 |
| 导出 | `/api/export/*` `/api/thumbnail/*` | PDF/图片导出、PDF首页缩略图 |

## 前端页面结构

每个页面独立，JavaScript 全为内联 `<script>` 或独立文件，不共享框架：

| 页面 | 模板 | JS | 职责 |
|------|------|----|------|
| 主页(抖音) | `index.html` | `static/app.js` (~1200行) | 抖音解析/下载/评论/策略分析 |
| 批量下载 | `batch.html` | `static/batch.js` | 多链接批量管理 |
| 文档转换 | `convert.html` | 内联 | 4种文档格式互转，拖拽上传+缩略图预览 |
| 一键抠图 | `bgremove.html` | 内联 | 多种模型去背景，含API Key配置面板 |

## 后端模块

- **`src/core.py`** — 抖音视频解析（链接检测、API调用、数据提取）
- **`src/strategy.py`** — DeepSeek AI 内容策略分析
- **`src/subtitle.py`** — faster-whisper 字幕提取
- **`src/downloader.py`** — 视频文件下载
- **`src/comment_analyzer.py`** — 评论抓取与情感分析
- **`src/batch_manager.py`** — 批量任务管理与并发控制
- **`converters/bg_remove.py`** — 抠图核心（rembg本地模型 + Clipdrop/remove.bg云端API）
- **`converters/pdf_to_ppt.py`** — PDF→PPTX（pdf2image + python-pptx）
- **`converters/pdf_to_images.py`** — PDF→图片ZIP
- **`converters/ppt_to_images.py`** — PPTX→图片ZIP（优先LibreOffice，回退到形状提取）
- **`converters/images_to_pdf.py`** — 多图片合并为PDF

## 关键常量

- 默认端口：`7860`（环境变量 `PORT` 覆盖）
- 下载目录：`~/.vibecoding/downloads/`
- 上传目录：`/tmp/vibecoding_uploads/`
- 抠图密钥文件：`~/.vibecoding/bgremove_keys.json`
- 历史分析文件：`~/.vibecoding/analyses.json`
- 默认AI模型：DeepSeek（通过 `openai` SDK 以兼容模式调用）

## 注意事项

- `/api/parse` 首次调用会触发 Playwright Chromium 自动安装（约300MB，仅一次）
- HuggingFace Space 部署用 Docker SDK，`Dockerfile` 中已包含中文字体、LibreOffice、poppler-utils 等依赖
- 批量下载的全局暂停/恢复通过 `batch_manager` 的状态管理实现，不直接操作 SSE 连接
- `.gitignore` 中排除了 `.claude/` 目录
