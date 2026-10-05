"""
composer.py - 智能重组、去重、代理注入与文件生成模块
将测活通过的优质数据源去重、清洗广告、加速代理替换，并重构生成 1.json, 自用仓库.txt 等发布文件
"""
import re
import json
from typing import List, Dict, Any
from auto_engine.config import (
    OUTPUT_CONFIG_1, OUTPUT_CONFIG_TV8, OUTPUT_REPO_TXT,
    GITHUB_PROXIES, MAX_SITES_OUTPUT, MIN_SCORE_THRESHOLD
)

# 广告与引流关键词过滤表
AD_KEYWORDS = ["加微信", "进群", "扫码", "招代理", "防失联", "公众号", "收费", "广告位", "出租"]

def is_ad_site(site: Dict) -> bool:
    """判定是否为垃圾广告引流站点"""
    name = site.get("name", "")
    key = site.get("key", "")
    api = str(site.get("api", ""))
    
    for kw in AD_KEYWORDS:
        if kw in name or kw in key:
            return True
            
    # 排除包含未解析相对路径的站点 (如 ./XBPQ/... 或 ./json/...，在缺乏对应本地文件时必然失效)
    ext = site.get("ext")
    if isinstance(ext, str) and (ext.startswith("./") or ext.startswith("../")):
        return True
    if isinstance(ext, dict):
        for val in ext.values():
            if isinstance(val, str) and (val.startswith("./") or val.startswith("../")):
                return True

    # 无有效 api 或纯文字占位
    if not api or api in ["csp_Placeholder", ""]:
        return True
    return False

def clean_site_name(name: str) -> str:
    """美化与规范化站点名称"""
    name = re.sub(r'[\(（]?(?:4k|1080p|蓝光|秒播|备用|采集|影视)[\)）]?', '', name, flags=re.IGNORECASE)
    name = name.strip(" |-_/[]【】")
    return name

class TVBoxComposer:
    def __init__(self, alive_results: List[Dict]):
        self.alive_results = alive_results
        self.single_configs = [r for r in alive_results if r["type"] == "single"]
        self.multi_configs = [r for r in alive_results if r["type"] == "multi"]

    def extract_and_merge_sites(self) -> List[Dict]:
        """从所有存活单仓中提取、去重、清洗并加权排序点播站点"""
        site_map = {} # fingerprint -> site
        
        # 优先从当前主推的 1.json 读取原始站点作为第一梯队底模
        base_sites = []
        if OUTPUT_CONFIG_1.exists():
            try:
                with open(OUTPUT_CONFIG_1, "r", encoding="utf-8") as fp:
                    base_data = json.load(fp)
                    base_sites = base_data.get("sites", [])
            except Exception:
                pass
                
        # 1. 注入当前基线站点
        for s in base_sites:
            if not is_ad_site(s):
                fp = f"{s.get('key')}_{s.get('api')}"
                site_map[fp] = s

        # 2. 从采集到的高分活跃单仓中融合最新站点
        for rep in self.single_configs:
            if rep["score"] < MIN_SCORE_THRESHOLD:
                continue
            raw_data = rep.get("raw_data")
            if not raw_data or "sites" not in raw_data:
                continue
                
            for s in raw_data["sites"]:
                if not isinstance(s, dict) or is_ad_site(s):
                    continue
                fp = f"{s.get('key')}_{s.get('api')}"
                if fp not in site_map:
                    site_map[fp] = s

        merged_sites = list(site_map.values())
        print(f"[*] 站点融合与去重完成：共汇聚优质点播站点 {len(merged_sites)} 个")
        return merged_sites

    def rebuild_config_1(self, merged_sites: List[Dict]) -> bool:
        """重构并输出 1.json 单仓配置"""
        if len(merged_sites) < 10:
            print("[!] 熔断保护触发：融合站点数量不足 10 个，放弃覆盖 1.json 以防止配置损坏！")
            return False

        # 保留现有的 parses, rules, doh 等高级配置
        existing_data = {}
        if OUTPUT_CONFIG_1.exists():
            try:
                with open(OUTPUT_CONFIG_1, "r", encoding="utf-8") as fp:
                    existing_data = json.load(fp)
            except Exception:
                pass

        # 优先把网盘、热播站点排在前面
        def site_priority(s):
            name = s.get("name", "")
            if any(k in name for k in ["阿里", "夸克", "网盘", "4K", "Tg", "玩偶", "至臻"]):
                return 0
            if any(k in name for k in ["厂长", "荐片", "农民", "低端", "爱看", "苹果"]):
                return 1
            return 2

        sorted_sites = sorted(merged_sites, key=site_priority)
        selected_sites = sorted_sites[:MAX_SITES_OUTPUT]

        new_config = {
            "spider": existing_data.get("spider", "https://jihulab.com/yoursmile66/TVBox/-/raw/main/Yoursmile.jar"),
            "wallpaper": existing_data.get("wallpaper", "https://深色壁纸.xxooo.cf/"),
            "sites": selected_sites,
            "parses": existing_data.get("parses", []),
            "lives": existing_data.get("lives", []),
            "logo": existing_data.get("logo", "https://gh-proxy.com/raw.githubusercontent.com/yoursmile66/TVBox/refs/heads/main/json/NanFeng.gif"),
            "rules": existing_data.get("rules", []),
            "doh": existing_data.get("doh", []),
            "ijk": existing_data.get("ijk", []),
            "ads": existing_data.get("ads", [])
        }

        try:
            with open(OUTPUT_CONFIG_1, "w", encoding="utf-8") as fp:
                json.dump(new_config, fp, ensure_ascii=False, indent=2)
            print(f"[√] 成功生成并更新: {OUTPUT_CONFIG_1.name} (含 {len(selected_sites)} 个精选站点)")
            return True
        except Exception as e:
            print(f"[!] 写入 1.json 失败: {e}")
            return False

    def rebuild_warehouse_txt(self) -> bool:
        """重构并输出 自用仓库.txt 多仓列表"""
        urls_list = [
            {
                "url": "https://wget.la/https://raw.githubusercontent.com/niubihu1/tvbox-/main/1.json",
                "name": "🚀自用优选线路🚀"
            }
        ]

        seen_urls = {urls_list[0]["url"]}

        # 加入全网验证存活的多仓和优质单仓线路（按得分排序）
        top_candidates = [r for r in self.alive_results if r["score"] >= 50]
        for c in top_candidates:
            url = c["url"]
            name = c.get("name", "")
            # 过滤内部或者重复
            if url in seen_urls or "niubihu1/tvbox-" in url:
                continue
            seen_urls.add(url)
            
            clean_name = clean_site_name(name) if name else "全网精选线路"
            clean_name = f"🚀{clean_name} [{c['latency']}ms]"
            
            urls_list.append({
                "url": url,
                "name": clean_name
            })
            if len(urls_list) >= 25: # 保留前 25 条极速稳定线路
                break

        output_data = {
            "urls": urls_list
        }

        try:
            with open(OUTPUT_REPO_TXT, "w", encoding="utf-8") as fp:
                fp.write("// 此多仓接口列表由 auto_engine 自动化巡检引擎每日实时测速生成\n")
                fp.write(json.dumps(output_data, ensure_ascii=False, indent=4))
            print(f"[√] 成功生成并更新: {OUTPUT_REPO_TXT.name} (含 {len(urls_list)} 条精选活跃线路)")
            return True
        except Exception as e:
            print(f"[!] 写入 自用仓库.txt 失败: {e}")
            return False

    def run_all(self) -> bool:
        merged_sites = self.extract_and_merge_sites()
        ok1 = self.rebuild_config_1(merged_sites)
        ok2 = self.rebuild_warehouse_txt()
        return ok1 and ok2
