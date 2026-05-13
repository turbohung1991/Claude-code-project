# 抖音批量下载 & 评论分析 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add batch multi-URL download queue and comment scraping + sentiment/keyword/AI analysis to the existing Douyin Flask app.

**Architecture:** New `BatchManager` class handles serial queued downloads with pause/resume. New `CommentAnalyzer` class fetches comments via Playwright-intercept API and runs sentiment + keyword + AI analysis. Both exposed via new REST/SSE routes in app.py, driven by a new `/batch` page.

**Tech Stack:** Flask, SSE, Playwright (async), OpenAI SDK, vanilla JS (no framework)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/batch_manager.py` | Create | BatchManager — serial queue, pause/resume, retry, dedup |
| `src/comment_analyzer.py` | Create | CommentAnalyzer — fetch, sentiment, keywords, AI summary |
| `src/core.py` | Modify | Add `CommentFetcher` class for Douyin comment API via Playwright |
| `templates/batch.html` | Create | Batch download page UI |
| `static/batch.js` | Create | Batch page frontend logic |
| `static/style.css` | Modify | Batch page styles |
| `app.py` | Modify | New routes: batch page, batch API, comment API |

---

### Task 1: Add CommentFetcher to `src/core.py`

**Files:**
- Modify: `src/core.py`

- [ ] **Step 1: Add CommentFetcher class after DouyinParser**

Add at the end of `src/core.py`:

```python
# ================================================================
# 评论抓取器
# ================================================================

class CommentFetcher:
    """抖音评论抓取器 — 基于 Playwright API 拦截"""

    @classmethod
    async def fetch_comments(
        cls, video_id: str, max_hot: int = 200, max_latest: int = 100
    ) -> Dict:
        """
        抓取评论。

        Returns:
            {
                'video_id': str,
                'hot_comments': List[Dict],
                'latest_comments': List[Dict],
                'total_fetched': int,
                'cursor': int,        # 下一页游标，用于 load_more
                'has_more': bool,
            }
        """
        result = {
            'video_id': video_id,
            'hot_comments': [],
            'latest_comments': [],
            'total_fetched': 0,
            'cursor': 0,
            'has_more': False,
        }

        pw, browser = await DouyinParser._launch_browser()
        try:
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                    'Version/16.0 Mobile/15E148 Safari/604.1'
                ),
                viewport={'width': 390, 'height': 844},
                locale='zh-CN',
            )
            page = await context.new_page()

            comments_data = []

            async def on_response(resp):
                nonlocal comments_data
                url = resp.url
                if 'comment/list' in url and not comments_data:
                    try:
                        body = await resp.json()
                        if body.get('comments') or body.get('comment_list'):
                            comments_data.append(body)
                    except Exception:
                        pass

            page.on('response', on_response)

            # 访问视频页面触发评论 API
            await page.goto(
                'https://www.douyin.com/', wait_until='domcontentloaded', timeout=20000
            )
            await page.wait_for_timeout(2000)

            video_url = f'https://www.douyin.com/video/{video_id}'
            await page.goto(video_url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(3000)

            # 滚动触发加载更多评论
            for _ in range(3):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(1500)

            # 如果通过 API 拦截拿到了数据
            if comments_data:
                data = comments_data[0]
                raw_comments = (
                    data.get('comments', []) or
                    data.get('comment_list', []) or
                    data.get('data', {}).get('comments', [])
                )

                hot, latest = [], []
                for c in raw_comments:
                    item = cls._normalize_comment(c)
                    if not item['content']:
                        continue
                    if c.get('is_hot') or c.get('is_hot_comment'):
                        hot.append(item)
                    else:
                        latest.append(item)

                # 热评补足或截断
                hot = hot[:max_hot]
                latest = latest[:max_latest]

                result['hot_comments'] = hot
                result['latest_comments'] = latest
                result['total_fetched'] = len(hot) + len(latest)
                if latest:
                    result['cursor'] = latest[-1].get('create_time', 0)
                    result['has_more'] = len(latest) >= max_latest

            await context.close()
        finally:
            await browser.close()
            await pw.stop()

        return result

    @classmethod
    async def load_more(cls, video_id: str, cursor: int, count: int = 50) -> Dict:
        """翻页加载更多评论"""
        # More comments require directly calling the API with cursor
        # Using the same Playwright interception approach
        result = {
            'comments': [],
            'cursor': cursor,
            'has_more': False,
        }

        pw, browser = await DouyinParser._launch_browser()
        try:
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                    'Version/16.0 Mobile/15E148 Safari/604.1'
                ),
                viewport={'width': 390, 'height': 844},
                locale='zh-CN',
            )
            page = await context.new_page()

            captured = []

            async def on_response(resp):
                if 'comment/list' in resp.url and not captured:
                    try:
                        body = await resp.json()
                        captured.append(body)
                    except Exception:
                        pass

            page.on('response', on_response)

            # Navigate with cursor parameter (will be picked up by page JS)
            api_url = (
                f'https://www.douyin.com/aweme/v1/web/comment/list/'
                f'?aweme_id={video_id}&cursor={cursor}&count={count}&item_type=0'
            )
            await page.goto(api_url, wait_until='domcontentloaded', timeout=15000)
            await page.wait_for_timeout(3000)

            if captured:
                data = captured[0]
                raw = (
                    data.get('comments', []) or
                    data.get('comment_list', []) or
                    data.get('data', {}).get('comments', [])
                )
                result['comments'] = [
                    cls._normalize_comment(c) for c in raw if cls._normalize_comment(c)['content']
                ]
                result['cursor'] = data.get('cursor', 0)
                result['has_more'] = data.get('has_more', 0) == 1

            await context.close()
        finally:
            await browser.close()
            await pw.stop()

        return result

    @staticmethod
    def _normalize_comment(c: Dict) -> Dict:
        """统一评论字段格式"""
        user = c.get('user', {}) or {}
        return {
            'cid': c.get('cid', ''),
            'nickname': user.get('nickname', '匿名'),
            'avatar': user.get('avatar_thumb', {}).get('url_list', [''])[0] or '',
            'content': (c.get('text', '') or c.get('content', '')).strip(),
            'digg_count': c.get('digg_count', 0) or 0,
            'reply_count': c.get('reply_comment_total', 0) or 0,
            'create_time': c.get('create_time', 0) or 0,
            'is_hot': bool(
                c.get('is_hot') or
                c.get('is_hot_comment') or
                c.get('label_type') or
                (c.get('digg_count', 0) >= 100)
            ),
        }
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import sys; sys.path.insert(0, '.'); from src.core import CommentFetcher; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add src/core.py
git commit -m "feat: add CommentFetcher class for Douyin comment API scraping"
```

---

### Task 2: Create `src/batch_manager.py`

**Files:**
- Create: `src/batch_manager.py`

- [ ] **Step 1: Write BatchManager class**

Create `src/batch_manager.py`:

```python
"""
批量任务管理器
串行下载队列，支持暂停/继续/重试/去重
"""

import os
import time
import threading
import asyncio
from queue import Queue
from typing import Dict, List, Optional
from pathlib import Path
from urllib.parse import quote


DOWNLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads'
)


class BatchManager:
    """批量下载队列管理器"""

    def __init__(self):
        self.batches: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def create_batch(self, urls: List[str]) -> str:
        """创建批量任务，返回 batch_id"""
        import uuid
        batch_id = str(uuid.uuid4())[:8]

        tasks = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            task_id = str(uuid.uuid4())[:8]
            tasks.append({
                'task_id': task_id,
                'url': url,
                'status': 'queued',
                'queue': Queue(),
                'result': {},
                'error': None,
            })

        batch = {
            'batch_id': batch_id,
            'tasks': tasks,
            'status': 'queued',  # queued | running | paused | done
            'paused': False,
            'thread': None,
            'interval': 3,  # seconds between tasks
        }

        with self._lock:
            self.batches[batch_id] = batch

        return batch_id

    def start(self, batch_id: str):
        """启动批量处理（异步线程）"""
        batch = self.batches.get(batch_id)
        if not batch:
            return

        batch['status'] = 'running'
        thread = threading.Thread(target=self._run, args=(batch_id,), daemon=True)
        batch['thread'] = thread
        thread.start()

    def pause(self, batch_id: str):
        batch = self.batches.get(batch_id)
        if batch:
            batch['paused'] = True
            batch['status'] = 'paused'

    def resume(self, batch_id: str):
        batch = self.batches.get(batch_id)
        if batch:
            batch['paused'] = False
            batch['status'] = 'running'

    def retry_task(self, batch_id: str, task_id: str):
        """重试单个失败任务"""
        batch = self.batches.get(batch_id)
        if not batch:
            return
        for task in batch['tasks']:
            if task['task_id'] == task_id and task['status'] == 'error':
                task['status'] = 'queued'
                task['error'] = None
                # Run in background
                threading.Thread(
                    target=self._process_one, args=(batch_id, task), daemon=True
                ).start()
                break

    def get_status(self, batch_id: str) -> Optional[Dict]:
        """获取批量任务整体状态"""
        batch = self.batches.get(batch_id)
        if not batch:
            return None

        tasks_status = []
        for t in batch['tasks']:
            tasks_status.append({
                'task_id': t['task_id'],
                'url': t['url'],
                'status': t['status'],
                'error': t.get('error'),
                'result': {
                    k: v for k, v in t['result'].items()
                    if k != 'queue'
                } if t['result'] else None,
            })

        done = sum(1 for t in batch['tasks'] if t['status'] == 'done')
        total = len(batch['tasks'])

        return {
            'batch_id': batch['batch_id'],
            'status': batch['status'],
            'progress': {
                'done': done,
                'total': total,
                'percent': int(done * 100 / total) if total > 0 else 0,
            },
            'tasks': tasks_status,
        }

    def _run(self, batch_id: str):
        """串行执行队列中的所有任务"""
        batch = self.batches.get(batch_id)
        if not batch:
            return

        for task in batch['tasks']:
            if batch['paused']:
                # Wait until resumed
                while batch['paused']:
                    time.sleep(1)
                    if batch_id not in self.batches:
                        return

            if task['status'] in ('done', 'error'):
                continue

            self._process_one(batch_id, task)

            # Interval between tasks
            if task != batch['tasks'][-1]:
                time.sleep(batch['interval'])

        # Check if all done
        all_done = all(
            t['status'] in ('done', 'error', 'skipped')
            for t in batch['tasks']
        )
        if all_done:
            batch['status'] = 'done'

    def _process_one(self, batch_id: str, task: Dict):
        """处理单个任务"""
        batch = self.batches.get(batch_id)
        if not batch:
            return

        from src.core import DouyinParser
        from src.downloader import VideoDownloader
        from src.subtitle import SubtitleExtractor
        from src.strategy import StrategyAnalyzer

        q = task['queue']

        def push(event_type, data):
            q.put({'event': event_type, 'data': data})

        try:
            url = task['url']

            # -- Parse --
            push('progress', {'step': 'parse', 'message': '正在解析...', 'percent': 0})
            link_type = DouyinParser.detect_link_type(url)
            video_id = asyncio.run(DouyinParser.parse_url(url))
            if not video_id:
                push('error', {'message': f'链接解析失败'})
                task['status'] = 'error'
                task['error'] = '链接解析失败'
                return

            # -- Get info --
            push('progress', {'step': 'parse', 'message': '获取视频信息...', 'percent': 10})
            video_data = asyncio.run(DouyinParser.get_video_info(video_id))
            if not video_data:
                push('error', {'message': '无法获取视频信息'})
                task['status'] = 'error'
                task['error'] = '无法获取视频信息'
                return

            desc = video_data.get('desc', video_id)
            author = video_data.get('author', {}).get('nickname', '未知')
            cover = (
                video_data.get('video', {}).get('cover', {}).get('url_list', [''])[0] or
                video_data.get('video', {}).get('origin_cover', {}).get('url_list', [''])[0] or ''
            )

            push('meta', {
                'video_id': video_id,
                'desc': desc[:100],
                'author': author,
                'cover': cover,
            })

            # -- Download --
            push('progress', {'step': 'download', 'message': '下载中...', 'percent': 20})

            # Build filename
            filename = desc[:30]
            for ch in '#?&= ，。！？、；：""''【】《》\t\n\r':
                filename = filename.replace(ch, '_')
            filename = filename.replace('/', '_').replace('\\', '_').strip() or video_id

            # Check duplicate
            download_path = os.path.join(DOWNLOAD_DIR, f'{filename}.mp4')
            if os.path.exists(download_path):
                push('progress', {
                    'step': 'download',
                    'message': '已存在，跳过下载',
                    'percent': 45,
                })
                push('video_ready', {
                    'filename': f'{filename}.mp4',
                    'size': os.path.getsize(download_path),
                    'size_display': f"{os.path.getsize(download_path)/1024/1024:.1f}MB",
                    'quality': '已缓存',
                    'url': f'/api/download/{quote(f"{filename}.mp4", safe="")}',
                    'skipped': True,
                })
            else:
                # Download
                quality_options = DouyinParser.parse_quality_options(video_data)
                if not quality_options:
                    play_addr = (
                        video_data.get('video', {}).get('play_addr', {}) or
                        video_data.get('video', {}).get('playAddr', {})
                    )
                    url_list = play_addr.get('url_list', []) or play_addr.get('urlList', [])
                    quality_options = [{
                        'label': '默认', 'gear_name': 'default', 'bit_rate': 0,
                        'url': url_list[0] if url_list else '',
                        'url_list': url_list,
                    }]

                selected = quality_options[0]  # Default to best quality
                video_url = selected.get('url') or selected.get('url_list', [''])[0]

                if not video_url:
                    push('error', {'message': '无法获取下载地址'})
                    task['status'] = 'error'
                    task['error'] = '无法获取下载地址'
                    return

                import requests as req
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
                    'Referer': 'https://www.douyin.com/',
                }
                resp = req.get(video_url, headers=headers, stream=True, timeout=120)
                resp.raise_for_status()
                total_size = int(resp.headers.get('content-length', 0))
                downloaded = 0

                with open(download_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = 20 + int(downloaded * 25 / total_size)
                                push('progress', {
                                    'step': 'download',
                                    'message': f'{downloaded//1024//1024}MB/{total_size//1024//1024}MB',
                                    'percent': min(pct, 45),
                                })

                file_size = os.path.getsize(download_path)
                push('video_ready', {
                    'filename': f'{filename}.mp4',
                    'size': file_size,
                    'size_display': f'{file_size/1024/1024:.1f}MB',
                    'quality': selected['label'],
                    'url': f'/api/download/{quote(f"{filename}.mp4", safe="")}',
                })

            # -- Subtitle --
            push('progress', {'step': 'subtitle', 'message': '提取字幕...', 'percent': 50})
            extractor = SubtitleExtractor(output_dir=DOWNLOAD_DIR)
            subtitle_result = extractor.extract(video_data, download_path)
            push('subtitle_ready', {
                'text': subtitle_result.get('text', '')[:500],
                'source': subtitle_result.get('source', 'none'),
            })
            push('progress', {'step': 'done', 'message': '完成', 'percent': 100})

            # Store result
            task['result'] = {
                'video_id': video_id,
                'desc': desc[:100],
                'author': author,
                'filename': f'{filename}.mp4',
                'subtitle_text': subtitle_result.get('text', ''),
            }

            push('complete', {'message': '处理完成'})
            task['status'] = 'done'

        except Exception as e:
            task['status'] = 'error'
            task['error'] = str(e)
            push('error', {'message': f'处理失败: {str(e)}'})

    def cleanup(self, batch_id: str):
        """清理已完成的任务"""
        if batch_id in self.batches:
            del self.batches[batch_id]


# Global singleton
batch_manager = BatchManager()
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import sys; sys.path.insert(0, '.'); from src.batch_manager import batch_manager; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add src/batch_manager.py
git commit -m "feat: add BatchManager for serial queue download"
```

---

### Task 3: Create `src/comment_analyzer.py`

**Files:**
- Create: `src/comment_analyzer.py`

- [ ] **Step 1: Write CommentAnalyzer class**

Create `src/comment_analyzer.py`:

```python
"""
评论分析模块
情感分析 + 关键词提取 + AI 综合总结
"""

import json
import os
import re
import asyncio
from typing import Dict, List, Optional
from openai import OpenAI

# 中文停用词（精简版）
STOP_WORDS = set(
    '的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 '
    '会 着 没有 看 好 自己 这 他 她 它 们 那 些 所 为 所以 因为 但是 '
    '可以 这个 那个 什么 怎么 如果 虽然 然而 而且 还是 只是 并 再 '
    '更 最 太 呀 吧 呢 吗 啊 哦 嗯 哈 嘛 啦 哇 哟 过 被 把 让 给 '
    '又 才 还 又 没 只 但 或 与 及 对 从 中 等 个 已 已经 能 能够 '
    '应该 需要 可能 其实 感觉 觉得 知道 真的 特别 比较 非常 一定 '
    '太 挺 蛮 超 级 简直 完全 根本 丝毫 从未 曾经 终于 然而 到底 '
    '究竟 居然 明显 当然 自然 必然 或许 大概 也许 尤其 确实 的确 '
    '真 假 好 坏 棒 差 行 不行 厉害 牛 绝 赞 顶 踩 爱 恨 喜欢 '
    '讨厌 可爱 帅 美 丑 丑恶 善良 邪恶 聪明 笨 好棒 好厉害 牛逼 '
    'yyds 绝绝子'.split()
)

# 情感词典
POSITIVE_WORDS = set(
    '好 棒 赞 爱 喜欢 厉害 牛 绝 顶 美 帅 可爱 优秀 完美 精彩 '
    '支持 加油 期待 好看 不错 可以 行 真不错 真好 太好了 棒极了 '
    'yyds 绝绝子 爱了 点赞 赞赞赞 好评 五星 推荐 值得 买 买了 '
    '不错 不错哦 可以的 挺好的 相当不错 非常棒 太棒了 真棒 给力 '
    '靠谱 实用 有用 学到了 收藏 转发了 已关注 粉了 种草 入手了 '
    '牛啊 6 六六六 太强了 大神 高手 专业的 真好用 超值'.split()
)

NEGATIVE_WORDS = set(
    '差 烂 坏 丑 讨厌 恨 垃圾 骗子 假的 不行 不好 太差 差劲 '
    '失望 无语 恶心 吐了 坑 骗人 假货 浪费 没用 后悔 千万别买 '
    '避雷 踩雷 差评 别买 不值 智商税 辣鸡 什么玩意 翻车 呵呵 '
    '就这 不过如此 一般 一般般 凑合'.split()
)


class CommentAnalyzer:
    """评论分析器"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        from src.strategy import StrategyAnalyzer
        # Reuse same client init logic as StrategyAnalyzer
        temp = StrategyAnalyzer(api_key=api_key, base_url=base_url)
        self.api_key = temp.api_key
        self.base_url = temp.base_url
        self.client = temp.client

    def fetch_and_analyze(
        self, video_id: str, max_hot: int = 200, max_latest: int = 100
    ) -> Dict:
        """一站式：抓取 + 分析"""
        from src.core import CommentFetcher

        # Fetch
        raw = asyncio.run(
            CommentFetcher.fetch_comments(video_id, max_hot, max_latest)
        )

        all_comments = raw['hot_comments'] + raw['latest_comments']
        if not all_comments:
            return {
                'video_id': video_id,
                'total_fetched': 0,
                'hot_comments': [],
                'latest_comments': [],
                'analysis': {
                    'sentiment': {'positive': 0, 'neutral': 0, 'negative': 0},
                    'keywords': [],
                    'summary': '暂无评论数据',
                },
                'cursor': 0,
                'has_more': False,
            }

        # Analyze
        sentiment = self._sentiment_analysis(all_comments)
        keywords = self._extract_keywords(all_comments)
        summary = self._ai_summary(all_comments, sentiment, keywords)

        return {
            'video_id': video_id,
            'total_fetched': len(all_comments),
            'hot_comments': raw['hot_comments'],
            'latest_comments': raw['latest_comments'],
            'analysis': {
                'sentiment': sentiment,
                'keywords': keywords,
                'summary': summary,
            },
            'cursor': raw['cursor'],
            'has_more': raw['has_more'],
        }

    def load_more_and_analyze(
        self, video_id: str, cursor: int, existing: Dict, count: int = 50
    ) -> Dict:
        """翻页加载 + 合并分析"""
        from src.core import CommentFetcher

        more = asyncio.run(
            CommentFetcher.load_more(video_id, cursor, count)
        )

        new_comments = more['comments']
        all_comments = (
            existing.get('hot_comments', []) +
            existing.get('latest_comments', []) +
            new_comments
        )

        # Limit total to 500
        if len(all_comments) > 500:
            all_comments = all_comments[:500]

        sentiment = self._sentiment_analysis(all_comments)
        keywords = self._extract_keywords(all_comments)
        summary = self._ai_summary(all_comments, sentiment, keywords)

        return {
            'video_id': video_id,
            'total_fetched': len(all_comments),
            'hot_comments': existing.get('hot_comments', []),
            'latest_comments': existing.get('latest_comments', []) + new_comments,
            'analysis': {
                'sentiment': sentiment,
                'keywords': keywords,
                'summary': summary,
            },
            'cursor': more['cursor'],
            'has_more': more['has_more'],
        }

    def _sentiment_analysis(self, comments: List[Dict]) -> Dict:
        """基于词典的情感分析"""
        pos, neg, neu = 0, 0, 0

        for c in comments:
            text = c.get('content', '')
            pos_score = sum(1 for w in POSITIVE_WORDS if w in text)
            neg_score = sum(1 for w in NEGATIVE_WORDS if w in text)

            if pos_score > neg_score:
                pos += 1
            elif neg_score > pos_score:
                neg += 1
            else:
                neu += 1

        total = len(comments) or 1
        return {
            'positive': round(pos * 100 / total, 1),
            'negative': round(neg * 100 / total, 1),
            'neutral': round(neu * 100 / total, 1),
            'positive_count': pos,
            'negative_count': neg,
            'neutral_count': neu,
        }

    def _extract_keywords(self, comments: List[Dict], top_n: int = 10) -> List[Dict]:
        """基于 TF 的关键词提取"""
        # Collect all words
        word_freq = {}
        for c in comments:
            text = c.get('content', '')
            # Simple Chinese word extraction (2-4 char n-grams)
            cleaned = re.sub(r'[^一-鿿]', ' ', text)
            words = cleaned.split()
            for w in words:
                if len(w) >= 2 and w not in STOP_WORDS:
                    word_freq[w] = word_freq.get(w, 0) + 1

        # Also extract common bigrams
        for c in comments:
            text = re.sub(r'[^一-鿿]', '', c.get('content', ''))
            for i in range(len(text) - 1):
                bigram = text[i:i+2]
                if bigram not in STOP_WORDS and len(bigram) == 2:
                    word_freq[bigram] = word_freq.get(bigram, 0) + 0.5

        # Sort and take top
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [
            {'word': w, 'count': int(c)} for w, c in sorted_words[:top_n]
        ]

    def _ai_summary(
        self, comments: List[Dict], sentiment: Dict, keywords: List[Dict]
    ) -> str:
        """AI 综合总结"""
        if not self.client:
            return self._fallback_summary(sentiment, keywords)

        # Build prompt with sample comments
        top_comments = sorted(
            comments, key=lambda c: c.get('digg_count', 0), reverse=True
        )[:10]
        extreme_comments = [
            c for c in comments
            if any(w in c.get('content', '') for w in POSITIVE_WORDS)
        ][:5] + [
            c for c in comments
            if any(w in c.get('content', '') for w in NEGATIVE_WORDS)
        ][:5]

        comment_samples = '\n'.join([
            f"  [{c.get('digg_count', 0)}赞] {c.get('nickname', '')}: {c.get('content', '')}"
            for c in (top_comments + extreme_comments)[:15]
        ])

        kw_str = ', '.join([k['word'] for k in keywords[:10]])

        prompt = f"""你是一位专业的社交媒体数据分析师。请根据以下抖音评论数据，生成简洁的评论分析报告。

## 数据概览
- 评论总数: {len(comments)}
- 情感分布: 正面{sentiment['positive']}% / 中性{sentiment['neutral']}% / 负面{sentiment['negative']}%
- 高频关键词: {kw_str}

## 代表性评论
{comment_samples}

## 要求
请从以下角度分析（200字以内）：
1. **用户画像**: 评论者是什么样的人群？
2. **核心观点**: 大家在讨论什么主要话题？
3. **争议点**: 有哪些不同意见？
4. **购买/行动意向**: 是否有转化潜力？

请用中文输出，简洁有力。"""

        try:
            response = self.client.chat.completions.create(
                model='deepseek-chat',
                messages=[
                    {'role': 'system', 'content': '你是一位专业的社交媒体数据分析师。'},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.7,
                max_tokens=600,
            )
            return response.choices[0].message.content
        except Exception as e:
            return self._fallback_summary(sentiment, keywords)

    def _fallback_summary(self, sentiment: Dict, keywords: List[Dict]) -> str:
        """无 AI 时的降级总结"""
        kw_str = '、'.join([k['word'] for k in keywords[:5]])
        if sentiment['positive'] > 50:
            tone = '整体评论偏正面，用户反馈积极'
        elif sentiment['negative'] > 30:
            tone = '存在一定负面声音，需关注用户不满点'
        else:
            tone = '评论态度较为中性'

        return (
            f'{tone}。'
            f'正面评论占{sentiment["positive"]}%，'
            f'负面评论占{sentiment["negative"]}%。'
            f'热门讨论词: {kw_str}。'
        )


# Global singleton
comment_analyzer = CommentAnalyzer()
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import sys; sys.path.insert(0, '.'); from src.comment_analyzer import comment_analyzer; print('OK')" 2>&1`

- [ ] **Step 3: Commit**

```bash
git add src/comment_analyzer.py
git commit -m "feat: add CommentAnalyzer for sentiment, keywords, AI summary"
```

---

### Task 4: Add batch-related CSS to `static/style.css`

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Append batch page styles**

Append to the end of `static/style.css`:

```css
/* ==================== Batch Page ==================== */
.batch-input-section {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
}

.batch-input-section textarea {
    width: 100%;
    min-height: 120px;
    padding: 14px;
    background: #111119;
    border: 1px solid var(--card-border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 0.9rem;
    font-family: inherit;
    outline: none;
    resize: vertical;
    line-height: 1.8;
    transition: border-color 0.2s;
}

.batch-input-section textarea:focus {
    border-color: var(--primary);
}

.batch-input-section textarea::placeholder {
    color: #555;
}

.batch-actions {
    display: flex;
    gap: 10px;
    margin-top: 12px;
    align-items: center;
}

.batch-global-controls {
    display: flex;
    gap: 8px;
    margin-left: auto;
}

/* Batch progress bar */
.batch-overall-progress {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 16px;
}

.batch-overall-progress .progress-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 0.88rem;
    color: var(--text-dim);
}

/* Task cards grid */
.task-cards {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.task-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 16px;
    transition: border-color 0.2s;
}

.task-card.status-done {
    border-color: rgba(0, 214, 143, 0.3);
}

.task-card.status-error {
    border-color: rgba(255, 107, 107, 0.3);
}

.task-card.status-processing {
    border-color: rgba(108, 92, 231, 0.4);
}

.task-card-header {
    display: flex;
    gap: 12px;
    align-items: center;
}

.task-card-cover {
    width: 64px;
    height: 85px;
    border-radius: 8px;
    background: #111119;
    background-size: cover;
    background-position: center;
    flex-shrink: 0;
}

.task-card-info {
    flex: 1;
    min-width: 0;
}

.task-card-info .tc-desc {
    font-size: 0.9rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 4px;
}

.task-card-info .tc-author {
    font-size: 0.8rem;
    color: var(--text-dim);
}

.task-card-info .tc-url {
    font-size: 0.75rem;
    color: #555;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-top: 2px;
}

.task-card-status {
    display: flex;
    align-items: center;
    gap: 6px;
}

.status-badge {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
}

.status-badge.queued { background: #2a2a3a; color: #888; }
.status-badge.parsing { background: rgba(108,92,231,0.15); color: #a78bfa; }
.status-badge.downloading { background: rgba(108,92,231,0.2); color: var(--primary); }
.status-badge.done { background: rgba(0,214,143,0.1); color: var(--success); }
.status-badge.error { background: rgba(255,107,107,0.1); color: var(--danger); }
.status-badge.paused { background: rgba(255,165,2,0.1); color: var(--orange); }

.task-card-progress {
    margin-top: 12px;
}

.task-card-progress .mini-bar {
    height: 4px;
    background: #222;
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 4px;
}

.task-card-progress .mini-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--pink));
    border-radius: 2px;
    width: 0%;
    transition: width 0.3s;
}

.task-card-progress .mini-text {
    font-size: 0.75rem;
    color: var(--text-dim);
}

.task-card-actions {
    display: flex;
    gap: 6px;
    margin-top: 12px;
}

/* Comment analysis panel */
.comment-panel {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--card-border);
}

.comment-panel h4 {
    font-size: 0.9rem;
    margin-bottom: 12px;
    color: var(--text);
}

.comment-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 16px;
}

.comment-stat {
    text-align: center;
    padding: 12px 8px;
    border-radius: var(--radius-sm);
    background: #111119;
}

.comment-stat .cs-value {
    font-size: 1.3rem;
    font-weight: 700;
}

.comment-stat .cs-label {
    font-size: 0.75rem;
    color: var(--text-dim);
    margin-top: 2px;
}

.comment-stat.positive .cs-value { color: var(--success); }
.comment-stat.neutral .cs-value { color: var(--orange); }
.comment-stat.negative .cs-value { color: var(--danger); }

.comment-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 16px;
}

.comment-keyword {
    padding: 4px 12px;
    background: rgba(108,92,231,0.12);
    color: var(--primary);
    border-radius: 20px;
    font-size: 0.8rem;
}

.comment-summary {
    background: #111119;
    border-radius: var(--radius-sm);
    padding: 14px;
    font-size: 0.85rem;
    line-height: 1.7;
    color: var(--text-dim);
}

.comment-loading {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px;
    color: var(--text-dim);
    font-size: 0.85rem;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "style: add batch page and comment panel CSS"
```

---

### Task 5: Create `static/batch.js`

**Files:**
- Create: `static/batch.js`

- [ ] **Step 1: Write batch.js**

Create `static/batch.js`:

```javascript
/**
 * 批量下载页面 — 前端逻辑
 */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const urlInput = $('#batchUrls');
const btnStart = $('#btnBatchStart');
const btnPause = $('#btnBatchPause');
const btnResume = $('#btnBatchResume');
const btnClear = $('#btnBatchClear');
const progressSection = $('#batchProgressSection');
const taskCards = $('#taskCards');
const globalProgressFill = $('#globalProgressFill');
const globalProgressText = $('#globalProgressText');

let currentBatchId = null;
let taskStates = {};
let eventSources = {};

// ==================== Actions ====================
btnStart.addEventListener('click', startBatch);
btnPause.addEventListener('click', pauseBatch);
btnResume.addEventListener('click', resumeBatch);
btnClear.addEventListener('click', clearAll);

async function startBatch() {
    const text = urlInput.value.trim();
    if (!text) { showToast('请粘贴抖音链接，一行一个'); return; }

    const urls = text.split('\n').map(s => s.trim()).filter(Boolean);
    if (urls.length === 0) { showToast('未检测到有效链接'); return; }
    if (urls.length > 50) { showToast('单次最多50个链接'); return; }

    btnStart.disabled = true;
    btnStart.textContent = '⏳ 创建中...';

    try {
        const resp = await fetch('/api/batch/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls }),
        });
        const data = await resp.json();

        if (!data.success) {
            showToast(data.error || '创建失败');
            btnStart.disabled = false;
            btnStart.textContent = '🚀 开始批量下载';
            return;
        }

        currentBatchId = data.batch_id;

        // Render task cards
        taskCards.innerHTML = '';
        data.tasks.forEach(task => {
            taskStates[task.task_id] = task;
            taskCards.appendChild(createTaskCard(task));
        });

        progressSection.classList.remove('hidden');
        btnStart.textContent = '✅ 已启动';
        btnPause.classList.remove('hidden');

        // Connect SSE for each task
        data.tasks.forEach(task => {
            connectTaskSSE(task.task_id);
        });

    } catch (e) {
        showToast('请求失败: ' + e.message);
        btnStart.disabled = false;
        btnStart.textContent = '🚀 开始批量下载';
    }
}

async function pauseBatch() {
    if (!currentBatchId) return;
    await fetch('/api/batch/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: currentBatchId }),
    });
    btnPause.classList.add('hidden');
    btnResume.classList.remove('hidden');
}

async function resumeBatch() {
    if (!currentBatchId) return;
    await fetch('/api/batch/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: currentBatchId }),
    });
    btnResume.classList.add('hidden');
    btnPause.classList.remove('hidden');
}

function clearAll() {
    urlInput.value = '';
    taskCards.innerHTML = '';
    progressSection.classList.add('hidden');
    currentBatchId = null;
    taskStates = {};
    // Close all SSE connections
    Object.values(eventSources).forEach(es => { try { es.close(); } catch(e) {} });
    eventSources = {};
    btnStart.disabled = false;
    btnStart.textContent = '🚀 开始批量下载';
    btnPause.classList.add('hidden');
    btnResume.classList.add('hidden');
}

// ==================== Task Card ====================
function createTaskCard(task) {
    const div = document.createElement('div');
    div.className = 'task-card status-queued';
    div.id = 'card-' + task.task_id;
    div.innerHTML = `
        <div class="task-card-header">
            <div class="task-card-cover" id="cover-${task.task_id}"></div>
            <div class="task-card-info">
                <div class="tc-desc" id="desc-${task.task_id}">等待中...</div>
                <div class="tc-author" id="author-${task.task_id}"></div>
                <div class="tc-url">${escHTML(task.url)}</div>
            </div>
            <div class="task-card-status">
                <span class="status-badge queued" id="status-${task.task_id}">排队中</span>
            </div>
        </div>
        <div class="task-card-progress">
            <div class="mini-bar"><div class="mini-fill" id="miniFill-${task.task_id}"></div></div>
            <div class="mini-text" id="miniText-${task.task_id}">等待处理...</div>
        </div>
        <div class="task-card-actions" id="actions-${task.task_id}">
            <button class="btn btn-sm" onclick="retryTask('${task.task_id}')" id="btnRetry-${task.task_id}" style="display:none;">🔄 重试</button>
            <button class="btn btn-sm" onclick="analyzeComments('${task.task_id}')" id="btnComment-${task.task_id}" style="display:none;">💬 评论分析</button>
        </div>
        <div id="commentPanel-${task.task_id}"></div>
    `;
    return div;
}

function updateTaskCard(taskId, updates) {
    const state = taskStates[taskId] = { ...(taskStates[taskId] || {}), ...updates };

    const card = $('#card-' + taskId);
    if (!card) return;

    // Status badge
    const badge = $('#status-' + taskId);
    const statusMap = {
        'queued': ['排队中', 'queued'],
        'parsing': ['解析中', 'parsing'],
        'downloading': ['下载中', 'downloading'],
        'done': ['已完成', 'done'],
        'error': ['失败', 'error'],
    };
    const [label, cls] = statusMap[state.status] || [state.status, 'queued'];
    badge.textContent = label;
    badge.className = 'status-badge ' + cls;
    card.className = 'task-card status-' + (state.status === 'downloading' || state.status === 'parsing' ? 'processing' : state.status);

    // Progress
    if (state.percent !== undefined) {
        $('#miniFill-' + taskId).style.width = state.percent + '%';
    }
    if (state.message) {
        $('#miniText-' + taskId).textContent = state.message;
    }

    // Video info
    if (state.desc) {
        $('#desc-' + taskId).textContent = state.desc;
        $('#desc-' + taskId).title = state.desc;
    }
    if (state.author) {
        $('#author-' + taskId).textContent = '👤 ' + state.author;
    }
    if (state.cover) {
        $('#cover-' + taskId).style.backgroundImage = 'url(' + state.cover + ')';
    }

    // Action buttons
    if (state.status === 'done') {
        $('#btnComment-' + taskId).style.display = '';
        $('#btnRetry-' + taskId).style.display = 'none';
    } else if (state.status === 'error') {
        $('#btnRetry-' + taskId).style.display = '';
        $('#btnComment-' + taskId).style.display = 'none';
    }

    updateGlobalProgress();
}

function updateGlobalProgress() {
    const tasks = Object.values(taskStates);
    const done = tasks.filter(t => t.status === 'done').length;
    const total = tasks.length;
    const pct = total > 0 ? Math.round(done * 100 / total) : 0;
    globalProgressFill.style.width = pct + '%';
    globalProgressText.textContent = done + ' / ' + total + ' 完成';
}

// ==================== SSE ====================
function connectTaskSSE(taskId) {
    if (eventSources[taskId]) {
        eventSources[taskId].close();
    }

    const es = new EventSource('/api/stream/' + taskId);
    eventSources[taskId] = es;

    es.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        const statusMap = {
            'parse': 'parsing',
            'download': 'downloading',
            'subtitle': 'downloading',
            'done': 'done',
        };
        updateTaskCard(taskId, {
            status: statusMap[data.step] || 'downloading',
            percent: data.percent || 0,
            message: data.message || '',
        });
    });

    es.addEventListener('meta', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, {
            desc: data.desc,
            author: data.author,
            cover: data.cover,
        });
    });

    es.addEventListener('video_ready', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, {
            videoUrl: data.url,
            filename: data.filename,
        });
    });

    es.addEventListener('subtitle_ready', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, {
            subtitleText: data.text,
        });
    });

    es.addEventListener('complete', (e) => {
        updateTaskCard(taskId, { status: 'done', percent: 100, message: '完成' });
        es.close();
    });

    es.addEventListener('error', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, {
            status: 'error',
            message: data.message || '处理失败',
        });
        es.close();
    });

    es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) {
            delete eventSources[taskId];
        }
    };
}

// ==================== Retry ====================
async function retryTask(taskId) {
    if (!currentBatchId) return;
    updateTaskCard(taskId, { status: 'parsing', percent: 0, message: '重试中...' });
    await fetch('/api/batch/retry/' + taskId, { method: 'POST' });
    connectTaskSSE(taskId);
}

// ==================== Comment Analysis ====================
async function analyzeComments(taskId) {
    const state = taskStates[taskId];
    const videoId = state.videoId;
    if (!videoId) { showToast('未找到视频ID'); return; }

    const panel = $('#commentPanel-' + taskId);
    panel.innerHTML = '<div class="comment-panel"><div class="comment-loading"><div class="spinner"></div>正在抓取评论并分析...</div></div>';
    panel.scrollIntoView({ behavior: 'smooth' });

    try {
        const resp = await fetch('/api/comments/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_id: videoId }),
        });
        const data = await resp.json();
        renderCommentResult(taskId, data);
    } catch (e) {
        panel.innerHTML = '<div class="comment-panel"><p style="color:var(--danger);">评论分析失败: ' + e.message + '</p></div>';
    }
}

function renderCommentResult(taskId, data) {
    const panel = $('#commentPanel-' + taskId);
    const analysis = data.analysis || {};

    let sentimentHtml = '';
    if (analysis.sentiment) {
        const s = analysis.sentiment;
        sentimentHtml = `
            <div class="comment-stats">
                <div class="comment-stat positive">
                    <div class="cs-value">${s.positive}%</div>
                    <div class="cs-label">正面 (${s.positive_count || 0})</div>
                </div>
                <div class="comment-stat neutral">
                    <div class="cs-value">${s.neutral}%</div>
                    <div class="cs-label">中性 (${s.neutral_count || 0})</div>
                </div>
                <div class="comment-stat negative">
                    <div class="cs-value">${s.negative}%</div>
                    <div class="cs-label">负面 (${s.negative_count || 0})</div>
                </div>
            </div>
        `;
    }

    let kwHtml = '';
    if (analysis.keywords && analysis.keywords.length > 0) {
        kwHtml = '<div class="comment-keywords">' +
            analysis.keywords.map(k =>
                '<span class="comment-keyword">' + escHTML(k.word) + ' (' + k.count + ')</span>'
            ).join('') +
            '</div>';
    }

    let summaryHtml = '';
    if (analysis.summary) {
        summaryHtml = '<div class="comment-summary">' +
            analysis.summary.replace(/\n/g, '<br>') +
            '</div>';
    }

    const hasMore = data.has_more;
    const totalFetched = data.total_fetched || 0;

    panel.innerHTML = `
        <div class="comment-panel">
            <h4>💬 评论分析 (${totalFetched}条)</h4>
            ${sentimentHtml}
            ${kwHtml}
            ${summaryHtml}
            ${hasMore ? `<button class="btn btn-sm" onclick="loadMoreComments('${taskId}')" style="margin-top:12px;">📥 加载更多评论</button>` : ''}
        </div>
    `;
}

async function loadMoreComments(taskId) {
    const state = taskStates[taskId];
    const videoId = state.videoId;
    const cursor = state.commentCursor || 0;

    try {
        const resp = await fetch('/api/comments/load-more?video_id=' + videoId + '&cursor=' + cursor + '&count=50');
        const data = await resp.json();
        taskStates[taskId].commentCursor = data.cursor;
        renderCommentResult(taskId, data);
        showToast('已加载更多评论');
    } catch (e) {
        showToast('加载失败: ' + e.message);
    }
}

// ==================== Utils ====================
function escHTML(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

let toastTimer;
function showToast(msg) {
    const toast = $('#toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 3000);
}
```

- [ ] **Step 2: Commit**

```bash
git add static/batch.js
git commit -m "feat: add batch download page frontend logic"
```

---

### Task 6: Create `templates/batch.html`

**Files:**
- Create: `templates/batch.html`

- [ ] **Step 1: Write batch page HTML**

Create `templates/batch.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>批量下载 — AI智能工具箱</title>
    <link rel="stylesheet" href="/static/style.css?v=3">
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <h1>AI智能工具箱</h1>
            <div class="subtitle-nav">
                <a href="/" class="douyin-link">抖音小助手</a>
                <span style="color:#555;">·</span>
                <a href="/batch" class="bg-link" style="border-color:rgba(255,255,255,0.5); box-shadow:0 0 18px rgba(108,92,231,0.25);">批量下载</a>
                <span style="color:#555;">·</span>
                <a href="/convert" class="convert-link">文档转换神器</a>
                <span style="color:#555;">·</span>
                <a href="/bgremove" class="bg-link">一键抠图</a>
            </div>
        </header>

        <!-- Input -->
        <section class="batch-input-section">
            <textarea id="batchUrls" placeholder="粘贴抖音链接，一行一个&#10;&#10;例如:&#10;https://v.douyin.com/abc123/&#10;https://www.douyin.com/video/123456789&#10;https://v.douyin.com/def456/"></textarea>
            <div class="batch-actions">
                <button id="btnBatchStart" class="btn btn-primary">🚀 开始批量下载</button>
                <div class="batch-global-controls">
                    <button id="btnBatchPause" class="btn btn-sm hidden">⏸ 暂停</button>
                    <button id="btnBatchResume" class="btn btn-sm hidden">▶ 继续</button>
                    <button id="btnBatchClear" class="btn btn-sm">🗑 清除</button>
                </div>
            </div>
        </section>

        <!-- Global Progress -->
        <section id="batchProgressSection" class="batch-overall-progress hidden">
            <div class="progress-label">
                <span>📊 总体进度</span>
                <span id="globalProgressText">0 / 0 完成</span>
            </div>
            <div class="progress-bar">
                <div id="globalProgressFill" class="progress-fill" style="width:0%;"></div>
            </div>
        </section>

        <!-- Task Cards -->
        <section id="taskCards" class="task-cards"></section>

        <!-- Toast -->
        <div id="toast" class="toast hidden"></div>
    </div>

    <script src="/static/batch.js?v=1"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/batch.html
git commit -m "feat: add batch download page template"
```

---

### Task 7: Update `app.py` with batch and comment API routes

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add new imports**

In `app.py`, after the existing import block (line 43), add:

```python
from src.batch_manager import batch_manager
from src.comment_analyzer import comment_analyzer
```

- [ ] **Step 2: Add batch page route**

After the bgremove page route (line 97), add:

```python
@app.route("/batch")
def batch_page():
    return render_template("batch.html")
```

- [ ] **Step 3: Add batch API routes**

After the Douyin API section (before line 416 — Export API), add:

```python
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
        "tasks": status["tasks"],
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
    # Find which batch contains this task
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
        try:
            result = comment_analyzer.fetch_and_analyze(video_id)
            # Cache result in memory (simple dict)
            _comment_cache[video_id] = result
        except Exception as e:
            _comment_cache[video_id] = {"error": str(e), "total_fetched": 0}

    import threading
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


@app.route("/api/comments/load-more")
def comments_load_more():
    video_id = request.args.get("video_id", "")
    cursor = int(request.args.get("cursor", 0))
    count = int(request.args.get("count", 50))

    existing = _comment_cache.get(video_id, {})

    result = comment_analyzer.load_more_and_analyze(video_id, cursor, existing, count)
    _comment_cache[video_id] = result
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

    body_html = f"""
    <h2>💬 评论分析报告</h2>
    <p>视频ID: {video_id} | 评论数: {data.get('total_fetched', 0)}</p>

    <h3>情感分布</h3>
    <table>
        <tr><th>正面</th><th>中性</th><th>负面</th></tr>
        <tr>
            <td style="color:#00d68f;">{sentiment.get('positive', 0)}% ({sentiment.get('positive_count', 0)})</td>
            <td style="color:#ffa502;">{sentiment.get('neutral', 0)}% ({sentiment.get('neutral_count', 0)})</td>
            <td style="color:#ff6b6b;">{sentiment.get('negative', 0)}% ({sentiment.get('negative_count', 0)})</td>
        </tr>
    </table>

    <h3>高频关键词</h3>
    <div>{kw_html}</div>

    <h3>AI 综合总结</h3>
    <p>{summary}</p>
    """

    return jsonify({"html": body_html, "title": f"评论分析_{video_id}"})
```

Note: The `_comment_cache` dict must be added at module level in `app.py`. Add after the `tasks = {}` line (line 54):

```python
_comment_cache = {}
```

- [ ] **Step 2: Verify routes**

Run: `python3 -c "import sys; sys.path.insert(0, '.'); from app import app; routes = [r.rule for r in app.url_map.iter_rules()]; print([r for r in routes if 'batch' in r or 'comment' in r])"`

Expected: List of batch and comment routes.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add batch and comment API routes to app.py"
```

---

### Task 8: Update navigation links in existing pages

**Files:**
- Modify: `templates/index.html`
- Modify: `templates/convert.html`
- Modify: `templates/bgremove.html`

- [ ] **Step 1: Add "批量下载" nav link to index.html**

In `templates/index.html`, in the `.subtitle-nav` div (line 15), add the batch link after the douyin link:

```html
<a href="/" class="douyin-link" style="border-color:rgba(255,255,255,0.5); box-shadow:0 0 18px rgba(255,107,157,0.25);">抖音小助手</a>
<span style="color:#555;">·</span>
<a href="/batch" class="bg-link">批量下载</a>
```

Replace lines 14-20 of `templates/index.html`:

From:
```html
            <div class="subtitle-nav">
    <a href="/" class="douyin-link" style="border-color:rgba(255,255,255,0.5); box-shadow:0 0 18px rgba(255,107,157,0.25);">抖音小助手</a>
    <span style="color:#555;">·</span>
    <a href="/convert" class="convert-link" style="">文档转换神器</a>
    <span style="color:#555;">·</span>
    <a href="/bgremove" class="bg-link" style="">一键抠图</a>
</div>
```

To:
```html
            <div class="subtitle-nav">
    <a href="/" class="douyin-link" style="border-color:rgba(255,255,255,0.5); box-shadow:0 0 18px rgba(255,107,157,0.25);">抖音小助手</a>
    <span style="color:#555;">·</span>
    <a href="/batch" class="bg-link">批量下载</a>
    <span style="color:#555;">·</span>
    <a href="/convert" class="convert-link">文档转换神器</a>
    <span style="color:#555;">·</span>
    <a href="/bgremove" class="bg-link">一键抠图</a>
</div>
```

Do the same for `templates/convert.html` and `templates/bgremove.html`.

- [ ] **Step 2: Commit**

```bash
git add templates/index.html templates/convert.html templates/bgremove.html
git commit -m "feat: add batch download nav link to all pages"
```

---

## Task Execution Order

1. Task 1 — `src/core.py` CommentFetcher (foundation)
2. Task 2 — `src/batch_manager.py` (foundation)
3. Task 3 — `src/comment_analyzer.py` (foundation)
4. Task 4 — `static/style.css` (styles)
5. Task 5 — `static/batch.js` (frontend logic)
6. Task 6 — `templates/batch.html` (page template)
7. Task 7 — `app.py` routes (wires everything)
8. Task 8 — nav links (polish)

Tasks 1-3 are independent and can run in parallel. Tasks 4-6 depend on the concepts from 1-3 but not their implementation. Task 7 depends on all preceding tasks. Task 8 is cosmetic.

---

## Verification Checklist

After all tasks complete, run the app and verify:

- [ ] `GET /batch` returns the batch page
- [ ] `POST /api/batch/create` with `{"urls": [...]}` returns batch_id + tasks
- [ ] `GET /api/batch/status/<batch_id>` shows task progress
- [ ] `POST /api/batch/pause` / `resume` toggle correctly
- [ ] `POST /api/batch/retry/<task_id>` retries a failed task
- [ ] `POST /api/comments/fetch` with `{"video_id": "..."}` triggers analysis
- [ ] `GET /api/comments/result/<video_id>` returns sentiment + keywords + summary
- [ ] `GET /api/comments/load-more` paginates correctly
- [ ] Navigation links work across all 4 pages
- [ ] Batch page: paste URLs, start, see cards progress, pause/resume, view comments
