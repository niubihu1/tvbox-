# -*- coding: utf-8 -*-
# QQ群：807916734 @Easy
"""FreeOK (freeok.in) dr_py source.

站点: https://www.freeok.in (MacCMS V10 + MX 主题)

"""

import base64
import hashlib
import html as html_lib
import json
import re
import sys
import time
import urllib.parse
import random

import requests
import urllib3

sys.path.append('..')
from base.spider import Spider  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):
    HOST = 'https://www.freeok.in'
    PAGE_SIZE = 40

    # 分类明确支持流识别
    searchable = True
    filterable = False
    quickSearch = True
    title = 'FreeOK'
    lang = 'zh'
    filters = {}

    DEFAULT_CLASSES = (
        ('电影', '/vodshow/id/dianying.html'),
        ('剧集', '/vodshow/id/juji.html'),
        ('动漫', '/vodshow/id/dongman.html'),
        ('综艺', '/vodshow/id/zongyi.html'),
        ('爽剧', '/vodshow/id/shuangju.html'),
    )

    # robot.php / Decode2 共用静态字符表
    STATIC = "PXhw7UT1B0a9kQDKZsjIASmOezxYG4CHo5Jyfg2b8FLpEvRr3WtVnlqMidu6cN"

    UA_MOBILE = (
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) '
        'Version/17.5 Mobile/15E148 Safari/604.1'
    )

    def __init__(self):
        self.host = self.HOST
        self.ext = ''
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.UA_MOBILE, 'Referer': self.HOST + '/'})
        self.proxies = {}
        self.play_cache = {}
        self.classes = [
            {'type_name': name, 'type_id': path}
            for name, path in self.DEFAULT_CLASSES
        ]

    # ------------------------------------------------------------- 基础
    def getName(self):
        return 'FreeOK'

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        self.ext = extend or ''
        return None

    def init(self, extend=''):
        self.setExtendInfo(extend if extend else self.ext)
        return None

    def homeLayout(self):
        return 0

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        value = str(url or '').lower()
        path = urllib.parse.urlparse(value).path
        return any(m in path or m in value for m in ('.m3u8', '.mp4', '.m4v', '.flv', '.webm', '.ts'))

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def log(self, *args):
        try:
            super().log(*args)
        except Exception:
            pass

    # ------------------------------------------------------- robot 过验证
    @classmethod
    def _robot_encrypt(cls, text):
        out = []
        for ch in text:
            idx = cls.STATIC.find(ch)
            code = ch if idx == -1 else cls.STATIC[(idx + 3) % 62]
            out.append(cls.STATIC[random.randint(0, 61)] + code + cls.STATIC[random.randint(0, 61)])
        return base64.b64encode(''.join(out).encode('utf-8')).decode('ascii')

    def _fetch(self, url, referer=None):
        """GET 页面；若命中 robot.php 验证页则自动过验证后重取。"""
        headers = {}
        if referer:
            headers['Referer'] = referer
        resp = self.session.get(url, headers=headers, timeout=20, verify=False)
        text = resp.text or ''
        if resp.status_code == 404 or resp.status_code >= 500:
            raise RuntimeError('http %s' % resp.status_code)
        if 'robot' in text.lower():
            ts = str(int(time.time()))
            token_plain = base64.b64encode(ts.encode('utf-8')).decode('ascii')
            host = url.split('/')[0] + '//' + url.split('/')[2]
            data = {
                'value': self._robot_encrypt(url),
                'token': self._robot_encrypt(token_plain),
            }
            self.session.post(host + '/robot.php', data=data, timeout=20, verify=False)
            resp = self.session.get(url, headers=headers, timeout=20, verify=False)
            text = resp.text or ''
        if len(text) < 1000:
            raise RuntimeError('page too short %d' % len(text))
        return resp

    # ----------------------------------------------------------- 首页
    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': self.filters}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            resp = self._fetch(self.host + '/')
            return {'list': self._parse_cards(resp.text, page_url=self.host + '/')}
        except Exception as error:
            self.log('FreeOK home failed: %s' % error)
            return {'list': []}

    # ----------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        try:
            page_url = self._category_url(tid, page)
            resp = self._fetch(page_url)
            if resp is None:
                raise RuntimeError('category page unavailable')
            videos = self._parse_cards(resp.text, page_url=resp.url or page_url)
            page_count = self._page_count(resp.text)
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': len(videos) or self.PAGE_SIZE,
                'total': (page_count * (len(videos) or self.PAGE_SIZE)) if page_count else len(videos),
            }
        except Exception as error:
            self.log('FreeOK category failed: %s' % error)
            return {
                'list': [],
                'page': page,
                'pagecount': page,
                'limit': self.PAGE_SIZE,
                'total': 0,
            }

    def _category_url(self, tid, page):
        tid = str(tid or '').strip()
        if tid.startswith('http'):
            path = urllib.parse.urlparse(tid).path
        elif tid.startswith('/'):
            path = tid
        else:
            path = '/vodshow/id/%s.html' % tid
        if page <= 1:
            return self.host + path
        path = path.replace('.html', '/page/%d.html' % page)
        return self.host + path

    @staticmethod
    def _page_count(text):
        pages = re.findall(r'href="[^"]*page/(\d+)\.html"', text)
        nums = [int(n) for n in pages if n.isdigit()]
        return max(nums) if nums else 0

    # ----------------------------------------------------------- 详情
    def detailContent(self, ids):
        raw_id = str(ids[0] if ids else '').strip()
        if not raw_id:
            return {'list': []}
        try:
            detail_url = self._detail_url(raw_id)
            resp = self._fetch(detail_url)
            text = resp.text
            title = self._clean(re.search(r'<h1[^>]*>\s*(?:<a[^>]*>)?([^<]+?)(?:</a>)?\s*</h1>', text))
            title = title or self._clean(re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', text))
            if not title:
                return {'list': []}

            pic = ''
            m = re.search(r'<img[^>]+data-original="([^"]+)"', text)
            if m:
                pic = html_lib.unescape(m.group(1))

            year = area = vod_type = ''
            tags = re.findall(r'<div class="module-info-tag-link">\s*<a[^>]*title="([^"]*)"[^>]*>([^<]*)</a>', text)
            tag_vals = []
            for _, t in tags:
                t = t.strip()
                if t and t != '/':
                    tag_vals.append(t)
            if len(tag_vals) > 0:
                year = tag_vals[0] if re.fullmatch(r'\d{4}', tag_vals[0]) else ''
            if len(tag_vals) > 1:
                area = tag_vals[1]
            if len(tag_vals) > 2:
                vod_type = tag_vals[2]
            if not vod_type:
                m = re.search(r'href="/vodshow/class/([^/"]+)/id/', text)
                if m:
                    vod_type = urllib.parse.unquote(m.group(1))

            director = self._clean(re.search(
                r'<span class="module-info-item-title">导演：</span>\s*<div class="module-info-item-content">(.*?)</div>',
                text, re.S))
            actor = self._clean(re.search(
                r'<span class="module-info-item-title">主演：</span>\s*<div class="module-info-item-content">(.*?)</div>',
                text, re.S))

            content = ''
            m = re.search(r'class="module-info-introduction-content"[^>]*>(.*?)</div>', text, re.S)
            if m:
                content = self._clean(m.group(1)) or title

            from_list, url_list = self._playlists(text)
            if not url_list:
                return {'list': []}

            vod = {
                'vod_id': detail_url,
                'vod_name': title,
                'vod_pic': pic,
                'type_name': vod_type,
                'vod_year': year,
                'vod_area': area,
                'vod_actor': actor,
                'vod_director': director,
                'vod_remarks': '',
                'vod_content': content,
                'vod_play_from': '$$$'.join(from_list),
                'vod_play_url': '$$$'.join(url_list),
            }
            return {'list': [vod]}
        except Exception as error:
            self.log('FreeOK detail failed: %s' % error)
            return {'list': []}

    def _detail_url(self, raw_id):
        m = re.search(r'/vod/(\d+)\.html', raw_id)
        if m:
            return self.host + '/vod/%s.html' % m.group(1)
        m = re.search(r'(\d+)', raw_id)
        if m:
            return self.host + '/vod/%s.html' % m.group(1)
        return self.host + raw_id

    @staticmethod
    def _playlists(text):
        """解析多线路播放列表，返回 (源名列表, 集串列表)。
        每个 source tab(data-dropdown-value) 与 id="panel1" 区块一一对应。
        """
        part = text
        i = part.find('y-playList')
        if i >= 0:
            part = part[i:]
        sources = re.findall(r'data-dropdown-value="([^"]+)"', part)
        sources = [s for s in sources if s.strip()]

        # 每个播放区块: id="panel1" ... </div> 闭合；取其中所有播放链接
        blocks = re.findall(
            r'<div class="module-play-list">.*?</div>\s*</div>\s*</div>', part, re.S)
        play = []
        for block in blocks:
            eps = re.findall(
                r'<a[^>]+class="module-play-list-link"[^>]+href="(/play/[^"]+\.html)"[^>]*>\s*<span>([^<]*)</span>',
                block)
            if eps:
                play.append(eps)

        # 兜底: 未按块匹配时按顺序收集
        if not play:
            all_eps = re.findall(
                r'<a[^>]+class="module-play-list-link"[^>]+href="(/play/[^"]+\.html)"[^>]*>\s*<span>([^<]*)</span>',
                part)
            if all_eps:
                play = [all_eps]

        from_list = []
        url_list = []
        for idx, eps in enumerate(play):
            if not eps:
                continue
            src = sources[idx] if idx < len(sources) else '线路%d' % (idx + 1)
            from_list.append(src)
            url_list.append('#'.join('%s$%s' % (name, href) for href, name in eps))
        return from_list, url_list

    # ----------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg='1'):
        page = max(1, int(pg or 1))
        keyword = str(key or '').strip()
        if not keyword:
            return {'list': [], 'page': page, 'pagecount': page, 'limit': self.PAGE_SIZE, 'total': 0}
        try:
            url = self.host + '/vodsearch.html?wd=' + urllib.parse.quote(keyword)
            resp = self._fetch(url)
            videos = self._parse_search(resp.text)
            if videos:
                return {'list': videos, 'page': page}
        except Exception as error:
            self.log('FreeOK search failed: %s' % error)
        return {'list': [], 'page': page}

    # ----------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        value = str(id or '').strip()
        if '@Headers=' in value:
            value = value.split('@Headers=', 1)[0].strip()
        if '$' in value and not value.startswith('http'):
            value = value.rsplit('$', 1)[-1].strip()
        if value.startswith('//'):
            value = 'https:' + value
        # 已经是直链
        if value.startswith('http') and self.isVideoFormat(value):
            result = {'parse': 0, 'playUrl': '', 'url': value, 'header': self._media_headers(value)}
            if '.m3u8' in value.lower():
                result['type'] = 'm3u8'
            return result

        play_url = self._play_url(value)
        if not play_url:
            return {'parse': 1, 'playUrl': '', 'url': self.host + '/', 'header': self._page_headers(self.host + '/')}
        try:
            if play_url in self.play_cache:
                cfg = self.play_cache[play_url]
            else:
                resp = self._fetch(play_url)
                cfg = self._parse_player(resp.text)
                self.play_cache[play_url] = cfg
            if not cfg or not cfg.get('url'):
                raise ValueError('player_aaaa url not found')

            api = self.session.post(
                self.host + '/jx/api.php',
                data={'vid': cfg['url']},
                headers={'Referer': self.host + '/jx/player.php'},
                timeout=20,
                verify=False,
            )
            if api.status_code != 200:
                raise ValueError('jx api %s' % api.status_code)
            body = api.json()
            data = body.get('data') or {}
            media = self._decode_media(data)
            if not media:
                raise ValueError('media url empty')
            result = {'parse': 0, 'playUrl': '', 'url': media, 'header': self._media_headers(media)}
            if '.m3u8' in media.lower():
                result['type'] = 'm3u8'
            return result
        except Exception as error:
            self.log('FreeOK play failed: %s' % error)
            return {'parse': 1, 'playUrl': '', 'url': play_url, 'header': self._page_headers(play_url)}

    def _play_url(self, value):
        if not value:
            return ''
        if value.startswith('http'):
            return value
        if value.startswith('/play/'):
            return self.host + value
        m = re.search(r'^(\d+)-(\d+)-(\d+)$', value)
        if m:
            return '%s/play/%s-%s-%s.html' % (self.host, m.group(1), m.group(2), m.group(3))
        m = re.search(r'(\d+)-(\d+)-(\d+)', value)
        if m:
            return '%s/play/%s-%s-%s.html' % (self.host, m.group(1), m.group(2), m.group(3))
        return ''

    @staticmethod
    def _parse_player(text):
        i = text.find('var player_aaaa=')
        if i < 0:
            i = text.find('player_aaaa=')
        if i < 0:
            return {}
        start = text.find('{', i)
        depth = 0
        in_str = False
        esc = False
        for j in range(start, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:j + 1])
                        except Exception:
                            return {}
        return {}

    # ------------------------------------------------------- 解密 URL
    @staticmethod
    def _custom_str_decode(s):
        """Decode1 第一步: md5('test') 异或 + base64 再解 {表0}/{表1}/{密文}"""
        key = hashlib.md5(b'test').hexdigest()
        raw = base64.b64decode(s)
        xored = ''.join(chr(raw[i] ^ ord(key[i % len(key)])) for i in range(len(raw)))
        return base64.b64decode(xored).decode('utf-8', 'replace')

    @classmethod
    def _decode_sign(cls, enc):
        """Decode1: 置换表 sign 还原直链 (urlmode=1 -> mp4)"""
        try:
            parts = cls._custom_str_decode(enc).split('/')
            if len(parts) < 3:
                return ''
            seq_a = json.loads(base64.b64decode(parts[1]).decode('utf-8'))  # indexOf 表
            seq_b = json.loads(base64.b64decode(parts[0]).decode('utf-8'))  # 取值表
            suffix = base64.b64decode('/'.join(parts[2:])).decode('utf-8', 'replace')
            out = []
            for ch in suffix:
                if re.match(r'^[a-zA-Z]+$', ch) and ch in seq_b:
                    out.append(seq_b[seq_a.index(ch)])
                else:
                    out.append(ch)
            return ''.join(out)
        except Exception:
            return ''

    @classmethod
    def _decode2(cls, enc):
        """Decode2: atob -> 每3字符取第2个 -> STATIC[(idx+59)%62] (urlmode=2 -> m3u8)"""
        try:
            s = base64.b64decode(enc).decode('latin-1', 'replace')
            out = []
            i = 1
            while i < len(s):
                ch = s[i]
                idx = cls.STATIC.find(ch)
                out.append(ch if idx == -1 else cls.STATIC[(idx + 59) % 62])
                i += 3
            return ''.join(out)
        except Exception:
            return ''

    def _decode_media(self, data):
        enc = str(data.get('url') or '').strip()
        if not enc:
            return ''
        mode = data.get('urlmode')
        if mode == 1:
            return self._decode_sign(enc)
        if mode == 2:
            return self._decode2(enc)
        # 未知 urlmode: 尝试两种
        r1 = self._decode_sign(enc)
        if r1.startswith('http'):
            return r1
        r2 = self._decode2(enc)
        if r2.startswith('http'):
            return r2
        return r1 or r2

    # ------------------------------------------------------- 卡片解析
    @staticmethod
    def _parse_cards(text, page_url=''):
        videos = []
        for m in re.finditer(
                r'<a href="(/vod/\d+\.html)" title="([^"]+)" class="module-poster-item module-item">'
                r'.*?<div class="module-item-note">([^<]*)</div>'
                r'.*?<img[^>]+data-original="([^"]+)"'
                r'.*?<div class="module-poster-item-title">([^<]*)</div>',
                text, re.S):
            href, title, note, pic, _ = m.groups()
            videos.append({
                'vod_id': href,
                'vod_name': html_lib.unescape(title),
                'vod_pic': html_lib.unescape(pic),
                'vod_remarks': html_lib.unescape(note).strip(),
            })
            if len(videos) >= 60:
                break
        return videos

    @staticmethod
    def _parse_search(text):
        videos = []
        for m in re.finditer(
                r'<div class="module-card-item module-item">'
                r'.*?<a href="(/vod/\d+\.html)" class="module-card-item-poster">'
                r'.*?<div class="module-item-note">([^<]*)</div>'
                r'.*?<img[^>]+data-original="([^"]+)"'
                r'.*?<strong>([^<]*)</strong>',
                text, re.S):
            href, note, pic, title = m.groups()
            videos.append({
                'vod_id': href,
                'vod_name': html_lib.unescape(title),
                'vod_pic': html_lib.unescape(pic),
                'vod_remarks': html_lib.unescape(note).strip(),
            })
            if len(videos) >= 40:
                break
        return videos

    # ------------------------------------------------------- 工具
    @staticmethod
    def _clean(value):
        if value is None:
            return ''
        if isinstance(value, re.Match):
            value = value.group(1)
        value = re.sub(r'<[^>]+>', '', str(value))
        value = html_lib.unescape(value)
        value = re.sub(r'[\s\u3000]+', ' ', value).strip(' /|・')
        return value

    def _media_headers(self, url):
        headers = {'User-Agent': self.UA_MOBILE}
        if '.m3u8' in url.lower():
            headers['Referer'] = self.host + '/'
        return headers

    def _page_headers(self, url):
        return {'User-Agent': self.UA_MOBILE, 'Referer': self.host + '/'}
