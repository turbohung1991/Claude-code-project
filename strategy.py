"""
内容策略分析模块
基于AI对抖音视频进行多维度内容策略分析
"""

import json
import os
from typing import Dict, List, Optional
from openai import OpenAI


CONTENT_STRATEGY_PROMPT = """你是一位顶尖的抖音内容策略分析师。请根据提供的视频信息，进行专业的策略分析。

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

请用中文输出，要有洞察、有数据、有可执行的建议。不要空泛。
"""


class StrategyAnalyzer:
    """内容策略分析器"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API Key（或兼容的）
            base_url: API Base URL（可选，用于DeepSeek等）
        """
        self.api_key = (api_key or
                        os.environ.get('OPENAI_API_KEY') or
                        os.environ.get('DEEPSEEK_API_KEY') or
                        self._load_from_openclaw_config())

        self.base_url = (base_url or
                         os.environ.get('OPENAI_BASE_URL') or
                         os.environ.get('DEEPSEEK_BASE_URL') or
                         'https://api.deepseek.com/v1')

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.api_key else None

    @staticmethod
    def _load_from_openclaw_config() -> Optional[str]:
        """尝试从OpenClaw配置文件加载DeepSeek API Key"""
        config_paths = [
            os.path.expanduser('~/.openclaw/openclaw.json'),
            os.path.expanduser('~/.config/openclaw/openclaw.json'),
        ]
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        config = json.load(f)
                    ds = config.get('models', {}).get('providers', {}).get('deepseek', {})
                    return ds.get('apiKey')
                except Exception:
                    continue
        return None

    def analyze(self, video_data: Dict, subtitles: str = '',
                model: str = "deepseek-chat") -> Dict:
        """
        分析视频内容策略

        Returns:
            {
                'success': bool,
                'analysis': str,
                'metadata': Dict
            }
        """
        if not self.client:
            return {
                'success': False,
                'analysis': '未配置AI API Key。请设置 DEEPSEEK_API_KEY 环境变量或通过 --api-key 参数指定。',
                'metadata': {}
            }

        # 准备分析数据
        desc = video_data.get('desc', '无')
        author = video_data.get('author', {}).get('nickname', '未知')
        music_info = video_data.get('music', {})
        music = music_info.get('title', '') or music_info.get('author', '无')

        # 提取话题标签
        hashtags = []
        text_extra = video_data.get('text_extra', [])
        for extra in text_extra:
            tag = extra.get('hashtag_name', '') or extra.get('tag', '')
            if tag:
                hashtags.append(f"#{tag}")
        hashtag_str = ', '.join(hashtags) if hashtags else '无'

        # 时长
        duration = video_data.get('duration', 0) // 1000 if video_data.get('duration') else 0

        # 分辨率
        video_info = video_data.get('video', {})
        width = video_info.get('width', 0)
        height = video_info.get('height', 0)
        resolution = f"{width}x{height}" if width and height else '未知'

        # 构造提示词
        prompt = CONTENT_STRATEGY_PROMPT.format(
            desc=desc[:200],
            author=author,
            music=music,
            hashtags=hashtag_str,
            duration=duration,
            resolution=resolution,
            subtitles=subtitles[:1000] if subtitles else '无'
        )

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业的抖音内容策略分析师，输出必须结构化、有深度、可执行。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000,
            )

            analysis_text = response.choices[0].message.content

            return {
                'success': True,
                'analysis': analysis_text,
                'metadata': {
                    'model': response.model,
                    'usage': {
                        'prompt_tokens': response.usage.prompt_tokens if response.usage else 0,
                        'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                    }
                }
            }

        except Exception as e:
            return {
                'success': False,
                'analysis': f'分析失败: {str(e)}',
                'metadata': {}
            }

    def save_report(self, result: Dict, output_path: str) -> Optional[str]:
        """保存分析报告"""
        if not result['success']:
            return None

        report_path = output_path.rsplit('.', 1)[0] + '_策略分析.md'

        content = f"""# 抖音视频内容策略分析报告

---

{result['analysis']}

---

*分析模型: {result['metadata'].get('model', 'N/A')}*

"""
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return report_path
