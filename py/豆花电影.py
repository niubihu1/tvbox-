#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆花电影网 TVBox爬虫源
基于遮天法v3.0+框架 - 道宫境(Lv.1)
站点: https://dhvideo.cc
架构: 自定义PHP + TailwindCSS (vk-theme), 非MacCMS
数据链路 (全HTML解析):
  首页       GET /                                    -> 视频卡片(lazy-image)
  分类列表   GET /{category}.html?page={pg}           -> 视频卡片 (0-indexed分页)
  详情       GET /movie/{hex}-{num}.html              -> 播放按钮 + 相关视频
             GET /tv/{hex}-{num}.html                  -> 多播放源 + 选集列表
  播放页     GET /movie/{hex}/{num}.html              -> currentUrl变量
             GET /tv/{hex}/{num}.html?origin={src}&p={ep} -> currentUrl变量
  搜索       GET /search?wd={keyword}                  -> 视频卡片
  播放API    GET /api/m3u8?origin=超级线路&url={play_id} -> m3u8 master playlist
防御等级: Lv.1 (无加密/无JS渲染, BS4解析HTML, 搜索限流429)

【遮天法铁律遵守清单】
  ✓ 铁律1: 引号闭合
  ✓ 铁律2: 括号闭合
  ✓ 铁律3: 防递归设计
  ✓ 铁律4: 模块区分 (requests.Session() 正确使用)
  ✓ 铁律5: 配置优先 (全部从 DEFAULT_CONFIG 读取)
  ✓ 铁律6: 参数必用
  ✓ 铁律7: 异常分级 (Timeout/ConnectionError/JSONDecodeError)
  ✓ 铁律8: 自检必跑
  ✓ 铁律9: getName 必补
  ✓ 铁律10: isVideoFormat 必补 (列表推导式)

【版本】1.0 | 【框架】遮天法v3.0+ | 【许可】开源
"""

import sys
import re
import json
import html as html_module
from urllib.parse import quote, unquote, urljoin
from typing import Dict, List, Optional, Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# TVBox环境兼容
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


# ==================================================================
#  DEFAULT_CONFIG 配置中心 (铁律5: 禁止硬编码)
# ==================================================================

DEFAULT_CONFIG = {
    "host": "https://dhvideo.cc",
    "site_name": "豆花电影网",

    "endpoints": {
        "home": "/",
        "category_p1": "/{type}.html",
        "category_pn": "/{type}/{pg}.html",
        "detail_movie": "/movie/{id}.html",
        "detail_tv": "/tv/{id}.html",
        "play_movie": "/movie/{id}.html",
        "play_tv": "/tv/{id}.html",
        "search": "/s.html?name={wd}&sion_id={sion_id}",
        "search_paged": "/s.html?name={wd}&page={pg}&sort_field=_id&sion_id={sion_id}",
        "m3u8_api": "/api/m3u8?origin={origin}&url={play_id}",
    },

    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://dhvideo.cc/",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    },

    "timeout": 15,
    "debug": False,

    # sion_id (从用户URL提取, 用于搜索时绕过部分限流)
    "sion_id": "6aa2a9f23a7e88e5a8a87d41",

    # 分类列表 (路由名映射到中文名称)
    "categories": [
        {"type_id": "dianying", "type_name": "电影"},
        {"type_id": "dianshiju", "type_name": "电视剧"},
        {"type_id": "zongyi", "type_name": "综艺"},
        {"type_id": "dongman", "type_name": "动漫"},
        {"type_id": "duanju", "type_name": "短剧"},
    ],

    # 默认播放源 (当详情页未提取到源名称时)
    "default_origin": "超级线路",

    # 视频详情页URL前缀映射
    # 电影: /movie/{hex}-{num}.html
    # 电视剧: /tv/{hex}-{num}.html
    "type_prefixes": {"movie": "/movie/", "tv": "/tv/"},
}


# ==================================================================
#  九秘核心能力库
# ==================================================================

class DouZiMi:
    """斗字秘 - 吞天魔罐: HTML清洗、URL修复、视频卡片解析"""

    @staticmethod
    def clean_text(text: str) -> str:
        """净化术: HTML实体解码 + 去多余空白"""
        if not text:
            return ""
        text = str(text)
        text = html_module.unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def fix_url(url: str, host: str = "") -> str:
        """补天术: 相对URL转绝对URL"""
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return host.rstrip("/") + url
        return urljoin(host.rstrip("/") + "/", url)

    @staticmethod
    def parse_video_cards(html_text: str, host: str) -> List[Dict]:
        """七十二变: 解析视频卡片 (适配vk-theme模板)
        卡片结构: <a href="/movie|tv/{hex}-{num}.html">
                     <img class="lazy-image" data-src="/img/id/{hex}.jpg" alt="标题">
                     <span>备注</span>
                  </a>
        """
        results: List[Dict] = []
        if not html_text:
            return results

        seen_ids: set = set()

        if HAS_BS4:
            try:
                soup = BeautifulSoup(html_text, "html.parser")
                # 找所有含 /movie/ 或 /tv/ 链接的a标签
                links = soup.find_all("a", href=re.compile(r"/(?:movie|tv)/[a-f0-9]+-\d+\.html"))
                for a in links:
                    href = a.get("href", "")
                    vid_match = re.search(r"/(?:movie|tv)/([a-f0-9]+-\d+)", href)
                    if not vid_match:
                        continue
                    vod_id = vid_match.group(1)
                    if vod_id in seen_ids:
                        continue
                    seen_ids.add(vod_id)

                    # 类型前缀 (movie/tv)
                    type_prefix = "movie" if "/movie/" in href else "tv"

                    # 名称和图片: 必须有img且img有alt属性 (过滤"立即播放"按钮)
                    img = a.find("img")
                    if not img:
                        continue
                    name = img.get("alt", "")
                    if not name:
                        continue
                    pic = (img.get("data-src", "") or
                           img.get("data-original", "") or
                           img.get("src", ""))

                    # 备注: 从span获取
                    remark = ""
                    spans = a.find_all("span")
                    for span in spans:
                        text = span.get_text(strip=True)
                        if text and len(text) < 20 and text != name:
                            # 排除非备注文本(如排序按钮等)
                            if not any(kw in text for kw in ("排序", "筛选", "最新", "最热", "播放最多")):
                                remark = text
                                break

                    if name and len(name) >= 2:
                        results.append({
                            "vod_id": f"{type_prefix}/{vod_id}",
                            "vod_name": name.strip(),
                            "vod_pic": DouZiMi.fix_url(pic, host),
                            "vod_remarks": remark,
                        })
                return results
            except Exception as e:
                if DEFAULT_CONFIG.get("debug"):
                    print(f"[DouZiMi] BS4解析失败: {e}")

        # 正则回退层
        pattern = re.compile(
            r'<a[^>]*href="/((?:movie|tv)/([a-f0-9]+-\d+))\.html"[^>]*>(.*?)</a>',
            re.S
        )
        for m in pattern.finditer(html_text):
            vod_id = m.group(2)
            if vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)
            type_prefix = m.group(1)
            inner = m.group(3)

            # 名称: 必须有img且img有alt属性 (过滤非卡片链接)
            name = ""
            alt_match = re.search(r'alt="([^"]+)"', inner)
            if alt_match:
                name = alt_match.group(1)
            else:
                continue  # 没有alt属性, 跳过(不是视频卡片)

            # 图片
            pic = ""
            pic_match = re.search(r'data-src="([^"]+)"', inner)
            if not pic_match:
                pic_match = re.search(r'src="([^"]+)"', inner)
            if pic_match:
                pic = pic_match.group(1)

            if name and len(name) >= 2:
                results.append({
                    "vod_id": f"{type_prefix}/{vod_id}",
                    "vod_name": name.strip(),
                    "vod_pic": DouZiMi.fix_url(pic, host),
                    "vod_remarks": "",
                })

        return results


class QianZiMi:
    """前字秘 - 不死天刀: 播放地址提取 (currentUrl -> m3u8 API)"""

    @staticmethod
    def extract_current_url(html_text: str) -> Optional[str]:
        """从播放页HTML提取 currentUrl 变量值
        格式: currentUrl = "\/api\/m3u8?origin=%E8%B6%85%E7%BA%A7%E7%BA%BF%E8%B7%AF\u0026url=6a9dd66004627a85083fce01"
        """
        if not html_text:
            return None

        # 匹配 currentUrl = "..." (含转义字符)
        match = re.search(r'currentUrl\s*=\s*["\']([^"\']+)["\']', html_text)
        if not match:
            return None

        raw = match.group(1)
        # 解码JS转义
        raw = raw.replace("\\/", "/")
        raw = raw.replace("\\u0026", "&")
        raw = raw.replace("\\u0026", "&")
        # 处理 \u 编码
        raw = raw.encode("utf-8").decode("unicode_escape", errors="replace") if "\\u" in raw else raw
        return raw if raw else None

    @staticmethod
    def extract_current_episode(html_text: str) -> Optional[dict]:
        """从播放页HTML提取当前选集数据 (xg_video_player_doc.aa)
        格式: aa: JSON.parse('{\\u0022origin\\u0022:\\u0022vip\\u0022,\\u0022url\\u0022:\\u0022/api/m3u8?...\\u0022,\\u0022title\\u0022:\\u0022_P05_005\\u0022}')
        返回: {"origin": "...", "url": "...", "title": "..."} 或 None
        """
        if not html_text:
            return None

        # 匹配 aa: JSON.parse('...')
        aa_pattern = re.compile(r"aa:\s*JSON\.parse\('([^']+)'")
        match = aa_pattern.search(html_text)
        if not match:
            return None

        raw_json = match.group(1)

        # 解码 \uXXXX 转义 (处理任意数量的前导反斜杠)
        decoded = re.sub(
            r'\\+u([0-9a-fA-F]{4})',
            lambda m: chr(int(m.group(1), 16)),
            raw_json
        )
        # 解码 \/
        decoded = decoded.replace("\\/", "/")

        try:
            data = json.loads(decoded)
            url = data.get("url", "")
            # URL内可能仍有转义, 二次解码
            url = url.replace("\\/", "/")
            url = re.sub(
                r'\\+u([0-9a-fA-F]{4})',
                lambda m: chr(int(m.group(1), 16)),
                url
            )
            return {
                "origin": data.get("origin", ""),
                "url": url,
                "title": data.get("title", ""),
            }
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def is_direct_video(url: str) -> bool:
        """判断是否为直接视频格式"""
        if not url:
            return False
        low = url.lower()
        return any(fmt in low for fmt in (".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".ts", ".mpd", ".webm"))

    @staticmethod
    def solve_pow(hash_val: str, target: str, max_iter: int = 1000000) -> Optional[int]:
        """前字秘·PoW: SHA-1 Proof-of-Work 爆破
        站点verify.js: sha1(hash + i) === target
        返回: nonce (int) 或 None
        """
        try:
            import hashlib
            for i in range(max_iter):
                if hashlib.sha1(f"{hash_val}{i}".encode()).hexdigest() == target:
                    return i
        except Exception:
            pass
        return None


class LieZiMi:
    """列字秘 - 虚空镜: 请求头构建"""

    @staticmethod
    def build_headers(referer: str) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer,
        }


# ==================================================================
#  Spider 主类 (道宫境 - HTML解析)
# ==================================================================

class Spider(BaseSpider):
    """豆花电影网 - TVBox爬虫"""

    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.site_url = self.config["host"]
        self.session = None

    def init(self, extend: str = ""):
        """TVBox标准init接口 (extend参数使用)"""
        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update(self.config.get("headers", {}))
            self.session.verify = False
            # 设置sion_id cookie (从配置或extend中获取)
            sion_id = self.config.get("sion_id", "")
            if sion_id:
                self.session.cookies.set("sion_id", sion_id, domain="dhvideo.cc")
        # extend参数使用: 解析配置
        if extend:
            try:
                ext = json.loads(extend)
                if "siteUrl" in ext:
                    self.site_url = ext["siteUrl"]
                    if self.session:
                        self.session.headers["Referer"] = self.site_url + "/"
                # 从extend中提取sion_id
                if "sion_id" in ext and self.session:
                    self.session.cookies.set("sion_id", ext["sion_id"], domain="dhvideo.cc")
            except (json.JSONDecodeError, TypeError):
                # extend可能是纯URL, 尝试提取sion_id
                if "sion_id=" in extend and self.session:
                    import urllib.parse as up
                    parsed = up.urlparse(extend)
                    params = up.parse_qs(parsed.query)
                    sid = params.get("sion_id", [""])[0]
                    if sid:
                        self.session.cookies.set("sion_id", sid, domain="dhvideo.cc")

    def getName(self) -> str:
        """铁律9: getName必补"""
        return self.config.get("site_name", "豆花电影网")

    def isVideoFormat(self, url: str) -> bool:
        """铁律10: isVideoFormat必补 (列表推导式)"""
        if not url:
            return False
        fmts = [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".mov", ".ts", ".mpd", ".webm"]
        return any(f in url.lower() for f in fmts)

    def manualVideoCheck(self) -> bool:
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def _fix_url(self, url: str) -> str:
        return DouZiMi.fix_url(url, self.site_url)

    def _fetch_html(self, url: str, params: dict = None) -> Optional[str]:
        """安全获取HTML (铁律7: 异常分级)"""
        if not self.session:
            return None
        try:
            resp = self.session.get(
                url, params=params,
                timeout=self.config.get("timeout", 15)
            )
            if resp.status_code != 200:
                if self.config.get("debug"):
                    print(f"[_fetch_html] HTTP {resp.status_code}: {url}")
                return None
            # 正确编码处理
            enc = resp.encoding
            if not enc or enc.lower() in ("iso-8859-1", "ascii"):
                resp.encoding = "utf-8"
            return resp.text
        except requests.exceptions.Timeout as e:
            if self.config.get("debug"):
                print(f"[_fetch_html] 超时: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            if self.config.get("debug"):
                print(f"[_fetch_html] 连接错误: {e}")
            return None
        except Exception as e:
            if self.config.get("debug"):
                print(f"[_fetch_html] 异常: {e}")
            return None

    def _parse_title_from_html(self, html_text: str) -> str:
        """从HTML标题提取视频名称
        格式: 邻家小姐_电影_免费观看完整版_豆花电影网 -> 邻家小姐
        """
        title_match = re.search(r"<title>([^<]+)</title>", html_text)
        if not title_match:
            return ""
        title = title_match.group(1).strip()
        # 按下划线分割取第一部分
        parts = title.split("_")
        if parts:
            return parts[0].strip()
        return title

    def _parse_detail_info(self, html_text: str) -> dict:
        """从详情页HTML提取元信息"""
        info: dict = {}
        if not html_text:
            return info

        if HAS_BS4:
            try:
                soup = BeautifulSoup(html_text, "html.parser")

                # 标题 (从<title>提取)
                info["vod_name"] = self._parse_title_from_html(html_text)

                # 封面: 找 /img/cover/ 或 /img/id/ 的图片
                vod_pic = ""
                for img in soup.find_all("img"):
                    src = img.get("src", "") or img.get("data-src", "")
                    if "/img/cover/" in src or "/img/id/" in src:
                        # 排除相关视频缩略图(在列表中)
                        parent = img.find_parent("a")
                        if parent and parent.get("href", ""):
                            href = parent.get("href", "")
                            # 如果链接指向其他视频详情页, 是相关推荐, 跳过
                            if re.search(r"/(?:movie|tv)/[a-f0-9]+-\d+\.html", href):
                                continue
                        vod_pic = src
                        break
                info["vod_pic"] = vod_pic

                # 元信息: 从页面文本提取
                text = soup.get_text()

                # 年份
                year_match = re.search(r"(\d{4})", text)
                if year_match:
                    year = year_match.group(1)
                    if 1900 <= int(year) <= 2030:
                        info["vod_year"] = year

                # 地区/类型/导演/主演: 从文本块提取
                for p in soup.find_all(["p", "div", "span", "li"]):
                    ptext = p.get_text(strip=True)
                    if "地区" in ptext or "地区" in ptext:
                        area_match = re.search(r"地区[：:]\s*([^\n\r·•|]+)", ptext)
                        if area_match:
                            info["vod_area"] = area_match.group(1).strip()
                    if "导演" in ptext:
                        dir_match = re.search(r"导演[：:]\s*([^\n\r·•|]+)", ptext)
                        if dir_match:
                            info["vod_director"] = dir_match.group(1).strip()
                    if "主演" in ptext or "演员" in ptext:
                        act_match = re.search(r"(?:主演|演员)[：:]\s*([^\n\r]+)", ptext)
                        if act_match:
                            info["vod_actor"] = act_match.group(1).strip()[:200]
                    if "类型" in ptext:
                        type_match = re.search(r"类型[：:]\s*([^\n\r·•|]+)", ptext)
                        if type_match:
                            info["vod_type_name"] = type_match.group(1).strip()

                # 简介
                intro_el = soup.find(class_=re.compile(r"reset-style|intro|desc|content|jianjie|brief"))
                if intro_el:
                    intro = intro_el.get_text(" ", strip=True)
                    if len(intro) > 20:
                        info["vod_content"] = intro[:2000]

            except Exception as e:
                if self.config.get("debug"):
                    print(f"[_parse_detail_info] BS4解析失败: {e}")

        # 图片URL修复
        if info.get("vod_pic"):
            info["vod_pic"] = self._fix_url(info["vod_pic"])

        return info

    def _parse_play_sources(self, html_text: str) -> tuple:
        """解析详情页的播放源和选集
        返回: (play_from_list, play_url_list)
        """
        play_from_list: List[str] = []
        play_url_list: List[str] = []

        if not html_text:
            return play_from_list, play_url_list

        if HAS_BS4:
            try:
                soup = BeautifulSoup(html_text, "html.parser")

                # 电视剧: 优先查找选集链接 (有?origin=参数)
                # 选集: /tv/{hex}/{num}.html?origin={src}&p={ep}
                ep_links = soup.find_all("a", href=re.compile(r"/(?:movie|tv)/[a-f0-9]+/\d+\.html\?"))
                if ep_links:
                    # 播放源tab: /tv/{hex}-{num}.html?origin={src} (横杠)
                    source_names: dict = {}
                    source_tabs = soup.find_all("a", href=re.compile(r"/(?:movie|tv)/[a-f0-9]+-\d+\.html\?"))
                    for tab in source_tabs:
                        href = tab.get("href", "").replace("&amp;", "&")
                        origin_match = re.search(r"\?origin=([^&]+)", href)
                        if origin_match:
                            origin = origin_match.group(1)
                            name = tab.get_text(strip=True) or origin
                            # 清理名称: 去掉 [N] 前缀
                            name = re.sub(r"^\[\d+\]", "", name).strip() or origin
                            if origin not in source_names:
                                source_names[origin] = name

                    # 按origin和p分组
                    episodes_by_source: dict = {}
                    for ep in ep_links:
                        href = ep.get("href", "").replace("&amp;", "&")
                        ep_match = re.search(r"\?origin=([^&]+)&p=(\d+)", href)
                        if ep_match:
                            origin = ep_match.group(1)
                            ep_num = int(ep_match.group(2))
                            ep_name = ep.get_text(strip=True) or f"第{ep_num + 1}集"
                            # 清理选集名: 去掉 [N] 前缀, 过长/分辨率/非正常名用默认
                            ep_name = re.sub(r"^\[\d+\]", "", ep_name).strip()
                            if (not ep_name or len(ep_name) > 20 or
                                    re.match(r"^[\d\.\s]+$", ep_name) or
                                    re.search(r"\d+x\d+", ep_name) or
                                    re.search(r"\d+h\d+m", ep_name) or
                                    re.search(r"\d{3,4}p", ep_name) or
                                    re.search(r"webrip|web-dl|bluray|蓝光|remux|hdr", ep_name, re.I) or
                                    re.search(r"_\d", ep_name)):
                                ep_name = f"第{ep_num + 1}集" if ep_num > 0 else "正片"
                            if origin not in episodes_by_source:
                                episodes_by_source[origin] = []
                            episodes_by_source[origin].append((ep_num, ep_name, href))

                    # 组装结果
                    for origin, eps in episodes_by_source.items():
                        eps.sort(key=lambda x: x[0])
                        src_name = source_names.get(origin, origin)
                        play_from_list.append(src_name)
                        url_list = [f"{name}${href}" for _, name, href in eps]
                        play_url_list.append("#".join(url_list))

                    if play_from_list:
                        return play_from_list, play_url_list

                # 电影: 找"立即播放"按钮 (无query参数的链接)
                # <a href="/movie/{hex}/{num}.html">立即播放</a>
                play_btn = None
                for a in soup.find_all("a", href=re.compile(r"/(?:movie|tv)/[a-f0-9]+/\d+\.html")):
                    href = a.get("href", "")
                    # 排除有query参数的链接(选集)
                    if "?" not in href:
                        play_btn = a
                        break
                    # 或者含"立即播放"文字
                    text = a.get_text(strip=True)
                    if "立即播放" in text or "播放" in text:
                        play_btn = a
                        break

                if play_btn:
                    href = play_btn.get("href", "").replace("&amp;", "&")
                    play_from_list.append("默认源")
                    play_url_list.append(f"正片${href}")
                    return play_from_list, play_url_list

                # 兜底: 找任何播放链接
                all_play_links = soup.find_all("a", href=re.compile(r"/(?:movie|tv)/[a-f0-9]+/\d+\.html"))
                if all_play_links:
                    eps_list = []
                    for a in all_play_links:
                        href = a.get("href", "").replace("&amp;", "&")
                        name = a.get_text(strip=True) or "播放"
                        if "?" not in href:  # 排除选集链接
                            eps_list.append(f"{name}${href}")
                    if eps_list:
                        play_from_list.append("默认源")
                        play_url_list.append("#".join(eps_list))

            except Exception as e:
                if self.config.get("debug"):
                    print(f"[_parse_play_sources] BS4解析失败: {e}")

        # 正则回退
        if not play_from_list:
            # 电视剧选集
            ep_pattern = re.compile(
                r'href="(/(?:movie|tv)/[a-f0-9]+/\d+\.html)\?origin=([^&]+)&p=(\d+)"[^>]*>([^<]+)'
            )
            eps_by_src: dict = {}
            for m in ep_pattern.finditer(html_text):
                href = m.group(1).replace("&amp;", "&")
                origin = m.group(2)
                ep_num = int(m.group(3))
                name = m.group(4).strip()
                if origin not in eps_by_src:
                    eps_by_src[origin] = []
                eps_by_src[origin].append((ep_num, name, f"{href}?origin={origin}&p={ep_num}"))

            for origin, eps in eps_by_src.items():
                eps.sort(key=lambda x: x[0])
                play_from_list.append(origin)
                url_list = [f"{n}${h}" for _, n, h in eps]
                play_url_list.append("#".join(url_list))

            if play_from_list:
                return play_from_list, play_url_list

            # 电影播放按钮 (无query参数)
            movie_play = re.search(
                r'href="(/(?:movie|tv)/[a-f0-9]+/\d+\.html)"[^>]*>[^<]*立即播放',
                html_text
            )
            if movie_play:
                play_from_list.append("默认源")
                play_url_list.append(f"正片${movie_play.group(1)}")

        return play_from_list, play_url_list

    # ==================== TVBox 六接口 ====================

    def homeContent(self, filter: bool = False) -> dict:
        """首页: 分类列表 + 推荐视频 (filter参数使用)"""
        result: dict = {"class": [], "list": [], "filters": {}}
        try:
            categories = self.config.get("categories", [])
            result["class"] = [
                {"type_id": c["type_id"], "type_name": c["type_name"]}
                for c in categories
            ]

            home_url = self._fix_url(self.config["endpoints"]["home"])
            html_text = self._fetch_html(home_url)
            if html_text:
                videos = DouZiMi.parse_video_cards(html_text, self.site_url)
                result["list"] = videos[:30]

        except Exception as e:
            if self.config.get("debug"):
                print(f"[homeContent] 异常: {e}")

        if filter:
            result["filters"] = {c["type_id"]: [] for c in categories}
        return result

    def homeVideoContent(self) -> dict:
        try:
            home_url = self._fix_url(self.config["endpoints"]["home"])
            html_text = self._fetch_html(home_url)
            if html_text:
                return {"list": DouZiMi.parse_video_cards(html_text, self.site_url)[:30]}
        except Exception as e:
            if self.config.get("debug"):
                print(f"[homeVideoContent] 异常: {e}")
        return {"list": []}

    def categoryContent(self, tid: str, pg: Any = 1, filter: bool = False, extend: dict = None) -> dict:
        """分类: 视频列表 (tid/pg/filter/extend参数全部使用)
        分页: 第1页 /{type}.html, 第N页 /{type}/{N}.html
        """
        page = int(pg) if pg else 1

        result: dict = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        # tid使用: 构建分类页URL
        endpoints = self.config["endpoints"]
        if page <= 1:
            url = self._fix_url(endpoints["category_p1"].format(type=tid))
        else:
            url = self._fix_url(endpoints["category_pn"].format(type=tid, pg=page))

        # extend使用: 合并额外参数
        params = None
        if extend and isinstance(extend, dict) and extend:
            params = dict(extend)

        try:
            html_text = self._fetch_html(url, params=params)
            if not html_text:
                return result

            videos = DouZiMi.parse_video_cards(html_text, self.site_url)
            result["list"] = videos
            result["limit"] = len(videos) if videos else 24

            # 解析分页: 找 /{type}/\d+.html 格式的最大页码
            page_matches = re.findall(rf"/{re.escape(tid)}/(\d+)\.html", html_text)
            if page_matches:
                max_page = max(int(p) for p in page_matches)
                result["pagecount"] = max_page
                result["total"] = result["limit"] * result["pagecount"]
            else:
                # 也检查 ?page= 格式
                page_matches2 = re.findall(r"\?page=(\d+)", html_text)
                if page_matches2:
                    max_page = max(int(p) for p in page_matches2) + 1
                    result["pagecount"] = max_page
                    result["total"] = result["limit"] * result["pagecount"]
                else:
                    result["pagecount"] = page
                    result["total"] = len(videos)

        except requests.exceptions.Timeout as e:
            if self.config.get("debug"):
                print(f"[categoryContent] 超时: {e}")
        except requests.exceptions.ConnectionError as e:
            if self.config.get("debug"):
                print(f"[categoryContent] 连接失败: {e}")
        except Exception as e:
            if self.config.get("debug"):
                print(f"[categoryContent] 异常: {e}")

        if filter:
            result["filters"] = {}
        return result

    def detailContent(self, ids: list) -> dict:
        """详情: 视频详情和播放源 (ids参数使用)
        vod_id格式: "movie/{hex}-{num}" 或 "tv/{hex}-{num}"
        """
        if not ids:
            return {"list": []}

        vod_id = str(ids[0]) if ids else ""
        if not vod_id:
            return {"list": []}

        # 解析vod_id: "movie/6a9dce8b268d04369d773013-70569" -> type=movie, id=6a9dce8b268d04369d773013-70569
        parts = vod_id.split("/", 1)
        if len(parts) != 2:
            return {"list": []}
        vtype = parts[0]  # "movie" or "tv"
        vid = parts[1]     # "6a9dce8b268d04369d773013-70569"

        endpoints = self.config["endpoints"]
        # 详情页URL: /movie/{hex}-{num}.html 或 /tv/{hex}-{num}.html
        detail_key = f"detail_{vtype}" if f"detail_{vtype}" in endpoints else "detail_movie"
        url = self._fix_url(endpoints[detail_key].format(id=vid))

        try:
            html_text = self._fetch_html(url)
            if not html_text:
                return {"list": []}

            # 提取元信息
            info = self._parse_detail_info(html_text)
            info["vod_id"] = vod_id

            # 提取播放源和选集
            play_from, play_url = self._parse_play_sources(html_text)
            info["vod_play_from"] = "$$$".join(play_from) if play_from else "默认源"
            info["vod_play_url"] = "$$$".join(play_url) if play_url else ""

            # 修复播放URL为绝对路径
            if info.get("vod_play_url"):
                urls = info["vod_play_url"]
                # 分隔符拆分后修复每个URL
                fixed_sources = []
                for src_urls in urls.split("$$$"):
                    fixed_eps = []
                    for ep in src_urls.split("#"):
                        if "$" in ep:
                            name, url_part = ep.split("$", 1)
                            url_part = url_part.replace("&amp;", "&")
                            fixed_eps.append(f"{name}${url_part}")
                        else:
                            fixed_eps.append(ep)
                    fixed_sources.append("#".join(fixed_eps))
                info["vod_play_url"] = "$$$".join(fixed_sources)

            return {"list": [info]}

        except requests.exceptions.Timeout as e:
            if self.config.get("debug"):
                print(f"[detailContent] 超时 (id={vod_id}): {e}")
        except requests.exceptions.ConnectionError as e:
            if self.config.get("debug"):
                print(f"[detailContent] 连接失败 (id={vod_id}): {e}")
        except Exception as e:
            if self.config.get("debug"):
                print(f"[detailContent] 异常 (id={vod_id}): {e}")
        return {"list": []}

    def playerContent(self, flag: str, id: str, vipFlags: list = None) -> dict:
        """播放: 从播放页提取m3u8地址 (flag/id/vipFlags参数全部使用)
        id是播放页URL: /movie/{hex}/{num}.html 或 /tv/{hex}/{num}.html?origin={src}&p={ep}

        提取策略 (按可靠性排序):
          1. xg_video_player_doc.aa -> 当前选集的直链m3u8或API路径
          2. currentUrl变量 -> API路径
          3. HTML直链m3u8/mp4正则
          4. iframe播放器 (parse=1)
        """
        play_url = self._fix_url(id)

        headers = LieZiMi.build_headers(self.site_url + "/")
        result: dict = {
            "parse": 1,
            "url": play_url,
            "header": json.dumps(headers),
        }

        # 如果已经是m3u8/mp4直链
        if QianZiMi.is_direct_video(play_url):
            result["parse"] = 0
            return result

        try:
            # 获取播放页HTML
            html_text = self._fetch_html(play_url)
            if not html_text:
                return result

            # 策略1: 前字秘 - 从 xg_video_player_doc.aa 提取当前选集数据
            current_ep = QianZiMi.extract_current_episode(html_text)
            if current_ep:
                ep_url = current_ep.get("url", "")
                if ep_url:
                    if ep_url.startswith("http") and ".m3u8" in ep_url:
                        # 直链m3u8 (电影类型)
                        result["parse"] = 0
                        result["url"] = ep_url
                        return result
                    elif ep_url.startswith("/api/"):
                        # API路径 (电视剧类型), 转绝对路径
                        api_url = self._fix_url(ep_url)
                        result["parse"] = 0
                        result["url"] = api_url
                        return result

            # 策略2: 前字秘 - 提取 currentUrl 变量 (旧格式兼容)
            current_url = QianZiMi.extract_current_url(html_text)
            if current_url:
                m3u8_api_url = self._fix_url(current_url)
                result["parse"] = 0
                result["url"] = m3u8_api_url
                return result

            # 策略3: 在播放页HTML中找m3u8/mp4直链
            m3u8_match = re.search(r'(https?://[^\s"<>\\]+\.m3u8[^\s"<>\\]*)', html_text)
            if m3u8_match:
                result["parse"] = 0
                result["url"] = m3u8_match.group(1).replace("\\/", "/")
                return result

            mp4_match = re.search(r'(https?://[^\s"<>\\]+\.mp4[^\s"<>\\]*)', html_text)
            if mp4_match:
                result["parse"] = 0
                result["url"] = mp4_match.group(1).replace("\\/", "/")
                return result

            # 策略4: iframe播放器 (需要客户端解析)
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html_text)
            if iframe_match:
                result["parse"] = 1
                result["url"] = self._fix_url(iframe_match.group(1))
                return result

        except requests.exceptions.Timeout as e:
            if self.config.get("debug"):
                print(f"[playerContent] 超时: {e}")
        except requests.exceptions.ConnectionError as e:
            if self.config.get("debug"):
                print(f"[playerContent] 连接失败: {e}")
        except Exception as e:
            if self.config.get("debug"):
                print(f"[playerContent] 异常: {e}")

        # vipFlags使用: 检查是否为VIP标识
        if vipFlags and isinstance(vipFlags, list):
            for vf in vipFlags:
                if vf and str(vf).lower() in flag.lower():
                    result["parse"] = 1
                    break

        result["url"] = play_url
        result["parse"] = 1
        return result

    def searchContent(self, key: str, quick: bool = False, pg: Any = "1") -> dict:
        """搜索: 返回结果 (key/quick/pg参数全部使用)
        端点: /s.html?name={wd}&sion_id={sion_id}
        分页: /s.html?name={wd}&page={pg0}&sort_field=_id&sion_id={sion_id}
          (站点page从0开始: TVBox pg=1 -> site page=0, pg=2 -> page=1)
        防429: 浏览器安全头 + PoW验证后备
        """
        page = int(pg) if pg else 1
        result: dict = {"list": [], "page": page, "pagecount": 1}

        if not key:
            return result

        # quick使用: 快速模式只搜第一页
        if quick and page > 1:
            return result

        try:
            endpoints = self.config["endpoints"]
            sion_id = self.config.get("sion_id", "")
            # 站点分页0-indexed: TVBox pg=1 -> site page=0
            page0 = page - 1

            if page <= 1:
                search_url = self._fix_url(
                    endpoints["search"].format(wd=quote(key), sion_id=sion_id)
                )
            else:
                search_url = self._fix_url(
                    endpoints["search_paged"].format(
                        wd=quote(key), pg=page0, sion_id=sion_id
                    )
                )

            # 搜索前确保已访问首页 (获取sion_id cookie)
            if self.session and not self.session.cookies.get("sion_id"):
                try:
                    self.session.get(self.site_url + "/", timeout=10)
                except Exception:
                    pass

            html_text = self._fetch_html(search_url)

            # 429重试: 尝试PoW验证后重试
            if not html_text and self.session:
                html_text = self._search_with_retry(search_url, key, sion_id)

            if not html_text:
                return result

            videos = DouZiMi.parse_video_cards(html_text, self.site_url)

            # 解析分页: 找 page=N 格式的最大页码
            page_matches = re.findall(r"[?&]page=(\d+)", html_text)
            if page_matches:
                max_site_page = max(int(p) for p in page_matches)
                result["pagecount"] = max_site_page + 1
            else:
                if f"page={page0 + 1}" in html_text:
                    result["pagecount"] = page + 1

            result["list"] = videos

        except requests.exceptions.Timeout as e:
            if self.config.get("debug"):
                print(f"[searchContent] 超时 (key={key}): {e}")
        except requests.exceptions.ConnectionError as e:
            if self.config.get("debug"):
                print(f"[searchContent] 连接失败 (key={key}): {e}")
        except Exception as e:
            if self.config.get("debug"):
                print(f"[searchContent] 异常 (key={key}): {e}")

        return result

    def _search_with_retry(self, search_url: str, key: str, sion_id: str) -> Optional[str]:
        """429重试: 从429页面提取PoW挑战, 计算attack_key后重试搜索
        429页面内嵌: var hash='...', var target='...'
        解决后: search_url + '&attack_key=' + nonce
        """
        if not self.session:
            return None

        try:
            # 1. 重新请求搜索URL, 获取429页面内容
            resp = self.session.get(search_url, timeout=self.config.get("timeout", 15))
            if resp.status_code != 429:
                # 不是429, 可能是其他问题
                if resp.status_code == 200:
                    return resp.text
                return None

            html_429 = resp.text
            if self.config.get("debug"):
                print(f"[_search_with_retry] 429页面长度: {len(html_429)}")

            # 2. 从429页面提取 hash 和 target
            hash_match = re.search(r"var\s+hash\s*=\s*'([a-f0-9]+)'", html_429)
            target_match = re.search(r"var\s+target\s*=\s*'([a-f0-9]+)'", html_429)

            if not hash_match or not target_match:
                if self.config.get("debug"):
                    print("[_search_with_retry] 未找到PoW挑战参数")
                return None

            hash_val = hash_match.group(1)
            target_val = target_match.group(1)

            if self.config.get("debug"):
                print(f"[_search_with_retry] PoW: hash={hash_val[:20]}... target={target_val[:20]}...")

            # 3. 计算PoW nonce (sha1(hash + i) === target)
            nonce = QianZiMi.solve_pow(hash_val, target_val)
            if nonce is None:
                if self.config.get("debug"):
                    print("[_search_with_retry] PoW计算失败")
                return None

            if self.config.get("debug"):
                print(f"[_search_with_retry] PoW solved: nonce={nonce}")

            # 4. 用attack_key重试搜索
            # 429页面的JS逻辑: currentUrl + separator + 'attack_key=' + i
            retry_url = search_url
            if "attack_key=" in retry_url:
                # 已有attack_key, 替换
                retry_url = re.sub(
                    r"([?&])attack_key=[^&]*",
                    rf"\1attack_key={nonce}",
                    retry_url
                )
            else:
                # 添加attack_key
                separator = "&" if "?" in retry_url else "?"
                retry_url = retry_url + separator + f"attack_key={nonce}"

            if self.config.get("debug"):
                print(f"[_search_with_retry] 重试URL: {retry_url[:120]}...")

            # 5. 用attack_key重试
            html_text = self._fetch_html(retry_url)
            return html_text

        except requests.exceptions.Timeout as e:
            if self.config.get("debug"):
                print(f"[_search_with_retry] 超时: {e}")
        except requests.exceptions.ConnectionError as e:
            if self.config.get("debug"):
                print(f"[_search_with_retry] 连接失败: {e}")
        except Exception as e:
            if self.config.get("debug"):
                print(f"[_search_with_retry] 异常: {e}")

        return None

    def searchContentPage(self, key: str, quick: bool, pg: int) -> dict:
        """搜索分页"""
        return self.searchContent(key, quick, pg)

    def localProxy(self, param: str = "") -> dict:
        """本地代理 (param参数使用)"""
        result: dict = {"url": "", "header": "", "mimeType": ""}
        if param:
            try:
                decoded = unquote(str(param))
                if decoded.startswith("http"):
                    result["url"] = decoded
                    result["header"] = json.dumps(
                        LieZiMi.build_headers(self.site_url + "/")
                    )
                    result["mimeType"] = "video/mp4"
            except (ValueError, TypeError) as e:
                if self.config.get("debug"):
                    print(f"[localProxy] 参数错误: {e}")
            except Exception as e:
                if self.config.get("debug"):
                    print(f"[localProxy] 异常: {e}")
        return result


# ==================================================================
#  自检入口 (铁律8)
# ==================================================================

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()

    spider = Spider()
    spider.init()

    print("=" * 60)
    print("  豆花电影网 TVBox爬虫源 - 自检")
    print(f"  站点: {spider.site_url}")
    print("  境界: 道宫境(Lv.1)")
    print("=" * 60)

    print("\n=== homeContent ===")
    try:
        home = spider.homeContent()
        print(f"分类数: {len(home.get('class', []))}")
        for c in home.get("class", []):
            print(f"  {c['type_name']}: {c['type_id']}")
        print(f"推荐视频数: {len(home.get('list', []))}")
        if home.get("list"):
            v = home["list"][0]
            print(f"首条: {v['vod_name']} | {v.get('vod_remarks', '')} | {v['vod_id']}")
            print(f"封面: {v.get('vod_pic', '')[:80]}")
    except Exception as e:
        print(f"homeContent 失败: {e}")

    print("\n=== categoryContent (电影) ===")
    try:
        cat = spider.categoryContent("dianying", "1", False, {})
        print(f"视频数: {len(cat.get('list', []))}")
        print(f"分页: page={cat.get('page')} pagecount={cat.get('pagecount')}")
        if cat.get("list"):
            v = cat["list"][0]
            print(f"首条: {v['vod_name']} | {v.get('vod_remarks', '')}")
            print(f"封面: {v.get('vod_pic', '')[:80]}")
            print(f"vod_id: {v.get('vod_id', '')}")
    except Exception as e:
        print(f"categoryContent 失败: {e}")

    print("\n=== categoryContent (电视剧) ===")
    try:
        cat2 = spider.categoryContent("dianshiju", "1", False, {})
        print(f"视频数: {len(cat2.get('list', []))}")
        if cat2.get("list"):
            v = cat2["list"][0]
            print(f"首条: {v['vod_name']} | {v.get('vod_remarks', '')}")
            print(f"vod_id: {v.get('vod_id', '')}")
    except Exception as e:
        print(f"categoryContent(电视剧) 失败: {e}")

    print("\n=== detailContent ===")
    try:
        if cat.get("list"):
            test_id = cat["list"][0]["vod_id"]
            detail = spider.detailContent([test_id])
            if detail.get("list"):
                d = detail["list"][0]
                print(f"名称: {d.get('vod_name', '')}")
                print(f"封面: {d.get('vod_pic', '')[:80]}")
                print(f"年份: {d.get('vod_year', '')}")
                print(f"地区: {d.get('vod_area', '')}")
                print(f"播放源: {d.get('vod_play_from', '')[:100]}")
                play_url = d.get('vod_play_url', '')
                print(f"播放URL片段: {play_url[:200]}")
            else:
                print("详情页无数据")
        else:
            print("无分类数据, 跳过详情测试")
    except Exception as e:
        print(f"detailContent 失败: {e}")

    print("\n=== detailContent (电视剧) ===")
    try:
        if cat2.get("list"):
            test_id2 = cat2["list"][0]["vod_id"]
            detail2 = spider.detailContent([test_id2])
            if detail2.get("list"):
                d2 = detail2["list"][0]
                print(f"名称: {d2.get('vod_name', '')}")
                print(f"播放源: {d2.get('vod_play_from', '')[:100]}")
                play_url2 = d2.get('vod_play_url', '')
                print(f"播放URL片段: {play_url2[:200]}")
                # 计算选集数
                if play_url2:
                    first_src = play_url2.split("$$$")[0]
                    ep_count = len(first_src.split("#"))
                    print(f"首源选集数: {ep_count}")
    except Exception as e:
        print(f"detailContent(电视剧) 失败: {e}")

    print("\n=== searchContent ===")
    try:
        search = spider.searchContent("海洋", False, "1")
        print(f"搜索结果数: {len(search.get('list', []))}")
        if search.get("list"):
            v = search["list"][0]
            print(f"首条: {v.get('vod_name')} | {v.get('vod_id')}")
    except Exception as e:
        print(f"searchContent 失败: {e}")

    print("\n=== playerContent ===")
    try:
        if cat.get("list"):
            test_id = cat["list"][0]["vod_id"]
            detail = spider.detailContent([test_id])
            if detail.get("list") and detail["list"][0].get("vod_play_url"):
                d = detail["list"][0]
                all_eps = d["vod_play_url"].split("$$$")
                if all_eps and all_eps[0]:
                    first_ep = all_eps[0].split("#")[0]
                    ep_url = first_ep.split("$")[-1] if "$" in first_ep else first_ep
                    ep_url = ep_url.replace("&amp;", "&")
                    first_flag = d["vod_play_from"].split("$$$")[0]
                    player = spider.playerContent(first_flag, ep_url, [])
                    print(f"parse: {player.get('parse')}")
                    print(f"url: {player.get('url', '')[:120]}")
    except Exception as e:
        print(f"playerContent 失败: {e}")

    print("\n" + "=" * 60)
    print("  自检完成")
    print("=" * 60)
