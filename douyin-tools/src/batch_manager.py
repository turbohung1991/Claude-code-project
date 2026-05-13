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
            'status': 'queued',
            'paused': False,
            'thread': None,
            'interval': 3,
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
                while batch['paused']:
                    time.sleep(1)
                    if batch_id not in self.batches:
                        return

            if task['status'] in ('done', 'error'):
                continue

            self._process_one(batch_id, task)

            if task != batch['tasks'][-1]:
                time.sleep(batch['interval'])

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
        from src.subtitle import SubtitleExtractor

        q = task['queue']

        def push(event_type, data):
            q.put({'event': event_type, 'data': data})

        try:
            url = task['url']

            # Parse
            push('progress', {'step': 'parse', 'message': '正在解析...', 'percent': 0})
            link_type = DouyinParser.detect_link_type(url)
            video_id = asyncio.run(DouyinParser.parse_url(url))
            if not video_id:
                push('error', {'message': '链接解析失败'})
                task['status'] = 'error'
                task['error'] = '链接解析失败'
                return

            # Get info
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

            # Download
            push('progress', {'step': 'download', 'message': '下载中...', 'percent': 20})

            filename = desc[:30]
            for ch in '#?&= ，。！？、；：""''【】《》\t\n\r':
                filename = filename.replace(ch, '_')
            filename = filename.replace('/', '_').replace('\\', '_').strip() or video_id

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

                selected = quality_options[0]
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

            # Subtitle
            push('progress', {'step': 'subtitle', 'message': '提取字幕...', 'percent': 50})
            extractor = SubtitleExtractor(output_dir=DOWNLOAD_DIR)
            subtitle_result = extractor.extract(video_data, download_path)
            push('subtitle_ready', {
                'text': subtitle_result.get('text', '')[:500],
                'source': subtitle_result.get('source', 'none'),
            })
            push('progress', {'step': 'done', 'message': '完成', 'percent': 100})

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
