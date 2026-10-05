"""
composer.py - 智能重组、全网源共识度分析、自适应配比与配置生成引擎
核心算法：
1. 全网大数据共识挖掘：统计候选站源在各大顶级单仓（饭太硬、肥猫、心魔、潇洒、南风、小马等）中的出现率与推荐频次；
2. 黄金品类均衡配比：在线影视(40%) + 4K网盘(35%) + 稳定采集(15%) + 特色专区(10%)，确保 100 个站源既有画质天花板，又有开箱即点即播；
3. 多仓共识测速排序：多仓线路综合“全网推荐度”与“宽带测速延迟”加权排名，优选前 25-30 条最稳定线路；
4. 深度安全过滤：去广告、去死链、相对路径修复、GitHub 镜像加速代理注入。
"""
import os
import re
import json
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from pathlib import Path

from auto_engine.config import (
    OUTPUT_CONFIG_1, OUTPUT_CONFIG_TV8, OUTPUT_REPO_TXT,
    GITHUB_PROXIES, MAX_SITES_OUTPUT, MIN_SCORE_THRESHOLD,
    CATEGORY_QUOTAS, ROOT_DIR
)
from auto_engine.json_cleaner import parse_tvbox_json

# 广告与引流垃圾站点关键词黑名单
AD_KEYWORDS = [
    "加微信", "进群", "扫码", "招代理", "防失联", "公众号", "收费", "广告位", 
    "出租", "备用群", "关注微信", "购买", "充值", "返利", "淘客"
]

def is_ad_site(site: Dict) -> bool:
    """判定是否为垃圾广告引流站点"""
    if not isinstance(site, dict):
        return True
    name = str(site.get("name", ""))
    key = str(site.get("key", ""))
    api = str(site.get("api", ""))
    ext = str(site.get("ext", ""))
    
    for kw in AD_KEYWORDS:
        if kw in name or kw in key:
            return True
            
    # 排除包含未解析相对路径的站点 (如 ./XBPQ/... 或 ./json/...，在缺乏对应本地文件时在电视端必然白屏报错)
    if isinstance(site.get("ext"), str):
        ext_str = site["ext"].strip()
        if ext_str.startswith("./") or ext_str.startswith("../"):
            # 如果本地根本没有该文件，直接剔除
            local_candidate = ROOT_DIR / ext_str.lstrip("./")
            if not local_candidate.exists():
                return True
                
    if isinstance(site.get("ext"), dict):
        for val in site["ext"].values():
            if isinstance(val, str) and (val.strip().startswith("./") or val.strip().startswith("../")):
                local_candidate = ROOT_DIR / val.strip().lstrip("./")
                if not local_candidate.exists():
                    return True

    # 无有效 api 或纯占位符
    if not api or api in ["csp_Placeholder", "占位", "null", "None"]:
        return True
    return False

def clean_site_name(name: str) -> str:
    """美化与规范化站点名称，去除多余修饰符"""
    name = re.sub(r'[\(（]?(?:4k|1080p|蓝光|秒播|备用|采集|影视|在线|优质|聚合)[\)）]?', '', name, flags=re.IGNORECASE)
    name = name.strip(" |-_/[]【】")
    return name

def get_site_fingerprint(site: Dict) -> str:
    """提取站点的归一化指纹，便于在全网不同单仓中聚类和统计共识频次"""
    name = str(site.get("name", ""))
    key = str(site.get("key", ""))
    api = str(site.get("api", ""))
    ext = str(site.get("ext", ""))
    
    # 剥除 emoji 与标点符号
    clean_n = re.sub(r'[\U00010000-\U0010ffff]', '', name)
    clean_n = re.sub(r'[\u2000-\u2bff]', '', clean_n)
    clean_n = re.sub(r'[\|┃\-_/\[\]【】\(\)（）\s]', '', clean_n)
    clean_n = re.sub(r'(?:4k|1080p|蓝光|秒播|备用|采集|影视|网盘|阿里|夸克|js|专线|纯净|弹幕)', '', clean_n, flags=re.IGNORECASE).strip()

    # 知名公共源核心归一化识别
    lower_all = f"{clean_n} {key} {api} {ext}".lower()
    if any(k in lower_all for k in ["玩偶", "wogg"]):
        return "wogg_玩偶哥哥"
    if any(k in lower_all for k in ["厂长", "czzy", "czsapp"]):
        return "czzy_厂长资源"
    if any(k in lower_all for k in ["荐片", "jianpian"]):
        return "jianpian_荐片影视"
    if any(k in lower_all for k in ["低端", "ddys"]):
        return "ddys_低端影视"
    if any(k in lower_all for k in ["爱看", "ikanbot"]):
        return "ikanbot_爱看机器人"
    if any(k in lower_all for k in ["至臻", "mihdr"]):
        return "zhizhen_至臻4K"
    if any(k in lower_all for k in ["蜡笔", "xiaocgeg"]):
        return "labi_蜡笔4K"
    if any(k in lower_all for k in ["木偶", "666291"]):
        return "muou_木偶4K"
    if any(k in lower_all for k in ["暴风", "bfzy"]):
        return "bfzy_暴风采集"
    if any(k in lower_all for k in ["红牛", "hongniu"]):
        return "hongniu_红牛资源"
    if any(k in lower_all for k in ["量子", "lziapi"]):
        return "liangzi_量子资源"
    if any(k in lower_all for k in ["极速", "jszy"]):
        return "jisu_极速资源"
    if any(k in lower_all for k in ["看球", "kanqiu"]):
        return "kanqiu_看球专区"
    if any(k in lower_all for k in ["茶杯狐", "hhzyapi"]):
        return "chabeihu_茶杯狐"
    if any(k in lower_all for k in ["南瓜", "nangua"]):
        return "nangua_南瓜影视"
    if any(k in lower_all for k in ["酷云七七", "kunyu77"]):
        return "kunyu77_酷云七七"
    if any(k in lower_all for k in ["六度", "六度tv"]):
        return "liudu_六度影视"
    if any(k in lower_all for k in ["大师兄", "dashixiong"]):
        return "dashixiong_大师兄"
    if any(k in lower_all for k in ["秋霞", "qiuxia"]):
        return "qiuxia_秋霞影视"
    if any(k in lower_all for k in ["易搜", "yiso"]):
        return "yiso_易搜"
    if any(k in lower_all for k in ["云搜", "upyun"]):
        return "upyun_云搜"
    if any(k in lower_all for k in ["夸克", "quark"]):
        return "quark_夸克网盘"
        
    # 通用指纹：优先使用 (api + ext核心) 或 (clean_name + api)
    if api.startswith("csp_"):
        return f"{api}_{clean_n}"
    return f"{clean_n}_{api[:30]}"

def classify_site(site: Dict) -> str:
    """根据站点特性智能划入四大阵营"""
    name = str(site.get("name", ""))
    key = str(site.get("key", ""))
    api = str(site.get("api", ""))
    type_ = site.get("type", 0)
    ext = str(site.get("ext", ""))
    combined = f"{name} {key} {api} {ext}".lower()
    
    # 1. 特色类 (体育赛事、少儿课堂、哔哩动漫、音乐MV、预告片)
    if any(k in combined for k in ["看球", "体育", "球", "小学", "初中", "高中", "课堂", "少儿", "哔哩", "bili", "音乐", "kugou", "酷狗", "mv", "预告", "星牙", "短剧"]):
        return "special"
        
    # 2. 4K 原画与网盘/磁力类 (阿里/夸克/UC/115/迅雷/云盘)
    if any(k in combined for k in [
        "网盘", "阿里", "夸克", "uc", "115", "迅雷", "4k", "原画", "wogg", "玩偶", 
        "至臻", "蜡笔", "木偶", "多多", "闪电", "花卷", "种子", "yiso", "upyun", 
        "misou", "pansearch", "alist", "quark", "token", "seed", "hdmoli", "zmi", "jutoushe"
    ]):
        return "pan"
        
    # 3. 稳定全网综合采集站 (CMS Type 1 或 api 包含 provide/vod)
    if type_ == 1 or "provide/vod" in api or any(k in combined for k in [
        "采集", "暴风", "红牛", "量子", "极速", "非凡", "索尼", "茶杯狐", "熊掌", "卧龙", "光速"
    ]):
        return "cms"
        
    # 4. 免登录在线影视 (dr_py, 网页JS/爬虫，厂长、低端、荐片、爱看等)
    return "online"

def inject_fast_proxy(url_str: str) -> str:
    """如果包含 GitHub raw 链接，自动注入当前最快速的 wget.la 代理前缀"""
    if not isinstance(url_str, str):
        return url_str
    if "raw.githubusercontent.com" in url_str:
        # 去除已有的旧代理
        for p in GITHUB_PROXIES:
            url_str = url_str.replace(p, "")
        url_str = url_str.lstrip("/")
        if not url_str.startswith("http"):
            url_str = "https://" + url_str
        return f"https://wget.la/{url_str}"
    return url_str

class TVBoxComposer:
    def __init__(self, alive_results: List[Dict]):
        self.alive_results = alive_results
        self.single_configs = [r for r in alive_results if r["type"] == "single"]
        self.multi_configs = [r for r in alive_results if r["type"] == "multi"]

    def extract_and_merge_sites(self) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        全网主流单仓源的大数据频次/共识度挖掘引擎：
        1. 聚合所有存活单仓及本地底模中的站点；
        2. 统计每个站点的全网出现频次 (Consensus Frequency)；
        3. 按照 4 大核心阵营进行均衡配比，优选总数达到 MAX_SITES_OUTPUT (100 个)。
        """
        site_frequency = defaultdict(int)       # fingerprint -> count
        site_best_candidate = {}                # fingerprint -> best site dict
        site_sources_map = defaultdict(set)     # fingerprint -> set of source names

        def ingest_site(site: Dict, source_name: str, base_weight: int = 1):
            if not isinstance(site, dict) or is_ad_site(site):
                return
            fp = get_site_fingerprint(site)
            site_frequency[fp] += base_weight
            site_sources_map[fp].add(source_name)
            
            # 保留配置最完整、ext 最详细的那个对象
            current_best = site_best_candidate.get(fp)
            if current_best is None:
                site_best_candidate[fp] = site
            else:
                curr_len = len(str(current_best.get("ext", "")))
                new_len = len(str(site.get("ext", "")))
                if new_len > curr_len:
                    site_best_candidate[fp] = site

        # 1. 读取本地历史底模 (1.json, 3.json, 2.json) 作为高权重基础种子
        local_files = [
            ("1.json", OUTPUT_CONFIG_1, 5),     # 当前基线赋予 5 次全网权重
            ("3.json", ROOT_DIR / "3.json", 4), # 历史精选 JS 站赋予 4 次全网权重
            ("2.json", ROOT_DIR / "2.json", 3), # 历史网盘/磁力赋予 3 次全网权重
        ]
        for name, pth, weight in local_files:
            if pth.exists():
                try:
                    with open(pth, "r", encoding="utf-8", errors="ignore") as fp:
                        parsed = parse_tvbox_json(fp.read())
                        if isinstance(parsed, dict) and "sites" in parsed:
                            for s in parsed["sites"]:
                                ingest_site(s, f"本地基线({name})", base_weight=weight)
                except Exception as e:
                    print(f"[!] 读取本地基线 {name} 异常: {e}")

        # 2. 遍历全网所有存活且高分的单仓配置，挖掘全网主流共识
        valid_singles = [r for r in self.single_configs if r["score"] >= MIN_SCORE_THRESHOLD]
        print(f"[*] 正在对全网 {len(valid_singles)} 个存活主流单仓进行大数据站点共识分析...")
        
        for rep in valid_singles:
            raw_data = rep.get("raw_data")
            if not raw_data or "sites" not in raw_data or not isinstance(raw_data["sites"], list):
                continue
            src_name = rep.get("name", "主流单仓")
            for s in raw_data["sites"]:
                ingest_site(s, src_name, base_weight=1)

        print(f"[+] 全网站点共识挖掘完成：发现独立候选站源 {len(site_best_candidate)} 个")

        # 3. 按四大阵营归类并按全网共识频次排序
        category_pools = {
            "online": [],
            "pan": [],
            "cms": [],
            "special": []
        }

        consensus_stats = []

        for fp, site in site_best_candidate.items():
            freq = site_frequency[fp]
            cat = classify_site(site)
            # 代理链接优化
            if isinstance(site.get("api"), str):
                site["api"] = inject_fast_proxy(site["api"])
            if isinstance(site.get("ext"), str):
                site["ext"] = inject_fast_proxy(site["ext"])
            if isinstance(site.get("jar"), str):
                site["jar"] = inject_fast_proxy(site["jar"])
                
            entry = {
                "fingerprint": fp,
                "site": site,
                "frequency": freq,
                "category": cat,
                "sources_count": len(site_sources_map[fp])
            }
            category_pools[cat].append(entry)
            consensus_stats.append({
                "name": site.get("name"),
                "category": cat,
                "frequency": freq,
                "api": str(site.get("api", ""))[:40]
            })

        # 阵营内部按全网共识频次降序排序
        for cat in category_pools:
            category_pools[cat].sort(key=lambda x: -x["frequency"])
            print(f"    ├─ [{cat.upper():7s}] 候选数: {len(category_pools[cat])} (最高共识频次: {category_pools[cat][0]['frequency'] if category_pools[cat] else 0})")

        # 4. 按照设定配额抽取前 100 个源
        selected_entries = []
        selected_fps = set()

        for cat, quota in CATEGORY_QUOTAS.items():
            pool = category_pools[cat]
            taken = 0
            for item in pool:
                if item["fingerprint"] not in selected_fps:
                    selected_entries.append(item)
                    selected_fps.add(item["fingerprint"])
                    taken += 1
                    if taken >= quota:
                        break

        # 如果部分分类未填满配额，用整体共识度最高且未入选的站点补齐至 MAX_SITES_OUTPUT (100 个)
        if len(selected_entries) < MAX_SITES_OUTPUT:
            all_remaining = []
            for cat in category_pools:
                for item in category_pools[cat]:
                    if item["fingerprint"] not in selected_fps:
                        all_remaining.append(item)
            all_remaining.sort(key=lambda x: -x["frequency"])
            needed = MAX_SITES_OUTPUT - len(selected_entries)
            for item in all_remaining[:needed]:
                selected_entries.append(item)
                selected_fps.add(item["fingerprint"])

        # 保证最终总数达到 MAX_SITES_OUTPUT
        final_sites = [item["site"] for item in selected_entries[:MAX_SITES_OUTPUT]]
        print(f"[√] 最终精选 100 站源组装完毕！总数: {len(final_sites)} 个")

        # 统计持久化
        stats_payload = {
            "total_candidates": len(site_best_candidate),
            "selected_count": len(final_sites),
            "quotas": CATEGORY_QUOTAS,
            "top_consensus_sites": sorted(consensus_stats, key=lambda x: -x["frequency"])[:100]
        }

        return final_sites, stats_payload

    def rebuild_config_1(self, final_sites: List[Dict]) -> bool:
        """重构并输出 1.json 单仓配置 (含 100 个高共识精选源)"""
        if len(final_sites) < 30:
            print("[!] 熔断保护触发：融合站点数量不足 30 个，放弃覆盖 1.json 以防止配置损坏！")
            return False

        # 保留现有的 parses, rules, doh 等高级配置
        existing_data = {}
        if OUTPUT_CONFIG_1.exists():
            try:
                with open(OUTPUT_CONFIG_1, "r", encoding="utf-8") as fp:
                    existing_data = json.load(fp)
            except Exception:
                pass

        # 加载高级解析、去广告规则与播放解码模板 (确保功能完备)
        template_file = ROOT_DIR / "auto_engine" / "data" / "config_template.json"
        template_data = {}
        if template_file.exists():
            try:
                with open(template_file, "r", encoding="utf-8") as fp:
                    template_data = json.load(fp)
            except Exception:
                pass

        # Spider 爬虫核心配置：优先使用自建仓库的高可用 Yoursmile240104.jar
        spider_url = "https://wget.la/https://raw.githubusercontent.com/niubihu1/tvbox-/main/jar/Yoursmile240104.jar"

        new_config = {
            "spider": spider_url,
            "wallpaper": existing_data.get("wallpaper") or template_data.get("wallpaper", "https://bingw.jasonzeng.dev/?index=random"),
            "sites": final_sites,
            "parses": existing_data.get("parses") or template_data.get("parses", []),
            "lives": existing_data.get("lives") or template_data.get("lives", []),
            "logo": existing_data.get("logo") or template_data.get("logo", "https://wget.la/https://raw.githubusercontent.com/yoursmile66/TVBox/refs/heads/main/json/NanFeng.gif"),
            "rules": existing_data.get("rules") or template_data.get("rules", []),
            "doh": existing_data.get("doh") or template_data.get("doh", []),
            "ijk": existing_data.get("ijk") or template_data.get("ijk", []),
            "ads": existing_data.get("ads") or template_data.get("ads", [])
        }

        try:
            with open(OUTPUT_CONFIG_1, "w", encoding="utf-8") as fp:
                json.dump(new_config, fp, ensure_ascii=False, indent=2)
            print(f"[√] 成功生成并更新: {OUTPUT_CONFIG_1.name} (含 {len(final_sites)} 个全网共识优选站源)")
            return True
        except Exception as e:
            print(f"[!] 写入 1.json 失败: {e}")
            return False

    def rebuild_warehouse_txt(self) -> bool:
        """
        重构并输出 自用仓库.txt 多仓列表
        同样基于“全网多仓共识度挖掘 + 实时延迟测速”进行综合加权排序
        """
        urls_list = [
            {
                "url": "https://wget.la/https://raw.githubusercontent.com/niubihu1/tvbox-/main/1.json",
                "name": "🚀自用优选线路🚀"
            }
        ]

        seen_urls = {urls_list[0]["url"]}

        import os
        is_ci = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"

        # 统计在所有多仓配置中，各单仓线路出现的共识频次
        line_frequency = defaultdict(int)
        for multi_rep in self.multi_configs:
            raw = multi_rep.get("raw_data", {})
            entries = raw.get("urls", []) if "urls" in raw else raw.get("storeHouse", [])
            for item in entries:
                if isinstance(item, dict):
                    u = item.get("url") or item.get("sourceUrl")
                    if u:
                        line_frequency[u] += 1

        # 排序打分：全网多仓共识频次加权 + 国内一线源加权 + 延迟打分
        def warehouse_sort_key(c):
            url = c.get("url", "")
            name = c.get("name", "")
            freq = line_frequency.get(url, 0)
            is_vip = any(k in name or k in url for k in [
                "饭太硬", "肥猫", "心魔", "周J", "道长", "潇洒", "南风", "摸鱼", "王二小", "小马", "俊宇", "香雅情", "荷城", "巧技"
            ])
            vip_bonus = 20 if is_vip else 0
            freq_score = min(30, freq * 5)
            # 综合推荐分
            total_rank = c["score"] + vip_bonus + freq_score
            return (-total_rank, c.get("latency", 9999))

        top_candidates = [r for r in self.alive_results if r["score"] >= 45]
        top_candidates.sort(key=warehouse_sort_key)

        for c in top_candidates:
            url = c["url"]
            name = c.get("name", "")
            if url in seen_urls or "niubihu1/tvbox-" in url:
                continue
            seen_urls.add(url)
            
            clean_name = clean_site_name(name) if name else "全网精选源"
            if is_ci:
                clean_name = f"🚀{clean_name} [在线]"
            else:
                clean_name = f"🚀{clean_name} [{c['latency']}ms]"
            
            urls_list.append({
                "url": url,
                "name": clean_name
            })
            if len(urls_list) >= 28: # 保留前 28 条极速稳定线路
                break

        output_data = {
            "urls": urls_list
        }

        try:
            with open(OUTPUT_REPO_TXT, "w", encoding="utf-8") as fp:
                if is_ci:
                    fp.write("// 此多仓接口列表由 GitHub Actions 自动化保活巡检引擎生成 [云端保活版]\n")
                else:
                    fp.write("// 此多仓接口列表由 auto_engine 本地家庭宽带巡检引擎实时测速生成 [家庭测速版]\n")
                fp.write(json.dumps(output_data, ensure_ascii=False, indent=4))
            print(f"[√] 成功生成并更新: {OUTPUT_REPO_TXT.name} (含 {len(urls_list)} 条精选高共识线路, 环境: {'GitHub Actions' if is_ci else '本地网络'})")
            return True
        except Exception as e:
            print(f"[!] 写入 自用仓库.txt 失败: {e}")
            return False

    def rebuild_config_tv8(self) -> bool:
        """
        重构并输出 tv8.json 多仓导航总索引
        整合经过测活验证的最顶级多仓仓库列表，同时兼容 storeHouse 与 urls 两种格式。
        """
        import os
        is_ci = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"

        # 基础多仓列表，第一位永远是自用优选仓（使用标准 URL 编码避免中文路径请求失败）
        our_warehouse_url = "https://wget.la/https://raw.githubusercontent.com/niubihu1/tvbox-/main/%E8%87%AA%E7%94%A8%E4%BB%93%E5%BA%93.txt"
        store_house_list = [
            {
                "sourceName": "❤️自用优选仓(28条精品线)❤️",
                "sourceUrl": our_warehouse_url
            }
        ]
        seen_urls = {our_warehouse_url}

        # 知名高品质多仓优先库（全部经过 200 OK 测活验证）
        curated_multi = [
            {"name": "💚影视仓官方多仓🍭", "url": "https://gitlab.com/noimank/tvbox/-/raw/main/tvboxmuti.json"},
            {"name": "💛小盒子精品多仓🍭", "url": "http://xhztv.top/dc"},
            {"name": "💜光影聚合多仓🍭", "url": "https://ztha.top/TVBox/GYCK.json"},
            {"name": "🧡游魂精品多仓🍭", "url": "https://www.iyouhun.com/tv/dc"},
            {"name": "💛拾光精选多仓🍭", "url": "https://wget.la/https://raw.githubusercontent.com/xmbjm/xmbjm.github.io/main/ck.json"},
            {"name": "💙威龙影视多仓🍭", "url": "http://tv.weidonglong.com/ysc5.json"},
            {"name": "💜云星聚合多仓🍭", "url": "https://fastly.jsdelivr.net/gh/tv189ymail/ku2023@main/A1/ck.json"},
            {"name": "💚小微精选多仓🍭", "url": "https://wget.la/https://raw.githubusercontent.com/yigedashu/xwck/refs/heads/main/xwck.json"},
            {"name": "💛刘备综合多仓🍭", "url": "https://raw.liucn.cc/box/dm.txt"},
            {"name": "💙新微精选多仓🍭", "url": "https://wget.la/https://raw.githubusercontent.com/wxrjck/-YSC-/refs/heads/main/wx.json"},
            {"name": "💜Kstore精选多仓🍭", "url": "https://12586.kstore.space/123.json"}
        ]

        for cm in curated_multi:
            u = cm["url"]
            if u not in seen_urls:
                seen_urls.add(u)
                store_house_list.append({
                    "sourceName": cm["name"],
                    "sourceUrl": u
                })

        # 从动态测活的多仓中补齐高分多仓
        alive_multi = [r for r in self.multi_configs if r["is_alive"] and r["score"] >= 75 and r["sites_count"] >= 3]
        alive_multi.sort(key=lambda x: (-x["score"], x.get("latency", 9999)))

        for m in alive_multi:
            u = m["url"]
            if u in seen_urls or "niubihu1/tvbox-" in u or "127.0.0.1" in u:
                continue
            seen_urls.add(u)
            name = clean_site_name(m.get("name", "")) or "全网精选多仓"
            badge = " [在线]" if is_ci else f" [{m['latency']}ms]"
            store_house_list.append({
                "sourceName": f"🚀{name}{badge}",
                "sourceUrl": u
            })
            if len(store_house_list) >= 16:
                break

        # 同时生成 urls 格式，确保影视仓、宝盒、各类 TVBox 完美兼容
        urls_compat = [
            {
                "name": item["sourceName"],
                "url": item["sourceUrl"]
            }
            for item in store_house_list
        ]

        tv8_data = {
            "storeHouse": store_house_list,
            "urls": urls_compat
        }

        try:
            with open(OUTPUT_CONFIG_TV8, "w", encoding="utf-8") as fp:
                if is_ci:
                    fp.write("// 此多仓接口由 auto_engine 自动化引擎测活与重构生成 [云端保活版]\n")
                else:
                    fp.write("// 此多仓接口由 auto_engine 本地家庭宽带巡检引擎实时测速生成 [家庭测速版]\n")
                fp.write(json.dumps(tv8_data, ensure_ascii=False, indent=2))
            print(f"[√] 成功生成并更新: {OUTPUT_CONFIG_TV8.name} (含 {len(store_house_list)} 个经过测活的高品质多仓仓库)")
            return True
        except Exception as e:
            print(f"[!] 写入 tv8.json 失败: {e}")
            return False

    def run_all(self) -> bool:
        final_sites, stats_payload = self.extract_and_merge_sites()
        
        # 持久化全网共识统计数据
        data_dir = ROOT_DIR / "auto_engine" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        stats_file = data_dir / "site_consensus.json"
        try:
            with open(stats_file, "w", encoding="utf-8") as fp:
                json.dump(stats_payload, fp, ensure_ascii=False, indent=2)
            print(f"[+] 全网共识统计数据已保存至: {stats_file}")
        except Exception as e:
            print(f"[!] 保存 site_consensus.json 失败: {e}")

        ok1 = self.rebuild_config_1(final_sites)
        ok2 = self.rebuild_warehouse_txt()
        ok3 = self.rebuild_config_tv8()
        return ok1 and ok2 and ok3
