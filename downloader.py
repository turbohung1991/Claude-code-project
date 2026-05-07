"""
视频下载模块
支持多清晰度选择、进度显示、音视频合并
"""

import os
import subprocess
import requests
from typing import Dict, Optional
from urllib.parse import urlparse


class VideoDownloader:
    """抖音视频下载器"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def download(self, video_data: Dict, quality_option: Dict,
                 filename: Optional[str] = None) -> Optional[str]:
        """
        下载视频

        Args:
            video_data: 视频元数据
            quality_option: 选中的清晰度选项
            filename: 自定义文件名（不含扩展名）

        Returns:
            下载后的文件路径，失败返回None
        """
        video_url = quality_option['url']
        if not video_url:
            print("❌ 无法获取视频下载地址")
            return None

        # 生成文件名
        if not filename:
            desc = video_data.get('desc', 'douyin_video')
            # 清理文件名
            filename = desc[:30].replace('/', '_').replace('\\', '_').strip()
            if not filename:
                filename = video_data.get('aweme_id', 'douyin_video')

        output_path = os.path.join(self.output_dir, f"{filename}.mp4")

        print(f"\n📥 开始下载: {filename}")
        print(f"   清晰度: {quality_option['label']}")
        print(f"   分辨率: {quality_option['width']}x{quality_option['height']}")
        print(f"   码率: {quality_option['bit_rate']//1000 if quality_option['bit_rate'] else 'N/A'} Kbps")

        # 下载视频
        success = self._download_file(video_url, output_path)

        if success:
            file_size = os.path.getsize(output_path)
            print(f"\n✅ 下载完成: {output_path}")
            print(f"   文件大小: {self._format_size(file_size)}")
            return output_path
        else:
            print(f"\n❌ 下载失败")
            return None

    def _download_file(self, url: str, output_path: str) -> bool:
        """下载文件，带进度显示"""
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                          "Version/16.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.douyin.com/",
        }

        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=60)
            resp.raise_for_status()

            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0

            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # 进度显示
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            bar_len = 40
                            filled = int(bar_len * percent / 100)
                            bar = '█' * filled + '░' * (bar_len - filled)
                            print(f"\r   [{bar}] {percent}% "
                                  f"({self._format_size(downloaded)}/"
                                  f"{self._format_size(total_size)})",
                                  end='', flush=True)

            print()  # 换行
            return True

        except Exception as e:
            print(f"\n   下载错误: {e}")
            return False

    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
