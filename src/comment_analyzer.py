"""
评论分析模块
情感分析 + 关键词提取 + AI 综合总结
"""

import json
import os
import re
from typing import Dict, List, Optional

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
    """评论分析器 — 情感分析 + 关键词提取 + AI 综合总结"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        from src.strategy import StrategyAnalyzer
        temp = StrategyAnalyzer(api_key=api_key, base_url=base_url)
        self.api_key = temp.api_key
        self.base_url = temp.base_url
        self.client = temp.client

    def fetch_and_analyze(
        self, video_id: str, max_comments: int = 500
    ) -> Dict:
        """一站式：抓取 + 分析"""
        from src.core import CommentFetcher

        raw = CommentFetcher.fetch_comments_sync(video_id, max_comments)

        all_comments = raw['hot_comments'] + raw['latest_comments']
        if not all_comments:
            return {
                'video_id': video_id,
                'total_fetched': 0,
                'hot_comments': [],
                'latest_comments': [],
                'analysis': {
                    'sentiment': {'positive': 0, 'neutral': 0, 'negative': 0,
                                  'positive_count': 0, 'negative_count': 0, 'neutral_count': 0},
                    'keywords': [],
                    'summary': '暂无评论数据',
                },
                'cursor': 0,
                'has_more': False,
            }

        sentiment = self._sentiment_analysis(all_comments)
        keywords = self._extract_keywords(all_comments)
        summary = self._ai_summary(all_comments, sentiment, keywords)

        # Tag each comment with sentiment label
        tagged_comments = self._tag_comments(all_comments)

        return {
            'video_id': video_id,
            'total_fetched': len(all_comments),
            'hot_comments': raw['hot_comments'],
            'latest_comments': raw['latest_comments'],
            'tagged_comments': tagged_comments,
            'analysis': {
                'sentiment': sentiment,
                'keywords': keywords,
                'summary': summary,
            },
            'cursor': raw['cursor'],
            'has_more': raw['has_more'],
        }

    def _tag_comments(self, comments: List[Dict]) -> List[Dict]:
        """给每条评论打上情感标签"""
        tagged = []
        for c in comments:
            text = c.get('content', '')
            pos_score = sum(1 for w in POSITIVE_WORDS if w in text)
            neg_score = sum(1 for w in NEGATIVE_WORDS if w in text)
            if pos_score > neg_score:
                label = '正面'
            elif neg_score > pos_score:
                label = '负面'
            else:
                label = '中性'
            tagged.append({
                'nickname': c.get('nickname', ''),
                'content': c.get('content', ''),
                'create_time': c.get('create_time', 0),
                'digg_count': c.get('digg_count', 0),
                'sentiment': label,
            })
        return tagged

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

    def _extract_keywords(self, comments: List[Dict], top_n: int = 15) -> List[Dict]:
        """基于 jieba 分词 + TF 的关键词提取"""
        import jieba

        # 表情包模式（过滤抖音括号表情：捂脸/微笑/玫瑰/笑哭/送花/流泪 等）
        EMOJI_PATTERN = re.compile(r'\[[一-鿿\w]+\]')

        word_freq = {}
        for c in comments:
            text = c.get('content', '')
            # 移除表情包
            text = EMOJI_PATTERN.sub('', text)
            # 移除 URL、纯数字、标点
            text = re.sub(r'https?://\S+', '', text)
            text = re.sub(r'[@#]\S+', '', text)

            # jieba 分词
            words = jieba.cut(text)
            for w in words:
                w = w.strip()
                if len(w) >= 2 and w not in STOP_WORDS and not w.isdigit():
                    word_freq[w] = word_freq.get(w, 0) + 1

        # 按频次排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        # 取 top_n，但过滤掉频次太低的
        result = [{'word': w, 'count': int(c)} for w, c in sorted_words[:top_n * 2]
                  if c >= 2][:top_n]
        return result

    def _ai_summary(
        self, comments: List[Dict], sentiment: Dict, keywords: List[Dict]
    ) -> str:
        """AI 综合总结"""
        if not self.client:
            return self._fallback_summary(sentiment, keywords)

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

        prompt = f"""你是一位专业的社交媒体数据分析师。请根据以下抖音评论数据，生成结构化的评论分析报告。

## 数据概览
- 评论总数: {len(comments)}
- 情感分布: 正面{sentiment['positive']}% / 中性{sentiment['neutral']}% / 负面{sentiment['negative']}%
- 高频关键词: {kw_str}

## 代表性评论（高赞 + 极端情感）
{comment_samples}

## 输出格式（严格按此结构，每段用 ## 标题）:

## 用户画像
- 年龄层、职业背景、兴趣特征（2-3句话）
- 评分（1-10）：给出典型性评分

## 核心话题
- TOP 3 讨论焦点，每条一句话概括
- 附带 1-2 条代表性评论原文佐证

## 情感分析
- 正面情绪来源（用户满意什么）
- 负面情绪来源（用户不满什么）
- 中性评论的倾向性判断（偏正面/偏负面/纯中立）

## 争议与分歧
- 是否存在两极分化的话题
- 不同观点各有什么道理

## 商业洞察
- 用户购买/行动意向强度（强/中/弱）
- 转化机会点在哪些方面
- 内容创作者可优化的方向建议

请用中文输出，350-500字，要有数据支撑和可执行的建议。"""

        try:
            response = self.client.chat.completions.create(
                model='deepseek-chat',
                messages=[
                    {'role': 'system', 'content': '你是一位专业的社交媒体数据分析师，输出必须严格按指定格式，结构清晰，有数据有洞察。'},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.7,
                max_tokens=1200,
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
