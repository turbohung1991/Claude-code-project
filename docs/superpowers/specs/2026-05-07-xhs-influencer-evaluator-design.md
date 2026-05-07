# 小红书达人评估系统 — 设计文档

## Overview

独立 Flask Web 应用，输入小红书达人 ID 或昵称，自动爬取达人数据，通过 DeepSeek AI 进行 7 维评估，输出品牌契合度报告。品牌方：LAN兰（国货纯净护肤）。

## Tech Stack

| 组件 | 用途 |
|------|------|
| Flask | Web 框架 |
| Playwright | 浏览器自动化爬虫（绕过小红书反爬） |
| DeepSeek API (openai SDK) | AI 多维度评估引擎 |
| SVG | 雷达图渲染 |
| HTML/CSS | 暗色主题前端 |

## System Architecture

```
xiaohongshu-evaluator/
├── app.py              # Flask 主应用
├── xhs_crawler.py      # 小红书爬虫（Playwright）
├── brand_profile.json  # LAN兰品牌画像配置
├── evaluator.py        # AI 评估引擎（DeepSeek）
├── requirements.txt
├── static/style.css    # 暗色主题
└── templates/
    ├── index.html      # 搜索页
    └── report.html     # 评估报告页
```

## Core Flow

1. 用户输入达人 ID/昵称 → 搜索页
2. Playwright 爬取小红书达人数据
3. DeepSeek API 7 维评估 + 品牌契合度分析
4. 报告页展示：达人信息卡 + 雷达图 + 维度详情 + 导出

## Data Model

```
XHS_Influencer:
├── 基础信息: ID, 昵称, 头像, 简介, 认证类型, 粉丝数
├── 内容数据: 笔记数, 近30天发布数, 平均点赞/收藏/评论, 互动率
├── 粉丝画像: 性别比, 年龄分布, 地域分布, 兴趣标签
├── 商业数据: 历史合作品牌, 报价区间, 笔记互动趋势
├── 内容风格: 出镜方式, 文案调性, 常用话题标签, 视觉风格
└── 风险标记: 负面舆情, 虚假数据嫌疑, 平台违规记录
```

## 7 Evaluation Dimensions

| 维度 | 权重 | 说明 |
|------|------|------|
| 基础数据 | 15% | 粉丝增长、互动率、数据质量 |
| 内容调性 | 20% | 视觉风格、文案质感、品牌调性匹配 |
| 粉丝画像 | 15% | 年龄/地域/消费力与LAN兰客群重叠度 |
| 商业价值 | 15% | 历史合作、转化率、报价合理性 |
| 品牌契合 | 20% | 达人理念与LAN兰"愈肤愈心"的共鸣度 |
| 风险审查 | 10% | 负面舆情、虚假数据、合规记录 |
| 增长潜力 | 5% | 粉丝增速、内容进化趋势、中长期价值 |

输出：综合契合度评分 0-100 + 推荐等级 (S/A/B/C/D)

## UI Design

### 搜索页
- 居中品牌标题（渐变紫色）+ 搜索框 + 开始评估按钮
- 支持达人 ID、昵称、主页链接输入
- 评估中显示进度动画（4 步骤徽章）

### 报告页
- **顶部**：达人信息卡（头像/粉丝/笔记/互动率）+ 操作按钮（返回/导出PDF/分享）+ 综合评分（环形图 + 推荐等级）
- **中部**：左右 50/50 布局 — 左侧正七边形雷达图（SVG），深灰标签，彩色数据点；右侧 7 维度进度条卡片（含分析结论）
- **底部**：分析结论卡片网格
- 暗色主题 (#0f0f13 背景, #1a1a24 卡片, #6c5ce7 强调色)

## Deployment

- Hugging Face Spaces (Flask SDK)
- 环境变量: DEEPSEEK_API_KEY
- Playwright Chromium 自动安装

## Verification

1. 启动 Flask 应用，访问搜索页
2. 输入真实小红书达人链接，点击评估
3. 验证 Playwright 成功爬取数据
4. 验证 DeepSeek 返回 7 维分析结果
5. 验证雷达图正七边形渲染正确
6. 验证 PDF 导出完整
7. 验证历史记录查询和删除功能
