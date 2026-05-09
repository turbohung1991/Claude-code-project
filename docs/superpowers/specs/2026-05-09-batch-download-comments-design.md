# 抖音批量下载 & 评论分析 — 设计规格

> Date: 2026-05-09
> Status: approved

## 概述

在现有单视频下载分析工具基础上，新增**批量下载**和**评论抓取分析**两个独立功能模块。

## 架构

```
src/
├── core.py                  # + CommentFetcher (评论 API 抓取)
├── batch_manager.py         # 新增：批量队列管理
├── comment_analyzer.py      # 新增：评论抓取 + 情感/关键词/AI 分析
templates/
├── index.html               # 现有单视频页（不动）
├── batch.html               # 新增：批量下载页
├── convert.html             # 现有（不动）
├── bgremove.html            # 现有（不动）
static/
├── app.js                   # + 批量/评论相关的 JS
├── batch.js                 # 新增：批量页专属逻辑
```

## 批量下载

### 前端 (`/batch`)

- 多行输入框（一行一个抖音链接），提交后创建批量任务
- 任务队列视图：全局进度条 + 视频卡片列表
- 每个卡片独立展示：缩略图、标题、作者、独立进度条、状态标签
- 全局控制：暂停全部 / 继续全部
- 单项控制：重试、跳过
- 已完成视频可点击展开评论分析面板

### 后端 (`src/batch_manager.py`)

- `BatchManager` 类管理任务队列
- 串行下载，间隔 3 秒防限流
- 任务状态机：`queued → parsing → downloading → analyzing → done | error`
- 复用现有 `DouyinParser`、`VideoDownloader`、`SubtitleExtractor`、`StrategyAnalyzer`
- 下载前检查 `downloads/` 去重，跳过已存在文件
- 批量任务记录保存到 `downloads/batch_history.json`

### API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/batch/create` | POST | `{urls: string[]}` → `{batch_id, tasks: [{task_id, url, status}]}` |
| `/api/batch/status/<batch_id>` | GET | 返回队列整体状态和各 task 进度 |
| `/api/batch/pause` | POST | 暂停队列 |
| `/api/batch/resume` | POST | 恢复队列 |
| `/api/batch/retry/<task_id>` | POST | 重试单个失败任务 |
| `/api/stream/<task_id>` | GET | SSE 流（复用现有） |

## 评论抓取与分析

### 数据获取 (`src/core.py` — CommentFetcher)

- 通过 Douyin API 抓取评论
- 默认抓取：热评 200 条 + 最新 100 条
- 支持翻页：`GET /api/comments/load-more?video_id=xxx&cursor=xxx` 每次 +50 条
- 上限 500 条
- 字段：`nickname`, `content`, `digg_count`, `reply_count`, `create_time`

### 分析引擎 (`src/comment_analyzer.py`)

**情感分析**：使用 NLP 模型/词典对每条评论打分，输出正面/中性/负面三类分布。

**关键词提取**：TF-IDF + 停用词过滤，提取 Top 10 高频词。

**AI 综合总结**：调用现有 StrategyAnalyzer 的 OpenAI 客户端，输入：
- 评论数据摘要（情感分布、高频词）
- 代表性评论样本（高赞 + 极端情感）
- 输出：用户画像、核心观点、争议点、购买意向

### API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/comments/fetch` | POST | `{video_id}` → 触发抓取，返回 `task_id` |
| `/api/comments/load-more` | GET | `?video_id=xxx&cursor=xxx` → 分页数据 |
| `/api/comments/result/<video_id>` | GET | 返回抓取进度 + 分析结果 |
| `/api/comments/export/<video_id>` | GET | 导出评论分析为 PDF |

### 数据存储

- `downloads/<video>_comments.json`：抓取数据 + 分析结果
- 结构：

```json
{
  "video_id": "...",
  "fetched_at": 1715200000,
  "total_fetched": 350,
  "hot_comments": [{...}],
  "latest_comments": [{...}],
  "analysis": {
    "sentiment": {"positive": 45, "neutral": 30, "negative": 25},
    "keywords": ["词1", "词2", ...],
    "summary": "AI 综合总结文本"
  }
}
```

## 错误处理

- 批量下载中单任务失败不影响后续任务
- 评论抓取 API 限流时自动重试（最多 3 次，指数退避）
- 网络异常、链接失效给出明确错误信息展示在对应卡片上
- 评论抓取超时 30s，返回已抓取的部分数据而非全失败

## 测试要点

- 批量创建 5 个链接，验证逐个下载 + 间隔
- 重复链接去重测试
- 暂停/继续/重试状态机正确性
- 评论抓取 300 条 + 翻页加载
- 情感分析 + 关键词输出格式验证
- 单任务失败不阻塞队列
