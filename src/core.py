"""
抖音视频解析核心模块 (Playwright版本)
使用浏览器自动化绕过反爬，支持短链接和长链接
"""

import re
import json
import asyncio
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

# ============================================================
# 正则模式 — 覆盖所有已知抖音链接格式
# ============================================================
SHORT_PATTERN = re.compile(r'v\.douyin\.com/([a-zA-Z0-9]+)/?')
LONG_PATTERN = re.compile(r'douyin\.com/video/(\d+)')
NOTE_PATTERN = re.compile(r'douyin\.com/note/(\d+)')
USER_VIDEO_PATTERN = re.compile(r'douyin\.com/user/.*?video/(\d+)')
USER_MODAL_PATTERN = re.compile(r'douyin\.com/user/\S*\?.*modal_id=(\d+)')
SHARE_PATTERN = re.compile(r'douyin\.com/share/video/(\d+)')
IES_SHARE_PATTERN = re.compile(r'iesdouyin\.com/share/video/(\d+)')
RAW_VIDEO_ID_PATTERN = re.compile(r'^(\d{15,20})$')
RENDER_DATA_PATTERN = re.compile(
    r'<script\s+id="RENDER_DATA"\s+type="application/json">(.*?)</script>',
    re.DOTALL
)

# 所有提取ID的正则（按优先级排列）
ALL_ID_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ('long_video', LONG_PATTERN),
    ('note', NOTE_PATTERN),
    ('ies_share', IES_SHARE_PATTERN),
    ('share', SHARE_PATTERN),
    ('user_video', USER_VIDEO_PATTERN),
    ('user_modal', USER_MODAL_PATTERN),
]

# 链接类型中文提示
LINK_TYPE_LABELS = {
    'short': '短链接（需浏览器跟随重定向）',
    'long_video': '视频链接',
    'note': '图文笔记',
    'share': '分享链接',
    'ies_share': '企业号分享链接',
    'user_video': '用户主页视频',
    'user_modal': '用户主页弹窗',
    'modal_page': '精选/发现页（modal_id）',
    'raw_id': '裸视频ID',
    'unknown': '无法识别的格式',
}

# 查询参数中可能包含视频ID的key
VIDEO_ID_QUERY_KEYS = ['video_id', 'aweme_id', 'item_id', 'modal_id']

# 从混合文本中提取抖音URL（如: "8.88 复制打开抖音 https://v.douyin.com/xxx/ ..."）
DOUYIN_URL_IN_TEXT = re.compile(
    r'(https?://(?:v\.|www\.)?(?:ies)?douyin\.com/[A-Za-z0-9/?=&_\-\.%~]+)'
)


class DouyinParser:
    """抖音链接解析器 — 基于Playwright浏览器自动化"""

    # ---- 类属性（外部可引用） ----
    SHORT_PATTERN = SHORT_PATTERN
    LONG_PATTERN = LONG_PATTERN
    NOTE_PATTERN = NOTE_PATTERN
    USER_VIDEO_PATTERN = USER_VIDEO_PATTERN
    USER_MODAL_PATTERN = USER_MODAL_PATTERN
    SHARE_PATTERN = SHARE_PATTERN
    IES_SHARE_PATTERN = IES_SHARE_PATTERN
    RAW_VIDEO_ID_PATTERN = RAW_VIDEO_ID_PATTERN

    # ================================================================
    # 浏览器生命周期
    # ================================================================

    @classmethod
    async def _launch_browser(cls):
        """每次请求独立启动浏览器（避免事件循环冲突）"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
            ],
        )
        return playwright, browser

    @classmethod
    async def _launch_context(cls, playwright, browser):
        """创建带反检测的浏览器上下文"""
        context = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            viewport={'width': 1440, 'height': 900},
            locale='zh-CN',
        )
        await context.add_init_script(
            '''Object.defineProperty(navigator, 'webdriver', {get: () => false});'''
        )
        return context

    # ================================================================
    # 链接类型检测 & ID提取
    # ================================================================

    @classmethod
    def extract_douyin_url(cls, text: str) -> Optional[str]:
        """
        从混合文本中提取抖音链接。

        处理从抖音App复制的原始分享文本，如：
        "0.79 o@d.Ag 05/14 DUY:/ # 大模型 https://v.douyin.com/xxx/ 复制此链接..."

        返回干净链接，没有则返回 None。
        """
        text = text.strip()

        # 如果整个文本就是一个 URL，直接返回
        if text.startswith('http://') or text.startswith('https://'):
            url = text.split()[0] if ' ' in text else text
            url = url.rstrip('.,;:!?。，；：！？)')
            if 'douyin.com' in url or 'iesdouyin.com' in url:
                return url
            return None

        # 从文本中提取抖音 URL
        urls = DOUYIN_URL_IN_TEXT.findall(text)
        if not urls:
            return None

        # 返回第一个匹配（大概率是要看的那个）
        url = urls[0].rstrip('.,;:!?。，；：！？)')
        return url

    @classmethod
    def detect_link_type(cls, url: str) -> str:
        """
        检测链接类型，返回类型标识符。

        支持的类型：
          short        — v.douyin.com 短链
          long_video   — douyin.com/video/123
          note         — douyin.com/note/123
          share        — douyin.com/share/video/123
          ies_share    — iesdouyin.com/share/video/123
          user_video   — douyin.com/user/xxx/video/123
          user_modal   — douyin.com/user/xxx?modal_id=123
          modal_page   — jingxuan/discover/search?modal_id=123
          raw_id       — 纯数字视频ID
          unknown      — 无法识别
        """
        url = url.strip()

        # 如果输入是混合文本（非纯URL），先提取URL
        if not url.startswith('http'):
            extracted = cls.extract_douyin_url(url)
            if extracted:
                url = extracted

        if RAW_VIDEO_ID_PATTERN.match(url):
            return 'raw_id'

        if SHORT_PATTERN.search(url):
            return 'short'

        for link_type, pattern in ALL_ID_PATTERNS:
            if pattern.search(url):
                return link_type

        # 查询参数兜底（jingxuan / discover / search 等）
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            for key in VIDEO_ID_QUERY_KEYS:
                if key in params and params[key][0].isdigit():
                    return 'modal_page'
        except Exception:
            pass

        return 'unknown'

    @classmethod
    def link_type_label(cls, link_type: str) -> str:
        """链接类型 → 中文描述"""
        return LINK_TYPE_LABELS.get(link_type, link_type)

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """
        从各种格式的抖音链接中提取视频ID（同步，不解析短链）。

        支持：
        - 混合文本（如: "复制打开抖音 https://v.douyin.com/xxx/ ..."）
        - 裸ID：7628983823787627689
        - douyin.com/video/{id}
        - douyin.com/note/{id}
        - douyin.com/share/video/{id}
        - iesdouyin.com/share/video/{id}
        - douyin.com/user/xxx/video/{id}
        - douyin.com/user/xxx?modal_id={id}
        - douyin.com/jingxuan?modal_id={id}
        - URL查询参数 video_id / aweme_id / item_id / modal_id
        """
        url = url.strip()

        # 混合文本 → 先提取URL
        if not url.startswith('http') and not RAW_VIDEO_ID_PATTERN.match(url):
            extracted = cls.extract_douyin_url(url)
            if extracted:
                url = extracted

        # 裸视频ID（纯数字）
        m = RAW_VIDEO_ID_PATTERN.match(url)
        if m:
            return m.group(1)

        # 正则匹配
        for _type, pattern in ALL_ID_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)

        # URL 查询参数兜底
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            for key in VIDEO_ID_QUERY_KEYS:
                if key in params:
                    val = params[key][0]
                    if val.isdigit():
                        return val
        except Exception:
            pass

        return None

    @classmethod
    async def parse_url(cls, url: str) -> Optional[str]:
        """
        统一入口：自动检测链接类型 + 提取视频ID。
        - 混合文本自动识别（如从App复制的分享文案）
        - 短链自动用 Playwright 跟随重定向
        返回 video_id，解析失败返回 None。
        """
        url = url.strip()

        # 如果不是纯URL/纯ID → 从混合文本中提取抖音链接
        if not url.startswith('http') and not RAW_VIDEO_ID_PATTERN.match(url):
            extracted = cls.extract_douyin_url(url)
            if extracted:
                url = extracted

        link_type = cls.detect_link_type(url)

        if link_type == 'raw_id':
            return url

        if link_type == 'short':
            return await cls._resolve_short_link(url)

        return cls.extract_video_id(url)

    @classmethod
    async def _resolve_short_link(cls, url: str) -> Optional[str]:
        """Playwright 跟随短链重定向，提取 video_id"""
        pw, browser = await cls._launch_browser()
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

            video_id = None

            async def on_response(resp):
                nonlocal video_id
                if resp.status in (301, 302, 200, 307, 308):
                    final_url = resp.url
                    for _type, pattern in ALL_ID_PATTERNS:
                        match = pattern.search(final_url)
                        if match:
                            video_id = match.group(1)
                            return

            page.on('response', on_response)
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await page.wait_for_timeout(2000)

            # 如果响应拦截没拿到，尝试从最终 URL 提取
            if not video_id:
                final_url = page.url
                for _type, pattern in ALL_ID_PATTERNS:
                    match = pattern.search(final_url)
                    if match:
                        video_id = match.group(1)
                        break

            await context.close()
        finally:
            await browser.close()
            await pw.stop()

        return video_id

    # 旧接口兼容
    resolve_short_link = _resolve_short_link

    # ================================================================
    # 视频信息获取
    # ================================================================

    @classmethod
    async def get_video_info(cls, video_id: str) -> Optional[Dict]:
        """
        通过Playwright浏览器获取视频信息。
        利用页面自身JS发起的API请求获取数据（绕过加密验证）。
        """
        pw, browser = await cls._launch_browser()
        try:
            context = await cls._launch_context(pw, browser)
            page = await context.new_page()

            video_data = None

            async def on_response(resp):
                nonlocal video_data
                url = resp.url

                # 拦截 aweme/detail API
                if 'aweme/v1/web/aweme/detail' in url or (
                    'aweme/v2' in url and 'detail' in url
                ):
                    try:
                        body = await resp.json()
                        detail = body.get('aweme_detail', {})
                        if detail and detail.get('aweme_id'):
                            video_data = detail
                    except Exception:
                        pass

                # feed API 备选
                if not video_data and (
                    'aweme/v1/web/aweme/post' in url or 'general/feed' in url
                ):
                    try:
                        body = await resp.json()
                        items = body.get('aweme_list', []) or body.get('data', [])
                        for item in items:
                            if isinstance(item, dict) and item.get('aweme_info'):
                                item = item['aweme_info']
                            if item.get('aweme_id') == video_id:
                                video_data = item
                                break
                    except Exception:
                        pass

            page.on('response', on_response)

            # 先访问首页建立 session
            await page.goto(
                'https://www.douyin.com/', wait_until='domcontentloaded', timeout=20000
            )
            await page.wait_for_timeout(2000)

            # 访问视频页面
            video_url = f'https://www.douyin.com/video/{video_id}'
            await page.goto(video_url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(5000)

            # RENDER_DATA 兜底
            if not video_data:
                html = await page.content()
                match = RENDER_DATA_PATTERN.search(html)
                if match:
                    try:
                        from urllib.parse import unquote
                        decoded = unquote(match.group(1))
                        data = json.loads(decoded)
                        video_data = cls._extract_from_render_data(data)
                    except Exception:
                        pass

            # page.evaluate 最终兜底
            if not video_data:
                try:
                    video_data = await page.evaluate(
                        '''() => {
                            try {
                                const app = document.querySelector('#RENDER_DATA');
                                if (app) {
                                    const data = JSON.parse(
                                        decodeURIComponent(app.textContent)
                                    );
                                    function findVideo(obj, depth) {
                                        if (depth > 10 || !obj || typeof obj !== 'object')
                                            return null;
                                        if (obj.video && obj.video.playAddr) return obj;
                                        if (obj.video && obj.video.play_addr) return obj;
                                        for (const key in obj) {
                                            const r = findVideo(obj[key], depth + 1);
                                            if (r) return r;
                                        }
                                        return null;
                                    }
                                    return findVideo(data, 0);
                                }
                            } catch(e) {}
                            return null;
                        }'''
                    )
                except Exception:
                    pass

        except Exception as e:
            print(f"Playwright error: {e}")
        finally:
            await context.close()
            await browser.close()
            await pw.stop()

        return video_data

    @classmethod
    def _extract_from_render_data(cls, data: dict, depth: int = 0) -> Optional[Dict]:
        """从RENDER_DATA递归提取视频信息"""
        if depth > 10 or not isinstance(data, dict):
            return None
        if 'video' in data and isinstance(data['video'], dict):
            if 'play_addr' in data['video'] or 'playAddr' in data['video']:
                return data
        for key, value in data.items():
            if isinstance(value, dict):
                result = cls._extract_from_render_data(value, depth + 1)
                if result:
                    return result
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        result = cls._extract_from_render_data(item, depth + 1)
                        if result:
                            return result
        return None

    # ================================================================
    # 清晰度解析
    # ================================================================

    @classmethod
    def parse_quality_options(cls, video_data: Dict) -> List[Dict]:
        """解析视频清晰度选项"""
        options = []
        video_info = video_data.get('video', {})

        bit_rates = video_info.get('bit_rate', [])
        if bit_rates:
            for br in bit_rates:
                gear_name = br.get('gear_name', '')
                bit_rate_val = br.get('bit_rate', 0)
                play_addr = br.get('play_addr', {}) or br.get('playAddr', {})
                url_list = play_addr.get('url_list', []) or play_addr.get('urlList', [])

                if not url_list:
                    continue

                label = cls._quality_label(gear_name, bit_rate_val)
                options.append({
                    'label': label,
                    'gear_name': gear_name,
                    'bit_rate': bit_rate_val,
                    'url': url_list[0],
                    'url_list': url_list,
                    'width': play_addr.get('width', 0),
                    'height': play_addr.get('height', 0),
                })

        if not options:
            play_addr = video_info.get('play_addr', {}) or video_info.get('playAddr', {})
            url_list = play_addr.get('url_list', []) or play_addr.get('urlList', [])
            if url_list:
                options.append({
                    'label': '默认清晰度',
                    'gear_name': 'default',
                    'bit_rate': video_info.get('bit_rate', 0),
                    'url': url_list[0],
                    'url_list': url_list,
                    'width': play_addr.get('width', 0),
                    'height': play_addr.get('height', 0),
                })

        # 去重 + 按码率降序
        seen = set()
        unique = []
        for opt in options:
            if opt['gear_name'] not in seen:
                seen.add(opt['gear_name'])
                unique.append(opt)
        unique.sort(key=lambda x: x['bit_rate'], reverse=True)
        return unique

    # ================================================================
    # 字幕提取
    # ================================================================

    @classmethod
    def extract_captions(cls, video_data: Dict) -> Optional[str]:
        """提取视频字幕/文案"""
        captions = []
        desc = video_data.get('desc', '')
        if desc:
            captions.append(f"【描述】{desc}")

        stickers = video_data.get('interaction_stickers') or []
        for sticker in stickers:
            text = sticker.get('text_content', '') or sticker.get('text', '')
            if text:
                captions.append(f"【贴纸】{text}")

        text_extra = video_data.get('text_extra') or []
        for extra in text_extra:
            tag = extra.get('hashtag_name', '') or extra.get('tag', '')
            if tag:
                captions.append(f"#话题# {tag}")

        music = video_data.get('music') or {}
        if music:
            music_title = music.get('title', '') or music.get('author', '')
            if music_title:
                captions.append(f"【音乐】{music_title}")

        author = video_data.get('author') or {}
        if author:
            nickname = author.get('nickname', '')
            if nickname:
                captions.append(f"【作者】{nickname}")

        return '\n'.join(captions) if captions else None

    # ================================================================
    # 内部工具
    # ================================================================

    @classmethod
    def _quality_label(cls, gear_name: str, bit_rate: int) -> str:
        """生成清晰度标签"""
        label_map = {
            '720_1': '720P 标清',
            '720_2': '720P 高清',
            '1080_1': '1080P 标清',
            '1080_2': '1080P 高清',
            '1080_4': '1080P 超清',
            '1080_8': '1080P 极清',
            'adapt_lowest_1': '自适应_最低',
            'adapt_low_1': '自适应_低',
            'adapt_medium_1': '自适应_中',
            'adapt_high_1': '自适应_高',
            'adapt_highest_1': '自适应_最高',
            'default': '默认清晰度',
        }
        if gear_name in label_map:
            return label_map[gear_name]
        if bit_rate > 8_000_000:
            return f"超清 ({bit_rate // 1_000_000}Mbps)"
        if bit_rate > 4_000_000:
            return f"高清 ({bit_rate // 1_000_000}Mbps)"
        if bit_rate > 1_000_000:
            return f"标清 ({bit_rate // 1_000_000}Mbps)"
        return gear_name or "未知清晰度"


# ================================================================
# 评论抓取器
# ================================================================

class CommentFetcher:
    """抖音评论抓取器 — 使用同步 Playwright 获取签名后用 requests 调 API"""

    @classmethod
    def fetch_comments_sync(
        cls, video_id: str, max_hot: int = 200, max_latest: int = 100
    ) -> Dict:
        """同步抓取评论"""
        from playwright.sync_api import sync_playwright
        import time

        result = {
            'video_id': video_id,
            'hot_comments': [],
            'latest_comments': [],
            'total_fetched': 0,
            'cursor': 0,
            'has_more': False,
        }

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox'],
            )
            try:
                context = browser.new_context(
                    user_agent=(
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/131.0.0.0 Safari/537.36'
                    ),
                    viewport={'width': 1440, 'height': 900},
                    locale='zh-CN',
                )
                page = context.new_page()

                # 访问视频页面，等待签名参数就绪
                page.goto(
                    'https://www.douyin.com/', wait_until='domcontentloaded', timeout=20000
                )
                page.wait_for_timeout(3000)

                video_url = f'https://www.douyin.com/video/{video_id}'
                page.goto(video_url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(5000)

                # 等待评论区加载
                for _ in range(5):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(2000)

                # 提取所有 cookies
                cookies = context.cookies()
                cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)

                # 从页面提取 msToken
                ms_token = page.evaluate('''() => {
                    try {
                        var m = document.cookie.match(/msToken=([^;]+)/);
                        if (m) return m[1];
                        m = localStorage.getItem('xmst');
                        if (m) return m;
                    } catch(e) {}
                    return '';
                }''')

                context.close()
            finally:
                browser.close()

        # 用 requests 直接调评论 API
        import requests as req

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': f'https://www.douyin.com/video/{video_id}',
            'Cookie': cookie_str,
        }

        all_hot = []
        all_latest = []
        cursor = 0
        has_more = True
        max_pages = 10

        for _ in range(max_pages):
            api_url = (
                f'https://www.douyin.com/aweme/v1/web/comment/list/'
                f'?aweme_id={video_id}&cursor={cursor}&count=50&item_type=0'
            )
            try:
                resp = req.get(api_url, headers=headers, timeout=15)
                data = resp.json()
                raw = data.get('comments', []) or []
                if not raw:
                    break

                for c in raw:
                    item = cls._normalize_comment(c)
                    if not item['content']:
                        continue
                    if c.get('is_hot') or c.get('is_hot_comment'):
                        all_hot.append(item)
                    else:
                        all_latest.append(item)

                cursor = data.get('cursor', 0)
                has_more = data.get('has_more', 0) == 1
                if not has_more:
                    break
            except Exception as e:
                print(f"[CommentFetcher] API error: {e}", flush=True)
                break

        result['hot_comments'] = all_hot[:max_hot]
        result['latest_comments'] = all_latest[:max_latest]
        result['total_fetched'] = len(all_hot) + len(all_latest)
        if all_latest:
            result['cursor'] = all_latest[-1].get('create_time', 0)
        result['has_more'] = has_more

        print(f"[CommentFetcher] total: {result['total_fetched']} comments for {video_id}",
              flush=True)
        return result

    @classmethod
    def load_more_sync(cls, video_id: str, cursor: int, count: int = 50) -> Dict:
        """同步翻页加载更多评论 — 直接调 API"""
        import requests as req

        result = {'comments': [], 'cursor': cursor, 'has_more': False}

        try:
            api_url = (
                f'https://www.douyin.com/aweme/v1/web/comment/list/'
                f'?aweme_id={video_id}&cursor={cursor}&count={count}&item_type=0'
            )
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': f'https://www.douyin.com/video/{video_id}',
            }
            resp = req.get(api_url, headers=headers, timeout=15)
            data = resp.json()
            raw = data.get('comments', []) or []
            result['comments'] = [
                cls._normalize_comment(c) for c in raw
                if cls._normalize_comment(c)['content']
            ]
            result['cursor'] = data.get('cursor', 0)
            result['has_more'] = data.get('has_more', 0) == 1
        except Exception as e:
            print(f"[CommentFetcher] load_more error: {e}", flush=True)

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
