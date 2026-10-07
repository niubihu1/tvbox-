# coding=utf-8
# QQ群：807916734
"""
目标站: 新影视 (2009711.com)
模板: 影视聚合搜索 / 爬虫播放
站点类型: 影视聚合
核心逻辑: 解析首页/分类/详情/播放页 HTML，从播放页 JS 中提取真实 m3u8 直链
"""
import re
import sys
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://www.2009711.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"

    # ========== 工具方法 ==========
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url, url)
        return url

    def _extract_vod_items(self, html):
        """
        从 HTML 中提取 .vod-item 视频列表（首页/分类/搜索/推荐通用）
        """
        videos = []
        items = re.findall(
            r'<li class="vod-item">(.*?)</li>',
            html, re.DOTALL
        )
        seen = set()
        for item in items:
            link_match = re.search(r'<a[^>]*href="/vod/detail/id/(\d+)\.html"[^>]*>', item)
            if not link_match:
                continue
            vid = link_match.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            title_match = re.search(r'<div class="vod-title">\s*([^<]*?)\s*</div>', item)
            name = title_match.group(1).strip() if title_match else vid

            pic = ""
            pic_match = re.search(r'<img[^>]*src="([^"]*)"', item)
            if pic_match:
                pic = pic_match.group(1).strip()
            else:
                pic_match = re.search(r'<img[^>]*data-src="([^"]*)"', item)
                if pic_match:
                    pic = pic_match.group(1).strip()
            if pic and (pic.startswith("data:image") or pic.endswith("placeholder.svg")):
                pic = ""

            remark = ""
            remark_match = re.search(r'<span class="vod-remarks">([^<]*)</span>', item)
            if remark_match:
                remark = remark_match.group(1).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) if pic else self.default_pic,
                "vod_remarks": remark
            })
        return videos

    def _extract_fallback(self, html):
        """兜底解析：匹配所有 /vod/detail/id/ 链接块"""
        videos = []
        seen = set()
        items = re.findall(
            r'<a[^>]*href="/vod/detail/id/(\d+)\.html"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        for vid, block in items:
            if vid in seen:
                continue
            seen.add(vid)

            name = ""
            for pattern in [r'alt="([^"]*)"', r'title="([^"]*)"', r'<div[^>]*class="[^"]*title[^"]*"[^>]*>([^<]*)</div>']:
                m = re.search(pattern, block)
                if m:
                    name = m.group(1).strip()
                    break
            if not name:
                name = vid

            pic = ""
            for attr in ['data-src', 'data-original', 'src']:
                m = re.search(r'<img[^>]*' + attr + r'="([^"]*)"', block)
                if m:
                    pic = m.group(1).strip()
                    break
            if pic and (pic.startswith("data:image") or pic.endswith("placeholder.svg")):
                pic = ""

            remark = ""
            m = re.search(r'<span[^>]*class="[^"]*remark[^"]*"[^>]*>([^<]*)</span>', block)
            if m:
                remark = m.group(1).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) if pic else self.default_pic,
                "vod_remarks": remark
            })
        return videos

    def _merge_videos(self, *video_lists):
        """合并多个视频列表，按 vod_id 去重"""
        seen = set()
        result = []
        for videos in video_lists:
            for v in videos:
                vid = v.get("vod_id")
                if vid and vid not in seen:
                    seen.add(vid)
                    result.append(v)
        return result

    # ========== 首页 ==========
    def homeContent(self, filter):
        categories = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "连续剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "30", "type_name": "短剧"},
        ]
        resp = self.fetch(self.site_url + "/", headers=self.headers)
        videos = []
        if resp:
            v1 = self._extract_vod_items(resp.text)
            v2 = self._extract_fallback(resp.text)
            videos = self._merge_videos(v1, v2)
        return {"class": categories, "list": videos[:30], "filters": {}}

    def homeVideoContent(self):
        return self.homeContent(False)

    # ========== 分类 ==========
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        limit = 30

        if page == 1:
            url = f"{self.site_url}/vod/show/id/{tid}.html"
        else:
            url = f"{self.site_url}/vod/show/id/{tid}/page/{page}.html"

        resp = self.fetch(url, headers=self.headers)
        videos = []
        if resp:
            v1 = self._extract_vod_items(resp.text)
            v2 = self._extract_fallback(resp.text)
            videos = self._merge_videos(v1, v2)

        # ===== 分页逻辑修复 =====
        pagecount = page + 1
        total = 0

        if resp:
            html = resp.text
            # 提取所有分页链接中的页码，取最大值
            page_matches = re.findall(r'/vod/show/id/\d+/page/(\d+)\.html', html)
            if page_matches:
                max_page = max(int(p) for p in page_matches)
                pagecount = max(pagecount, max_page)

            # 从"共XX页"文本提取
            m = re.search(r'共\s*(\d+)\s*页', html)
            if m:
                pagecount = max(pagecount, int(m.group(1)))

            # 如果当前页有数据，保守允许继续加载
            if len(videos) >= limit:
                pagecount = max(pagecount, page + 1)

            # 如果当前页没有数据且不是第一页，说明已到底
            if not videos and page > 1:
                pagecount = page

            total = pagecount * limit

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total
        }

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        limit = 30
        encoded = urllib.parse.quote(key)
        url = f"{self.site_url}/vod/search.html?wd={encoded}"
        if page > 1:
            url += f"&page={page}"

        resp = self.fetch(url, headers=self.headers)
        videos = []
        pagecount = page + 1
        total = 0

        if resp:
            html = resp.text
            v1 = self._extract_vod_items(html)
            v2 = self._extract_fallback(html)
            videos = self._merge_videos(v1, v2)

            # 提取分页信息
            page_matches = re.findall(r'[?&]page=(\d+)', html)
            if page_matches:
                max_page = max(int(p) for p in page_matches)
                pagecount = max(pagecount, max_page)

            m = re.search(r'共\s*(\d+)\s*页', html)
            if m:
                pagecount = max(pagecount, int(m.group(1)))

            # 如果满页则允许继续
            if len(videos) >= limit:
                pagecount = max(pagecount, page + 1)

            # 如果没数据且不是第一页
            if not videos and page > 1:
                pagecount = page

            total = pagecount * limit

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total
        }

    # ========== 详情 ==========
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0]
        url = f"{self.site_url}/vod/detail/id/{vid}.html"
        resp = self.fetch(url, headers=self.headers)
        if not resp:
            return {"list": []}

        html = resp.text

        # 标题
        name = vid
        title_match = re.search(r'<h1 class="detail-title">([^<]*)</h1>', html)
        if title_match:
            name = title_match.group(1).strip()
        else:
            title_match = re.search(r'<title>([^<]*)</title>', html)
            if title_match:
                name = title_match.group(1).split('_')[0].strip()

        # 封面
        pic = self.default_pic
        pic_match = re.search(r'<div class="detail-cover">\s*<img[^>]*src="([^"]*)"', html, re.DOTALL)
        if pic_match:
            pic = self._fix_url(pic_match.group(1))
        else:
            pic_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            if pic_match:
                pic = self._fix_url(pic_match.group(1))

        # 简介
        content = ""
        desc_match = re.search(r'<div class="detail-desc">\s*<p>([^<]*)</p>', html, re.DOTALL)
        if desc_match:
            content = desc_match.group(1).strip()
        else:
            desc_match = re.search(r'<div class="desc-content">\s*([^<]*?)\s*</div>', html, re.DOTALL)
            if desc_match:
                content = desc_match.group(1).strip()

        # 年份、地区、导演、主演
        year = ""
        area = ""
        director = ""
        actor = ""

        meta_items = re.findall(
            r'<div class="meta-item">\s*<span class="meta-label">([^<]*)</span>(.*?)</div>',
            html, re.DOTALL
        )
        for label, value in meta_items:
            label = label.strip().replace('：', '').replace(':', '')
            value = re.sub(r'<[^>]+>', '', value).strip()
            if label == "年份":
                year = value
            elif label == "地区":
                area = value
            elif label == "导演":
                director = value
            elif label == "主演":
                actor = value

        # 播放源名称
        source_tabs = re.findall(
            r'<div class="source-tab[^"]*" data-source="(\d+)"[^>]*>.*?<span>([^<]*)</span>.*?</div>',
            html, re.DOTALL
        )

        # 播放列表
        play_sources = {}
        eplist = re.findall(
            r'<a[^>]*href="/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html"[^>]*>([^<]*)</a>',
            html
        )
        for v, s, e, ep_name in eplist:
            ep_name = ep_name.strip()
            if not ep_name or ep_name == "立即播放":
                continue
            sid = int(s)
            if sid not in play_sources:
                play_sources[sid] = []
            play_page = f"{self.site_url}/vod/play/id/{v}/sid/{s}/nid/{e}.html"
            play_sources[sid].append(f"{ep_name}${play_page}")

        play_from = []
        play_url = []
        for sid in sorted(play_sources.keys()):
            source_name = f"线路{sid}"
            for tab_sid, tab_name in source_tabs:
                if int(tab_sid) == sid:
                    source_name = tab_name.strip()
                    break
            play_from.append(source_name)
            play_url.append("#".join(play_sources[sid]))

        if not play_from:
            play_from = ["默认线路"]
            play_url = [f"播放${url}"]

        result = [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_play_from": '$$$'.join(play_from),
            "vod_play_url": '$$$'.join(play_url)
        }]
        return {"list": result}

    # ========== 播放 ==========
    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if "$" in id:
            play_url = id.split("$")[-1]
        play_url = self._fix_url(play_url)

        # 如果已经是直链
        if '.m3u8' in play_url or '.mp4' in play_url:
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.site_url + "/",
                }
            }

        # 从播放页提取真实 m3u8
        try:
            resp = self.fetch(play_url, headers=self.headers)
            if resp:
                html = resp.text
                # 匹配 var url = '...m3u8...';
                m3u8_match = re.search(r"var\s+url\s*=\s*['\"]([^'\"]+)['\"]", html)
                if m3u8_match:
                    real_url = self._fix_url(m3u8_match.group(1))
                    if '.m3u8' in real_url or '.mp4' in real_url:
                        return {
                            "parse": 0,
                            "url": real_url,
                            "header": {
                                'User-Agent': self.headers['User-Agent'],
                                'Referer': self.site_url + "/",
                            }
                        }
                # 备选：匹配 DPlayer video.url 字符串
                dp_match = re.search(r"video:\s*\{[^}]*url:\s*['\"]([^'\"]+)['\"]", html)
                if dp_match:
                    real_url = self._fix_url(dp_match.group(1))
                    if '.m3u8' in real_url or '.mp4' in real_url:
                        return {
                            "parse": 0,
                            "url": real_url,
                            "header": {
                                'User-Agent': self.headers['User-Agent'],
                                'Referer': self.site_url + "/",
                            }
                        }
        except Exception:
            pass

        return {
            "parse": 1,
            "url": play_url,
            "header": self.headers
        }
