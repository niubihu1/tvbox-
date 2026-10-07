# -*- coding: utf-8 -*-
# 可可影视 Spider — 兼容 FongMi/TV & WebHomeTV
# 基于 python-spider-guide 新规范编写
# 注意: 该站有 cdndefend 反爬, 需求解 SHA1 PoW 挑战
# QQ群：807916734
import sys
import re
import json
import time
import hashlib
import hmac
import base64
from urllib.parse import quote, unquote, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append('..')

# ===== 兼容导入：FM有基类，PeekPro没有就自己定义 =====
try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        _session = rq.Session()

        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = self._session.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

        def set_cookie(self, name, value, domain, path='/'):
            self._session.cookies.set(name, value, domain=domain, path=path)

        def get_cookies(self):
            return self._session.cookies


class Spider(Spider):

    # ===== 站点配置 =====
    DOMAINS = [
        'https://www.kkys03.com',
    ]

    # 图片 CDN 域名（主站 /vod1/ 路径有 cdndefend，CDN 可直接访问）
    PIC_CDN = 'https://vres.cyscyy.com'

    host = ''

    UA = ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')

    # 搜索引擎线路过滤关键词
    SKIP_KEYWORDS = ('搜索', '百度', '搜狗', '神马', '360', 'baidu', 'google',
                     'sogou', 'kuaishou', '快手')

    # 水印文本（需从标题中过滤）
    WATERMARKS = ('可可影视-kekys.com', '可可影视 kekys.com', '可可影视',
                  'kkys01.com', 'kkys', 'kekys.com')

    # ===== 4K API 配置 =====
    # APP API 域名
    API_VCACHE = 'https://vcache.mjrlin.cn'
    # AES-256-CBC 解密密钥和 IV (从 kkys.min.js KKYS.Settings.KEYS 提取)
    API_AES_KEY = b'ayt5wy5afwmwrpb19k9s3psx3dymyd0n'
    API_AES_IV = b'b3t069ijy7pirw0j'
    # HMAC-SHA1 签名密钥 (从 kkys.min.js KKYS.Settings.HASH 提取)
    API_HASH = 'te@9fs#5tbf8#dx7zw8nx'
    # 设备信息
    API_APP_ID = 'kkdy'
    API_DEVICE_ID = 'd2c2f3345d9b2b12'
    API_DEVICE_CREATED_AT = '1785930051138'
    # APP 请求头
    API_UA = ('com.kkdyC1V260805.T180309/3.5.0 Dalvik/2.1.0 '
              '(Linux; U; Android 11; KB2000 Build/RP1A.201005.001)')

    # ===== 父分类 =====
    classes = [
        {'type_name': '电影', 'type_id': '1'},
        {'type_name': '连续剧', 'type_id': '2'},
        {'type_name': '动漫', 'type_id': '3'},
        {'type_name': '综艺纪录', 'type_id': '4'},
        {'type_name': '短剧', 'type_id': '6'},
    ]

    # ===== 筛选器 =====
    # URL格式: /show/{type}-{genre}-{area}-{lang}-{year}-{sort}-{page}.html
    # sort值: 2=最新, 3=最热, 4=评分 (默认3)
    filters = {
        '1': [
            {'key': 'genre', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '剧情', 'v': '剧情'},
                {'n': '喜剧', 'v': '喜剧'},
                {'n': '动作', 'v': '动作'},
                {'n': '爱情', 'v': '爱情'},
                {'n': '恐怖', 'v': '恐怖'},
                {'n': '惊悚', 'v': '惊悚'},
                {'n': '犯罪', 'v': '犯罪'},
                {'n': '科幻', 'v': '科幻'},
                {'n': '悬疑', 'v': '悬疑'},
                {'n': '奇幻', 'v': '奇幻'},
                {'n': '冒险', 'v': '冒险'},
                {'n': '战争', 'v': '战争'},
                {'n': '历史', 'v': '历史'},
                {'n': '古装', 'v': '古装'},
                {'n': '家庭', 'v': '家庭'},
                {'n': '传记', 'v': '传记'},
                {'n': '武侠', 'v': '武侠'},
                {'n': '歌舞', 'v': '歌舞'},
                {'n': '短片', 'v': '短片'},
                {'n': '动画', 'v': '动画'},
                {'n': '儿童', 'v': '儿童'},
                {'n': '职场', 'v': '职场'},
            ]},
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '中国大陆'},
                {'n': '中国香港', 'v': '中国香港'},
                {'n': '中国台湾', 'v': '中国台湾'},
                {'n': '美国', 'v': '美国'},
                {'n': '日本', 'v': '日本'},
                {'n': '韩国', 'v': '韩国'},
                {'n': '英国', 'v': '英国'},
                {'n': '法国', 'v': '法国'},
                {'n': '德国', 'v': '德国'},
                {'n': '印度', 'v': '印度'},
                {'n': '泰国', 'v': '泰国'},
                {'n': '其他', 'v': '其他'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
                {'n': '2020', 'v': '2020'},
                {'n': '2019', 'v': '2019'},
                {'n': '2018', 'v': '2018'},
            ]},
            {'key': 'by', 'name': '排序', 'value': [
                {'n': '最热', 'v': '3'},
                {'n': '最新', 'v': '2'},
                {'n': '评分', 'v': '4'},
            ]},
        ],
        '2': [
            {'key': 'genre', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '国产剧', 'v': '国产剧'},
                {'n': '港剧', 'v': '港剧'},
                {'n': '韩剧', 'v': '韩剧'},
                {'n': '日剧', 'v': '日剧'},
                {'n': '欧美剧', 'v': '欧美剧'},
                {'n': '泰剧', 'v': '泰剧'},
                {'n': '台剧', 'v': '台剧'},
                {'n': '短剧', 'v': '短剧'},
            ]},
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '中国大陆'},
                {'n': '中国香港', 'v': '中国香港'},
                {'n': '中国台湾', 'v': '中国台湾'},
                {'n': '美国', 'v': '美国'},
                {'n': '日本', 'v': '日本'},
                {'n': '韩国', 'v': '韩国'},
                {'n': '英国', 'v': '英国'},
                {'n': '其他', 'v': '其他'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
                {'n': '2020', 'v': '2020'},
            ]},
            {'key': 'by', 'name': '排序', 'value': [
                {'n': '最热', 'v': '3'},
                {'n': '最新', 'v': '2'},
                {'n': '评分', 'v': '4'},
            ]},
        ],
        '3': [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '中国大陆'},
                {'n': '日本', 'v': '日本'},
                {'n': '美国', 'v': '美国'},
                {'n': '韩国', 'v': '韩国'},
                {'n': '其他', 'v': '其他'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
                {'n': '2020', 'v': '2020'},
            ]},
            {'key': 'by', 'name': '排序', 'value': [
                {'n': '最热', 'v': '3'},
                {'n': '最新', 'v': '2'},
                {'n': '评分', 'v': '4'},
            ]},
        ],
        '4': [
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
                {'n': '2020', 'v': '2020'},
            ]},
            {'key': 'by', 'name': '排序', 'value': [
                {'n': '最热', 'v': '3'},
                {'n': '最新', 'v': '2'},
                {'n': '评分', 'v': '4'},
            ]},
        ],
        '6': [
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
            ]},
            {'key': 'by', 'name': '排序', 'value': [
                {'n': '最热', 'v': '3'},
                {'n': '最新', 'v': '2'},
                {'n': '评分', 'v': '4'},
            ]},
        ],
    }

    # ===== 初始化 =====
    def init(self, extend=""):
        self.host = self.DOMAINS[0]
        self.header = {
            'User-Agent': self.UA,
            'Referer': self.host + '/',
        }
        self._home_cache = []
        self._home_cache_time = 0
        self._cdndefend_cookie = None
        self._search_token = None
        self._search_token_time = 0
        # 4K API 缓存: {vodId: {'sources': [...], 'time': ts}}
        self._api_detail_cache = {}
        self._probe_domain()

    def getName(self):
        return '可可影视'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ===== 多域名探测与切换 =====
    def _probe_domain(self):
        for domain in self.DOMAINS:
            try:
                text = self._txt(domain, timeout=10)
                if text and len(text) > 500 and not self._is_cdndefend_challenge(text):
                    self.host = domain
                    self.header['Referer'] = self.host + '/'
                    return
            except Exception:
                continue

    # ===== cdndefend PoW 求解器 =====
    def _solve_cdndefend(self, html):
        """求解 cdndefend JS 挑战

        算法:
        1. 从挑战页提取 40 位 hex 常量 C
        2. n1 = int(C[0], 16)
        3. 找最小 i 使 SHA1(C + str(i)) 的字节 [n1] == 0xb0 且 [n1+1] == 0x0b
        4. cookie = C + str(i)
        """
        try:
            m = re.search(r'["\']([a-fA-F0-9]{40})["\']', html)
            if not m:
                return None
            c = m.group(1)

            n1 = int(c[0], 16)
            target_b0 = 0xb0
            target_b1 = 0x0b

            for i in range(5000000):
                test = (c + str(i)).encode('utf-8')
                h = hashlib.sha1(test).digest()
                if h[n1] == target_b0 and h[n1 + 1] == target_b1:
                    return c + str(i)

            return None
        except Exception:
            return None

    def _is_cdndefend_challenge(self, text):
        """检测是否为 cdndefend 挑战页"""
        if not text:
            return False
        indicators = ('cdndefend', 'verifying your browser')
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators) and len(text) < 15000

    # ===== URL 拼接 =====
    def _url(self, path):
        if not path:
            return ''
        if path.startswith('http'):
            return path
        if path.startswith('/'):
            return self.host + path
        return self.host + '/' + path

    # ===== 图片 URL 拼接（使用 CDN 域名避开 cdndefend）=====
    def _pic_url(self, pic):
        """将图片路径转为 CDN URL

        主站 /vod1/ 路径有 cdndefend 反爬，Python 无法通过。
        但 vres.cyscyy.com 等 CDN 域名可以直接访问相同图片。
        """
        if not pic:
            return ''
        if 'logo_placeholder' in pic:
            return ''
        if pic.startswith('http'):
            return pic
        if pic.startswith('/'):
            return self.PIC_CDN + pic
        return self.PIC_CDN + '/' + pic

    # ===== 设置 cdndefend cookie (兼容 FM 和 PeekPro) =====
    def _set_cdndefend_cookie(self, cookie_val):
        """设置 cdndefend cookie"""
        self._cdndefend_cookie = cookie_val
        # 尝试通过 set_cookie 方法设置（PeekPro 环境）
        try:
            self.set_cookie('cdndefend_js_cookie', cookie_val,
                            domain=self.host.replace('https://', '').replace('http://', ''),
                            path='/')
        except Exception:
            pass

    # ===== 获取带 cdndefend cookie 的 header（用于封面图和播放）=====
    def _get_header(self, referer=None):
        """返回包含 cdndefend cookie 的 header 字典"""
        h = dict(self.header)
        if referer:
            h['Referer'] = referer
        if self._cdndefend_cookie:
            h['Cookie'] = f'cdndefend_js_cookie={self._cdndefend_cookie}'
        return h

    # ===== 内容响应 header（图片走 CDN，不需要 cdndefend cookie）=====
    def _content_header(self):
        """返回内容响应 header（用于封面图加载）"""
        return dict(self.header)

    # ===== 网络请求（含 cdndefend 挑战求解 + 重试）=====
    def _txt(self, url, referer=None, timeout=30):
        headers = dict(self.header)
        if referer:
            headers['Referer'] = referer
        if self._cdndefend_cookie:
            headers['Cookie'] = f'cdndefend_js_cookie={self._cdndefend_cookie}'

        for attempt in range(3):
            try:
                rsp = self.fetch(url, headers=headers, timeout=timeout)
                try:
                    rsp.encoding = 'utf-8'
                except Exception:
                    pass
                text = rsp.text

                if not self._is_cdndefend_challenge(text):
                    return text

                # 检测到 cdndefend 挑战，求解
                cookie = self._solve_cdndefend(text)
                if not cookie:
                    return text

                self._set_cdndefend_cookie(cookie)
                headers['Cookie'] = f'cdndefend_js_cookie={cookie}'

                # 重试请求
                rsp = self.fetch(url, headers=headers, timeout=timeout)
                try:
                    rsp.encoding = 'utf-8'
                except Exception:
                    pass
                text = rsp.text

                if not self._is_cdndefend_challenge(text):
                    return text

                # 第二次仍然是挑战页，可能是新挑战，重新求解
                cookie2 = self._solve_cdndefend(text)
                if cookie2:
                    self._set_cdndefend_cookie(cookie2)
                    headers['Cookie'] = f'cdndefend_js_cookie={cookie2}'
                    continue

            except Exception:
                return ''

        return ''

    # ===== 正则匹配工具 =====
    def _match(self, pattern, text, group=1, flags=0):
        m = re.search(pattern, text, flags)
        if m:
            return m.group(group)
        return ''

    # ===== 标题水印清理 =====
    def _clean_title(self, text):
        if not text:
            return ''
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除数学字母符号 (水印 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞)
        # 注意: \u 只支持4位hex, 超过FFFF的要用 \U + 8位hex
        text = re.sub(r'[\U0001D400-\U0001D7FF]', '', text)
        # 移除站点水印（在去点之前，保留水印中的原始点号）
        for wm in self.WATERMARKS:
            text = text.replace(wm, '')
        # 移除数学符号后残留的孤立标点 (如 kkys01.com 去掉数学符号后留下的点)
        text = re.sub(r'(?<!\d)\.(?!\d)', '', text)
        # 清理空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 清理首尾的孤立标点
        text = re.sub(r'^[.\s]+|[.\s]+$', '', text)
        return text

    # ========== 首页（始终返回 filters）==========
    def homeContent(self, filter):
        return {
            'class': self.classes,
            'filters': self.filters,
        }

    # ========== 首页精选（多分类并发抓取 + 缓存）==========
    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {'list': self._home_cache[:72], 'header': self._content_header()}

        # 首页可直接访问，从中提取视频
        html = self._txt(self.host + '/', timeout=15)
        if html and not self._is_cdndefend_challenge(html):
            videos = self._parse_home_list(html)
            if videos:
                self._home_cache = videos[:72]
                self._home_cache_time = now
                return {'list': self._home_cache, 'header': self._content_header()}

        # 备用：并发抓取分类页
        tids = ['1', '2', '3', '4']
        videos = []
        seen = set()

        def load(tid):
            url = f'{self.host}/show/{tid}------1.html'
            html = self._txt(url, timeout=15)
            return self._parse_video_list(html)

        try:
            pool = ThreadPoolExecutor(max_workers=4)
            futures = [pool.submit(load, tid) for tid in tids]
            for fu in as_completed(futures, timeout=20):
                for v in fu.result() or []:
                    vid = v.get('vod_id')
                    if vid and vid not in seen:
                        seen.add(vid)
                        videos.append(v)
                    if len(videos) >= 72:
                        break
            pool.shutdown(wait=False)
        except Exception:
            pass

        self._home_cache = videos[:72]
        self._home_cache_time = now
        return {'list': self._home_cache, 'header': self._content_header()}

    # ========== 解析首页视频列表 ==========
    def _parse_home_list(self, html):
        """从首页 HTML 解析视频列表

        首页结构: carousel-item + v-item 混合
        carousel-item: <a href="/detail/{id}.html" class="carousel-item">
          <div class="carousel-item-cover"><img data-original="cover"></div>
          <div class="carousel-item-title">标题</div>
          <div class="carousel-item-tags">备注</div>
        </a>

        v-item: 同分类页结构
        """
        videos = []
        seen_ids = set()

        # 方法1: 解析 carousel-item 卡片
        carousel_items = re.findall(
            r'<a[^>]*href="/detail/(\d+)\.html"[^>]*class="carousel-item"[^>]*>(.*?)</a>',
            html, re.S
        )
        for vod_id, inner in carousel_items:
            if vod_id in seen_ids:
                continue
            title = self._match(r'class="carousel-item-title"[^>]*>(.*?)</div>', inner, 1, re.S)
            title = self._clean_title(title)
            pic = self._match(r'data-original="([^"]+)"', inner)
            if pic and 'logo_placeholder' in pic:
                pic = ''
            remarks = self._match(r'class="carousel-item-tags"[^>]*>(.*?)</div>', inner, 1, re.S)
            remarks = self._clean_title(remarks)
            if title:
                seen_ids.add(vod_id)
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': self._pic_url(pic),
                    'vod_remarks': remarks,
                })

        # 方法2: 解析 v-item 卡片（首页也可能有）
        v_items = self._parse_v_item_cards(html)
        for v in v_items:
            if v['vod_id'] not in seen_ids:
                seen_ids.add(v['vod_id'])
                videos.append(v)

        return videos

    # ========== 解析 v-item 卡片（分类页/搜索页通用）==========
    def _parse_v_item_cards(self, html):
        """解析 v-item 格式的视频卡片

        结构:
        <a href="/detail/{id}.html" class="v-item">
          <div class="v-item-cover">
            <img data-original="placeholder" />  <!-- 占位图 -->
            <img data-original="real_cover" />   <!-- 真实封面 -->
          </div>
          <div class="v-item-top">
            <div class="v-item-top-left"><span>豆瓣:X.X分</span></div>
          </div>
          <div class="v-item-bottom"><span>备注</span></div>
          <div class="v-item-footer">
            <div class="v-item-title" style="display: none">水印</div>
            <div class="v-item-title">真实标题</div>
          </div>
        </a>
        """
        videos = []
        seen_ids = set()

        cards = re.findall(
            r'<a[^>]*href="/detail/(\d+)\.html"[^>]*class="v-item"[^>]*>(.*?)</a>',
            html, re.S
        )

        for vod_id, inner in cards:
            if vod_id in seen_ids:
                continue

            # 标题: 取非隐藏的 v-item-title
            titles = re.findall(
                r'class="v-item-title"[^>]*>(.*?)</div>',
                inner, re.S
            )
            title = ''
            for t in titles:
                clean = self._clean_title(t)
                if not clean:
                    continue
                # 跳过水印
                if any(wm in clean for wm in self.WATERMARKS):
                    continue
                title = clean
                break

            # 封面: 取第二个 data-original（第一个是占位图）
            imgs = re.findall(r'data-original="([^"]+)"', inner)
            pic = ''
            for img in imgs:
                if 'logo_placeholder' not in img:
                    pic = img
                    break

            # 备注: v-item-bottom > span
            remarks = self._match(
                r'class="v-item-bottom"[^>]*>.*?<span[^>]*>(.*?)</span>',
                inner, 1, re.S
            )
            remarks = self._clean_title(remarks)

            if title:
                seen_ids.add(vod_id)
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': self._pic_url(pic),
                    'vod_remarks': remarks,
                })

        return videos

    # ========== 解析搜索结果卡片 ==========
    def _parse_search_result_cards(self, html):
        """解析 search-result-item 格式的搜索结果

        结构:
        <a href="/detail/{id}.html" class="search-result-item">
          <div class="search-result-item-header"><div>电影</div></div>
          <div class="search-result-item-ctn">
            <div class="search-result-item-side">
              <div class="search-result-item-pic">
                <img data-original="cover" alt="标题" title="标题">
              </div>
            </div>
            ...
          </div>
        </a>
        """
        videos = []
        seen_ids = set()

        cards = re.findall(
            r'<a[^>]*href="/detail/(\d+)\.html"[^>]*class="search-result-item"[^>]*>(.*?)</a>',
            html, re.S
        )

        for vod_id, inner in cards:
            if vod_id in seen_ids:
                continue

            # 标题: 从 img alt 或 title 属性获取
            title = self._match(r'alt="([^"]+)"', inner)
            if not title:
                title = self._match(r'title="([^"]+)"', inner)
            title = self._clean_title(title)

            # 封面
            pic = self._match(r'data-original="([^"]+)"', inner)
            if pic and 'logo_placeholder' in pic:
                pic = ''

            # 备注: 从 search-result-item-footer 或其他元素
            remarks = self._match(
                r'class="search-result-item-footer"[^>]*>(.*?)</div>',
                inner, 1, re.S
            )
            remarks = self._clean_title(remarks)

            if title:
                seen_ids.add(vod_id)
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': self._pic_url(pic),
                    'vod_remarks': remarks,
                })

        return videos

    # ========== 分类列表 ==========
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)

            # 解析 extend 参数
            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    try:
                        ext = json.loads(extend)
                    except Exception:
                        ext = {}

            # 读取筛选参数
            genre = ext.get('genre', '') or ext.get('type', '')
            area = ext.get('area', '')
            year = ext.get('year', '')
            sort_by = ext.get('by', '') or ext.get('sort', '')
            lang = ext.get('lang', '')

            # 构建 /show/ URL
            # 格式: /show/{type}-{genre}-{area}-{lang}-{year}-{sort}-{page}.html
            # sort值: 2=最新, 3=最热, 4=评分
            if not sort_by:
                sort_by = '3'  # 默认最热

            parts = [
                tid,
                quote(genre, safe='') if genre else '',
                quote(area, safe='') if area else '',
                quote(lang, safe='') if lang else '',
                year or '',
                sort_by,
                str(pg),
            ]
            url = f'{self.host}/show/' + '-'.join(parts) + '.html'
            html = self._txt(url, timeout=30)

            if not html or self._is_cdndefend_challenge(html):
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 18, 'total': 18,
                        'header': self._content_header()}

            videos = self._parse_video_list(html)
            pagecount = self._parse_pagecount(html, tid)

            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 18,
                'total': pagecount * 18,
                'header': self._content_header(),
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 18, 'total': 18}

    # ========== 解析分页总页数 ==========
    def _parse_pagecount(self, html, tid=''):
        """解析分页总页数

        该站分页使用 AJAX 加载，页面源码中无分页链接。
        经测试，所有分类固定20页。
        """
        # 检查当前页是否有内容
        cards = re.findall(r'class="v-item"', html)
        if not cards:
            return 1
        # 该站所有分类固定20页
        return 20

    # ========== 解析视频列表（分类页）==========
    def _parse_video_list(self, html):
        """解析分类页视频列表

        使用 v-item 卡片结构解析
        """
        videos = self._parse_v_item_cards(html)

        # 备用: 如果 v-item 解析失败，尝试通用的 detail 链接解析
        if not videos:
            videos = self._parse_generic_detail_links(html)

        return videos

    # ========== 通用 detail 链接解析（备用）==========
    def _parse_generic_detail_links(self, html):
        """通用 detail 链接解析"""
        videos = []
        seen_ids = set()

        # 按链接分组
        link_pattern = re.compile(
            r'<a[^>]*href="/detail/(\d+)\.html"[^>]*>(.*?)</a>',
            re.S
        )

        id_data = {}
        for m in link_pattern.finditer(html):
            vod_id = m.group(1)
            inner = m.group(2)

            if vod_id not in id_data:
                id_data[vod_id] = {'texts': [], 'imgs': [], 'title_attr': ''}

            title_attr = self._match(r'title="([^"]+)"', m.group(0))
            if title_attr and not id_data[vod_id]['title_attr']:
                id_data[vod_id]['title_attr'] = title_attr

            text = re.sub(r'<[^>]+>', '', inner).strip()
            if text:
                id_data[vod_id]['texts'].append(text)

            img_src = self._match(r'data-original="([^"]+)"', inner)
            if img_src and 'logo_placeholder' not in img_src:
                id_data[vod_id]['imgs'].append(img_src)

        for vod_id, data in id_data.items():
            if vod_id in seen_ids:
                continue

            title = ''
            remarks = ''
            pic = ''

            if data['title_attr']:
                title = self._clean_title(data['title_attr'])

            for text in data['texts']:
                clean = self._clean_title(text)
                if not clean:
                    continue
                if clean.startswith('豆瓣:'):
                    continue
                if any(wm in clean for wm in self.WATERMARKS):
                    continue
                if any(kw in clean for kw in ('正片', '更新至', '全集', '第', '集', 'HD', 'TC',
                                               '完结', '高清', '抢先版', '蓝光', '4K')):
                    if not remarks:
                        remarks = clean
                    continue
                if not title:
                    title = clean

            if data['imgs']:
                pic = data['imgs'][0]

            if title:
                seen_ids.add(vod_id)
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': self._pic_url(pic),
                    'vod_remarks': remarks,
                })

        return videos

    # ========== 详情页 ==========
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = ids[0]

        url = f'{self.host}/detail/{vod_id}.html'
        html = self._txt(url, referer=self.host + '/', timeout=30)
        if not html or self._is_cdndefend_challenge(html):
            return {'list': []}

        vod = {}

        # 标题: detail-title 下的 <strong> 标签
        # 结构: <div class="detail-title"><strong>水印</strong><strong>真实标题</strong><strong>水印</strong></div>
        # CSS 隐藏奇数位 strong，显示偶数位
        title_section = self._match(
            r'class="detail-title"[^>]*>(.*?)</div>',
            html, 1, re.S
        )
        if title_section:
            strongs = re.findall(r'<strong[^>]*>(.*?)</strong>', title_section, re.S)
            # 偶数位（第2、4...个）是真实标题
            title_parts = []
            for idx, s in enumerate(strongs):
                clean = self._clean_title(s)
                if not clean:
                    continue
                if any(wm in clean for wm in self.WATERMARKS):
                    continue
                title_parts.append(clean)
            vod['vod_name'] = ''.join(title_parts).strip()
        else:
            vod['vod_name'] = ''

        # 如果标题为空，从 meta 标签获取
        if not vod['vod_name']:
            meta_title = self._match(r'<meta\s+name="keywords"\s+content="([^,]+)', html)
            if meta_title:
                vod['vod_name'] = self._clean_title(meta_title)

        # 封面: 从 detail-pic 或 meta og:image 获取
        pic = self._match(r'data-original="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', html)
        if pic and 'logo_placeholder' in pic:
            pic = ''
        if not pic:
            pic = self._match(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        vod['vod_pic'] = self._pic_url(pic)

        # 标签: detail-tags-item
        tags = re.findall(r'class="detail-tags-item"[^>]*>([^<]+)<', html)
        tag_texts = [t.strip() for t in tags if t.strip()]

        # 从标签中提取年份/地区/类型
        vod['vod_year'] = ''
        vod['vod_area'] = ''
        vod['type_name'] = ''
        for t in tag_texts:
            if re.match(r'^\d{4}$', t):
                vod['vod_year'] = t
            elif '/' in t:
                vod['type_name'] = t.strip()
            elif t in ('中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国',
                       '英国', '法国', '德国', '印度', '泰国', '其他'):
                vod['vod_area'] = t

        # 详情行: detail-info-row
        info_rows = re.findall(
            r'class="detail-info-row"[^>]*>.*?class="detail-info-row-side"[^>]*>(.*?)</div>.*?class="detail-info-row-main"[^>]*>(.*?)</div>',
            html, re.S
        )
        for label, content in info_rows:
            label = self._clean_title(label)
            content = self._clean_title(content)
            if '导演' in label:
                vod['vod_director'] = content
            elif '演员' in label or '主演' in label:
                vod['vod_actor'] = content
            elif '语言' in label:
                vod['vod_lang'] = content
            elif '状态' in label or '备注' in label:
                vod['vod_remarks'] = content
            elif '类型' in label:
                if not vod['type_name']:
                    vod['type_name'] = content
            elif '地区' in label:
                if not vod['vod_area']:
                    vod['vod_area'] = content
            elif '年份' in label:
                if not vod['vod_year']:
                    vod['vod_year'] = content

        if 'vod_remarks' not in vod:
            vod['vod_remarks'] = ''

        # 简介: 从 meta description 获取
        content = self._match(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if content:
            vod['vod_content'] = content.replace('&#039;', "'").replace('&amp;', '&').strip()
        else:
            vod['vod_content'] = ''

        # 播放列表
        play_from, play_url = self._parse_playlist(html, vod_id)

        # 如果 HTML 解析没有播放列表, 从 API 构建
        if not play_from:
            play_from, play_url = self._api_build_playlist(vod_id)

        vod['vod_play_from'] = '$$$'.join(play_from)
        vod['vod_play_url'] = '$$$'.join(play_url)

        return {'list': [vod], 'header': self._content_header()}

    # ===== 4K API: AES-256-CBC 解密 =====
    def _api_decrypt(self, enc_data):
        """解密 APP API 加密响应"""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            raw = base64.b64decode(base64.b64encode(enc_data))
            cipher = AES.new(self.API_AES_KEY, AES.MODE_CBC, self.API_AES_IV)
            decrypted = unpad(cipher.decrypt(raw), AES.block_size)
            return json.loads(decrypted.decode('utf-8'))
        except Exception:
            return None

    # ===== 4K API: 构建请求头 =====
    def _api_headers(self, ts=None, sign=None):
        """构建 APP API 请求头 (含 ts 和 sign 认证)"""
        h = {
            'User-Agent': self.API_UA,
            'appId': self.API_APP_ID,
            'os': 'android',
            'appVersion': '3.5.0',
            'package': 'com.kkdyC1V260805.T180309',
            'deviceId': self.API_DEVICE_ID,
            'deviceCreatedAt': self.API_DEVICE_CREATED_AT,
            'channelId': 'c1',
        }
        if ts is not None:
            h['ts'] = str(ts)
        if sign:
            h['sign'] = sign
        return h

    # ===== 4K API: 计算签名 =====
    def _api_compute_sign(self, method, url_path, params):
        """计算 API 请求签名

        从 kkys.min.js 逆向:
        1. data = convertObjectToQueryParameters(params) — 参数按 key 字母排序后拼接
        2. extra = appId=xxx&deviceCreatedAt=xxx&deviceId=xxx
        3. signString = method|url_path|data|ts|extra|
        4. sign = HmacSHA1(signString, HASH).hex()

        返回 (ts, sign)
        """
        ts = int(time.time() * 1000)
        method_lower = method.lower()

        # convertObjectToQueryParameters: 按key字母排序
        if params:
            sorted_keys = sorted(params.keys())
            data = '&'.join(f'{k}={params[k]}' for k in sorted_keys)
        else:
            data = ''

        extra = (f'appId={self.API_APP_ID}'
                 f'&deviceCreatedAt={self.API_DEVICE_CREATED_AT}'
                 f'&deviceId={self.API_DEVICE_ID}')
        sign_string = f'{method_lower}|{url_path}|{data}|{ts}|{extra}|'
        sign = hmac.new(self.API_HASH.encode('utf-8'),
                        sign_string.encode('utf-8'),
                        hashlib.sha1).hexdigest()
        return ts, sign

    # ===== 4K API: 获取 vod 详情 (含所有线路的 siteId 和 episodeVodId) =====
    def _api_get_detail(self, vod_id):
        """调用 detail.capi 获取 vod 详情, 返回 playSources 列表

        返回格式:
        [
            {
                'siteId': 'dujia2',
                'name': '超清2',
                'episodeVodId': 95728,
                'tips': '秒播/4K',
                'list': [...],  # 部分线路有直接返回集数和m3u8
            },
            ...
        ]
        """
        # 缓存检查 (10分钟有效期)
        cache = self._api_detail_cache.get(vod_id)
        if cache and time.time() - cache['time'] < 600:
            return cache['sources']

        try:
            url_path = '/v2/vod/detail.capi'
            url = f'{self.API_VCACHE}{url_path}'
            params = {
                'vodId': vod_id,
                'os': 'android',
                'appId': self.API_APP_ID,
                'userLevel': '0',
            }
            ts, sign = self._api_compute_sign('GET', url_path, params)
            resp = self.fetch(url, headers=self._api_headers(ts, sign),
                              params=params, timeout=15)
            if resp.status_code != 200:
                return []
            if resp.headers.get('Encrypted') != '1':
                return []
            result = self._api_decrypt(resp.content)
            if not result or result.get('code') != 200:
                return []
            sources = result.get('data', {}).get('playSources', [])
            self._api_detail_cache[vod_id] = {
                'sources': sources,
                'time': time.time(),
            }
            return sources
        except Exception:
            return []

    # ===== 4K API: 获取某线路的集数和 m3u8 URL =====
    def _api_get_episodes(self, vod_id, site_id, episode_vod_id):
        """调用 episodes.capi 获取指定线路的 m3u8 URL

        返回格式:
        [
            {
                'id': 2918628,
                'title': '第1集',
                'index': 1,
                'playUrls': [{'name': 'L9', 'url': 'https://...', 'type': 'h264'}],
            },
            ...
        ]
        """
        try:
            url_path = '/v2/vod/episodes.capi'
            url = f'{self.API_VCACHE}{url_path}'
            params = {
                'vodId': vod_id,
                'siteId': site_id,
                'episodeVodId': str(episode_vod_id),
                'os': 'android',
                'appId': self.API_APP_ID,
                'userLevel': '0',
            }
            ts, sign = self._api_compute_sign('GET', url_path, params)
            resp = self.fetch(url, headers=self._api_headers(ts, sign),
                              params=params, timeout=15)
            if resp.status_code != 200:
                return []
            if resp.headers.get('Encrypted') != '1':
                return []
            result = self._api_decrypt(resp.content)
            if not result or result.get('code') != 200:
                return []
            return result.get('data', [])
        except Exception:
            return []

    # ===== 4K API: 通过 play URL 获取 m3u8 =====
    def _api_resolve_play_url(self, play_url):
        """通过 API 解析 4K 线路的 m3u8 URL

        play_url 格式: /play/{vodId}-{sourceId}-{episodeId}.html

        返回 m3u8 URL 或空字符串
        """
        try:
            m = re.match(r'/play/(\d+)-(\d+)-(\d+)\.html', play_url)
            if not m:
                return ''
            vod_id, source_id, episode_id = m.group(1), m.group(2), m.group(3)

            # 获取详情, 找到对应线路
            sources = self._api_get_detail(vod_id)

            # 遍历所有 API 线路, 找到有匹配 episodeId 的那个
            for source in sources:
                site_id = source.get('siteId', '')
                ep_vod_id = source.get('episodeVodId', 0)
                ep_list = source.get('list', [])

                # 如果该线路已有集数列表, 直接查找
                if ep_list:
                    for ep in ep_list:
                        if str(ep.get('id', '')) == episode_id:
                            play_urls = ep.get('playUrls', [])
                            if play_urls:
                                return play_urls[0].get('url', '')
                    continue

                # 如果该线路没有集数列表, 调用 episodes.capi 获取
                if not site_id or not ep_vod_id:
                    continue
                episodes = self._api_get_episodes(vod_id, site_id, ep_vod_id)
                for ep in episodes:
                    if str(ep.get('id', '')) == episode_id:
                        play_urls = ep.get('playUrls', [])
                        if play_urls:
                            return play_urls[0].get('url', '')

            # Fallback: 4K/秒播线路 (dujia2) 可能不在 detail.capi 返回中
            # 尝试用 vodId 作为 episodeVodId 获取 dujia2 线路的集数
            for test_ep_vod_id in [vod_id, source_id]:
                episodes = self._api_get_episodes(vod_id, 'dujia2', test_ep_vod_id)
                if not episodes:
                    continue
                for ep in episodes:
                    if str(ep.get('id', '')) == episode_id:
                        play_urls = ep.get('playUrls', [])
                        if play_urls:
                            return play_urls[0].get('url', '')
                # 如果 dujia2 有集数但没匹配到, 尝试用 source_id 作为 episodeVodId
                if test_ep_vod_id == vod_id and episodes:
                    break

            return ''
        except Exception:
            return ''

    # ===== 4K API: 从 API 构建播放列表 =====
    def _api_build_playlist(self, vod_id):
        """从 APP API 构建播放列表 (当网站 HTML 无播放列表时使用)

        返回 (play_from, play_url) 列表
        play_from: ['优质1(播放快/高清)', '蓝光1(香港加速)', ...]
        play_url: ['第1集$/play/32184-1-299069.html#...', ...]
        """
        play_from = []
        play_url = []

        try:
            sources = self._api_get_detail(vod_id)
            sid_counter = 0

            for source in sources:
                site_id = source.get('siteId', '')
                name = source.get('name', '')
                tips = source.get('tips', '')
                ep_vod_id = source.get('episodeVodId', 0)
                ep_list = source.get('list', [])

                # 跳过搜索引擎线路
                if any(kw in name.lower() for kw in self.SKIP_KEYWORDS):
                    continue

                # 如果没有集数列表, 调用 episodes.capi 获取
                if not ep_list and site_id and ep_vod_id:
                    ep_list = self._api_get_episodes(vod_id, site_id, ep_vod_id)

                if not ep_list:
                    continue

                sid_counter += 1
                line_name = f'{name}({tips})' if tips else name

                ep_strs = []
                for ep in ep_list:
                    ep_id = ep.get('id', '')
                    ep_title = ep.get('title', '') or f'第{len(ep_strs) + 1}集'
                    ep_title = self._clean_title(ep_title)
                    if not ep_title:
                        ep_title = f'第{len(ep_strs) + 1}集'
                    ep_strs.append(f'{ep_title}$/play/{vod_id}-{sid_counter}-{ep_id}.html')

                if ep_strs:
                    play_from.append(line_name)
                    play_url.append('#'.join(ep_strs))

            # 尝试添加 4K/秒播线路 (dujia2, 不在 detail.capi 中)
            dujia2_episodes = self._api_get_episodes(vod_id, 'dujia2', vod_id)
            if dujia2_episodes:
                sid_counter += 1
                ep_strs = []
                for ep in dujia2_episodes:
                    ep_id = ep.get('id', '')
                    ep_title = ep.get('title', '') or f'第{len(ep_strs) + 1}集'
                    ep_title = self._clean_title(ep_title)
                    if not ep_title:
                        ep_title = f'第{len(ep_strs) + 1}集'
                    ep_strs.append(f'{ep_title}$/play/{vod_id}-{sid_counter}-{ep_id}.html')

                if ep_strs:
                    # 根据 episode 数量判断是电影还是剧集
                    if len(dujia2_episodes) == 1:
                        line_name = '4K(秒播/4K)'
                    else:
                        line_name = '超清2(秒播/4K)'
                    play_from.append(line_name)
                    play_url.append('#'.join(ep_strs))

        except Exception:
            pass

        return play_from, play_url

    # ========== 解析播放列表 ==========
    def _parse_playlist(self, html, vod_id):
        """解析播放列表

        结构:
        1. source-list-box-main > source-item (线路标签)
        2. episode-list-box-main > episode-list (每条线路的集数)

        source-item 和 episode-list 按顺序一一对应

        source-item:
          <a class="source-item">
            <span class="source-item-label">4K</span>
            <span class="source-item-sublabel">秒播/4K</span>
          </a>

        episode-list:
          <div class="episode-list">
            <a href="/play/{vodid}-{sid}-{eid}.html" class="episode-item">
              <span>集名</span>
            </a>
          </div>
        """
        play_from = []
        play_url = []

        # 提取线路标签
        source_items = re.findall(
            r'<a[^>]*class="source-item[^"]*"[^>]*>(.*?)</a>',
            html, re.S
        )
        source_names = []
        for item in source_items:
            label = self._match(r'source-item-label[^>]*>([^<]+)<', item)
            sublabel = self._match(r'source-item-sublabel[^>]*>([^<]+)<', item)
            label = label.strip() if label else ''
            sublabel = sublabel.strip() if sublabel else ''
            if label and sublabel:
                source_names.append(f'{label}({sublabel})')
            elif label:
                source_names.append(label)
            else:
                source_names.append(f'线路{len(source_names) + 1}')

        # 提取每条线路的集数
        ep_lists = re.findall(
            r'<div class="episode-list"[^>]*>(.*?)</div>',
            html, re.S
        )

        # 按顺序配对
        for idx, ep_list_html in enumerate(ep_lists):
            if idx >= len(source_names):
                break

            line_name = source_names[idx]

            # 跳过搜索引擎线路
            if any(kw in line_name.lower() for kw in self.SKIP_KEYWORDS):
                continue

            # 4K/秒播线路不再跳过, 通过 APP API 解析 m3u8
            # (之前跳过是因为网站 playSource.src 为空, 但 APP API 可以获取 m3u8)

            # 提取集数
            episodes = re.findall(
                r'<a[^>]*href="(/play/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>',
                ep_list_html, re.S
            )

            ep_list = []
            for ep_url, ep_inner in episodes:
                ep_name = re.sub(r'<[^>]+>', '', ep_inner).strip()
                ep_name = self._clean_title(ep_name)
                if not ep_name:
                    ep_name = f'第{len(ep_list) + 1}集'
                ep_list.append(f'{ep_name}${ep_url}')

            if ep_list:
                play_from.append(line_name)
                play_url.append('#'.join(ep_list))

        # 备用: 如果没有 source-item，直接从 episode-list 提取
        if not play_from and ep_lists:
            for idx, ep_list_html in enumerate(ep_lists):
                episodes = re.findall(
                    r'<a[^>]*href="(/play/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>',
                    ep_list_html, re.S
                )
                ep_list = []
                for ep_url, ep_inner in episodes:
                    ep_name = re.sub(r'<[^>]+>', '', ep_inner).strip()
                    ep_name = self._clean_title(ep_name)
                    if not ep_name:
                        ep_name = f'第{len(ep_list) + 1}集'
                    ep_list.append(f'{ep_name}${ep_url}')
                if ep_list:
                    play_from.append(f'线路{idx + 1}')
                    play_url.append('#'.join(ep_list))

        # 备用2: 从全页面提取 play 链接
        if not play_from:
            episodes = re.findall(
                r'<a[^>]*class="episode-item[^"]*"[^>]*href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>',
                html, re.S
            )
            source_groups = {}
            source_order = []
            for ep_url, vid, sid, eid, inner in episodes:
                if vid != vod_id:
                    continue
                ep_name = re.sub(r'<[^>]+>', '', inner).strip()
                ep_name = self._clean_title(ep_name)
                if sid not in source_groups:
                    source_groups[sid] = []
                    source_order.append(sid)
                source_groups[sid].append((ep_url, ep_name))

            for idx, sid in enumerate(source_order):
                eps = source_groups[sid]
                line_name = f'线路{idx + 1}'
                if any(kw in line_name.lower() for kw in self.SKIP_KEYWORDS):
                    continue
                ep_list = []
                for ep_url, ep_name in eps:
                    display_name = ep_name if ep_name else f'第{len(ep_list) + 1}集'
                    ep_list.append(f'{display_name}${ep_url}')
                if ep_list:
                    play_from.append(line_name)
                    play_url.append('#'.join(ep_list))

        return play_from, play_url

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg or 1)

            # 获取搜索 token（从首页 hidden input）
            if not self._search_token or time.time() - self._search_token_time > 300:
                home_html = self._txt(self.host + '/', timeout=15)
                if home_html and not self._is_cdndefend_challenge(home_html):
                    token = self._match(r'name="t"[^>]*value="([^"]+)"', home_html)
                    if token:
                        self._search_token = token
                        self._search_token_time = time.time()

            if not self._search_token:
                return {'list': [], 'page': pg}

            # 搜索
            url = (f'{self.host}/search?k={quote(key, safe="")}'
                   f'&t={quote(self._search_token, safe="")}')
            if pg > 1:
                url += f'&page={pg}'

            html = self._txt(url, timeout=30)
            if not html or self._is_cdndefend_challenge(html):
                return {'list': [], 'page': pg}

            # 解析搜索结果
            videos = self._parse_search_result_cards(html)

            # 备用: 如果 search-result-item 解析失败，尝试 v-item
            if not videos:
                videos = self._parse_v_item_cards(html)

            # 备用2: 通用 detail 链接解析
            if not videos:
                videos = self._parse_generic_detail_links(html)

            return {'list': videos, 'page': pg, 'header': self._content_header()}
        except Exception:
            return {'list': [], 'page': pg}

    # ========== 播放解析（多级 fallback）==========
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        url = id if str(id).startswith('http') else self._url(id)

        # 播放 header: 仅含 UA + Referer，不含 cdndefend cookie
        # m3u8 在外部 CDN 上，不需要主站 cookie；带 cookie 反而可能被 CDN 拒绝
        play_header = {
            'User-Agent': self.UA,
            'Referer': self.host + '/',
        }

        # 0. /play/ 链接: 通过 APP API 获取 m3u8
        # 网站播放页可能无法直接解析, 优先用 APP API
        if '/play/' in id:
            m3u8_url = self._api_resolve_play_url(id)
            if m3u8_url:
                api_play_header = {
                    'User-Agent': 'com.salmon.film.app.start.App/3.5.0 (Linux;Android 11) AndroidXMedia3/1.9.0',
                }
                return {
                    'parse': 0,
                    'playUrl': '',
                    'url': m3u8_url,
                    'header': api_play_header,
                    'format': 'application/x-mpegURL',
                    'contentType': 'application/x-mpegURL',
                }

        # 1. 直链检测
        if self._is_direct_media(url):
            real = url
            if '.m3u8' in real.lower():
                real = self._resolve_m3u8_child(real, referer=self.host + '/')
            return {
                'parse': 0,
                'playUrl': '',
                'url': real,
                'header': play_header,
                'format': 'application/x-mpegURL' if '.m3u8' in real else '',
                'contentType': 'application/x-mpegURL' if '.m3u8' in real else '',
            }

        # 2. 播放页解析 - 尝试从 HTML 中提取 m3u8
        html = self._txt(url, referer=self.host + '/', timeout=30)
        if html and not self._is_cdndefend_challenge(html):
            real = self._extract_m3u8_from_html(html, url)
            if real:
                # 解析子播放列表（master playlist → child playlist）
                if '.m3u8' in real.lower():
                    real = self._resolve_m3u8_child(real, referer=self.host + '/')
                return {
                    'parse': 0,
                    'playUrl': '',
                    'url': real,
                    'header': play_header,
                    'format': 'application/x-mpegURL',
                    'contentType': 'application/x-mpegURL',
                }

        # 3. 兜底: 交给壳子 WebView 嗅探
        # WebView 需要访问主站播放页，必须带 cdndefend cookie
        webview_header = self._get_header(referer=self.host + '/')
        return {
            'parse': 1,
            'playUrl': '',
            'url': url,
            'header': webview_header,
        }

    # ========== 从播放页 HTML 提取 m3u8 ==========
    def _extract_m3u8_from_html(self, html, page_url=''):
        """从播放页 HTML 中提取 m3u8/mp4 URL

        多级匹配:
        1. player_aaaa JSON
        2. playSource.src = "..." 赋值
        3. playSource 对象字面量 src: "..."
        4. data-src / data-url 属性
        5. 全局 m3u8/mp4 URL 匹配
        """
        # 1. player_aaaa
        real = self._parse_player_aaaa(html)
        if real:
            return real.replace('\\/', '/')

        # 2. playSource.src = "..." 赋值
        src_match = re.search(
            r'playSource\s*(?:\.\s*src|\[\s*[\'"]src[\'"]\s*\])\s*=\s*["\']([^"\']+)["\']',
            html
        )
        if src_match:
            return src_match.group(1).replace('\\/', '/')

        # 3. playSource 对象字面量: { src: "https://...m3u8", ... }
        obj_match = re.search(
            r'src\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            html, re.I
        )
        if obj_match:
            return obj_match.group(1).replace('\\/', '/')

        # 4. data-src / data-url 属性
        data_url = self._match(r'data-(?:src|url)="([^"]+\.m3u8[^"]*)"', html, flags=re.I)
        if data_url:
            return data_url.replace('\\/', '/')

        # 5. 全局匹配 m3u8/mp4
        m = re.search(
            r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            html, re.I
        )
        if m:
            return m.group(1).replace('\\/', '/')

        return ''

    # ========== 解析 player_aaaa ==========
    def _parse_player_aaaa(self, html):
        idx = html.find('player_aaaa')
        if idx < 0:
            return ''

        start = html.find('{', idx)
        if start < 0:
            return ''

        depth = 0
        end = start
        for i in range(start, len(html)):
            if html[i] == '{':
                depth += 1
            elif html[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        json_str = html[start:end]
        try:
            data = json.loads(json_str)
            url = data.get('url', '')
            encrypt = data.get('encrypt', 0)

            if encrypt == 0:
                return url
            elif encrypt in [1, 2]:
                try:
                    return base64.b64decode(url).decode('utf-8')
                except Exception:
                    return ''
            return url
        except Exception:
            return self._match(r'"url"\s*:\s*"([^"]+)"', json_str)

    # ========== 直链检测 ==========
    def _is_direct_media(self, url):
        url = (url or '').lower()
        return '.m3u8' in url or '.mp4' in url or '.flv' in url or '.mkv' in url

    # ========== 解析子 m3u8（Exo 兼容）==========
    def _resolve_m3u8_child(self, m3u8_url, referer=''):
        """解析 master playlist，返回子播放列表 URL

        使用干净的 header（不含 cdndefend cookie）请求外部 CDN。
        """
        ref = referer or self.host + '/'
        headers = {
            'User-Agent': self.UA,
            'Referer': ref,
        }
        try:
            rsp = self.fetch(m3u8_url, headers=headers, timeout=20)
            try:
                rsp.encoding = 'utf-8'
            except Exception:
                pass
            text = rsp.text
        except Exception:
            return m3u8_url

        if not text or '#EXTM3U' not in text:
            return m3u8_url
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                for nxt in lines[i + 1:]:
                    if nxt and not nxt.startswith('#'):
                        return urljoin(m3u8_url, nxt)
        return m3u8_url

    # ========== 本地代理兜底 ==========
    def localProxy(self, param):
        return [200, 'text/plain', b'', '']
