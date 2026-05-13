"""
字幕提取模块
支持从API数据提取、OCR识别、语音识别三种方式
"""

import os
import json
import subprocess
import tempfile
from typing import Dict, Optional, List
from PIL import Image


class SubtitleExtractor:
    """字幕提取器"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = output_dir

    def extract(self, video_data: Dict, video_path: Optional[str] = None) -> Dict:
        """
        提取字幕文本

        Returns:
            {
                'source': 'api'|'ocr'|'speech'|'none',
                'text': str,
                'segments': List[Dict]  # 时间轴分段（如有）
            }
        """
        result = {
            'source': 'none',
            'text': '',
            'segments': [],
        }

        # 方法1: 从API数据提取
        api_text = self._extract_from_api(video_data)
        if api_text:
            result['source'] = 'api'
            result['text'] = api_text
            return result

        # 方法2: OCR识别视频帧中的文字
        if video_path and os.path.exists(video_path):
            ocr_text = self._extract_via_ocr(video_path)
            if ocr_text:
                result['source'] = 'ocr'
                result['text'] = ocr_text
                return result

        # 方法3: 语音识别
        if video_path and os.path.exists(video_path):
            speech_text = self._extract_via_speech(video_path)
            if speech_text:
                result['source'] = 'speech'
                result['text'] = speech_text
                return result

        return result

    def _extract_from_api(self, video_data: Dict) -> str:
        """从API响应中提取字幕文本"""
        from src.core import DouyinParser
        return DouyinParser.extract_captions(video_data)

    def _extract_via_ocr(self, video_path: str) -> Optional[str]:
        """通过OCR提取视频帧中的文字（采样关键帧）"""
        try:
            # 检查是否安装了tesseract
            tesseract_check = subprocess.run(
                ['which', 'tesseract'], capture_output=True, text=True
            )
            if tesseract_check.returncode != 0:
                return None

            import pytesseract

            # 提取关键帧
            frames_dir = tempfile.mkdtemp(prefix='dy_frames_')
            subprocess.run([
                'ffmpeg', '-i', video_path,
                '-vf', 'fps=1/2',  # 每2秒一帧
                '-frames:v', '20',  # 最多20帧
                f'{frames_dir}/frame_%03d.png'
            ], capture_output=True, timeout=30)

            # OCR识别每一帧
            texts = []
            for fname in sorted(os.listdir(frames_dir)):
                fpath = os.path.join(frames_dir, fname)
                try:
                    img = Image.open(fpath)
                    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                    text = text.strip()
                    if text and len(text) > 3:  # 过滤太短的
                        texts.append(text)
                except Exception:
                    pass

            # 清理临时文件
            subprocess.run(['rm', '-rf', frames_dir])

            if texts:
                return '\n'.join(texts)

        except Exception as e:
            print(f"   OCR提取失败: {e}")

        return None

    def _extract_via_speech(self, video_path: str) -> Optional[str]:
        """通过语音识别提取字幕"""
        try:
            # 提取音频
            audio_path = tempfile.mktemp(suffix='.wav', prefix='dy_audio_')
            subprocess.run([
                'ffmpeg', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le',
                '-ar', '16000', '-ac', '1',
                audio_path
            ], capture_output=True, timeout=30)

            if not os.path.exists(audio_path):
                return None

            # 尝试使用whisper
            try:
                import whisper
                model = whisper.load_model("small")
                result = model.transcribe(audio_path, language="zh")
                os.remove(audio_path)
                return result['text']
            except ImportError:
                pass
            except Exception:
                pass

            # 清理
            if os.path.exists(audio_path):
                os.remove(audio_path)

        except Exception as e:
            print(f"   语音识别失败: {e}")

        return None

    def save_to_file(self, result: Dict, base_path: str) -> Optional[str]:
        """保存字幕到文件"""
        if not result['text']:
            return None

        subtitle_path = base_path.rsplit('.', 1)[0] + '_subtitles.txt'
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write(f"提取方式: {result['source']}\n")
            f.write("=" * 50 + "\n\n")
            f.write(result['text'])

        return subtitle_path
