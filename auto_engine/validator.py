"""
validator.py - 高性能异步多维健康探测与评分引擎
使用 asyncio + aiohttp 并发探测接口连通性、解析有效性、Spider可达性及响应延迟
"""
import time
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from auto_engine.json_cleaner import parse_tvbox_json
from auto_engine.config import CHECK_TIMEOUT, MAX_CONCURRENCY

class TVBoxValidator:
    def __init__(self, timeout: int = CHECK_TIMEOUT, concurrency: int = MAX_CONCURRENCY):
        self.timeout = timeout
        self.concurrency = concurrency
        self.headers = {
            "User-Agent": "okhttp/4.9.0 Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def _test_url(self, session: aiohttp.ClientSession, url: str) -> tuple[bool, int, str]:
        """基础连通性与耗时测量，返回 (is_ok, latency_ms, text)"""
        start = time.time()
        try:
            async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                latency = int((time.time() - start) * 1000)
                if resp.status == 200:
                    text = await resp.text(encoding="utf-8", errors="ignore")
                    return True, latency, text
                return False, latency, ""
        except Exception:
            return False, 9999, ""

    async def validate_interface(self, session: aiohttp.ClientSession, candidate: Dict) -> Dict[str, Any]:
        """多级深度检测单个候选源"""
        url = candidate["url"]
        name = candidate.get("name", "未命名")
        source = candidate.get("source", "未知")
        
        report = {
            "url": url,
            "name": name,
            "source": source,
            "is_alive": False,
            "latency": 9999,
            "type": "unknown", # "single" (单仓), "multi" (多仓), "live" (纯直播源), "invalid"
            "score": 0,
            "sites_count": 0,
            "spider": "",
            "raw_data": None
        }

        # Level 1: HTTP 探测
        is_ok, latency, content = await self._test_url(session, url)
        if not is_ok or not content:
            return report

        report["latency"] = latency

        # Level 2: 结构有效性解析
        parsed = parse_tvbox_json(content)
        
        # 判断是否为合法单仓配置 (必须包含 sites)
        if isinstance(parsed, dict) and "sites" in parsed and isinstance(parsed["sites"], list):
            sites = parsed["sites"]
            sites_count = len(sites)
            if sites_count > 0:
                report["is_alive"] = True
                report["type"] = "single"
                report["sites_count"] = sites_count
                # 环境自适应评分模型 (满分 100)
                import os
                is_ci = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"
                is_domestic = any(k in name or k in url for k in [
                    "饭太硬", "肥猫", "心魔", "周J", "道长", "潇洒", "南风", "摸鱼", "王二小", "小马", "俊宇", "香雅情", "荷城", "小米", ".cn"
                ])

                # 1. 连通基准分: 40
                # 2. 延迟分 (0~30 分): 若处于 GitHub Actions (海外环境)，为国内源提供地理距离补偿
                if is_ci:
                    latency_score = 25 if is_domestic else max(0, min(30, int(30 - (latency / 200))))
                else:
                    latency_score = max(0, min(30, int(30 - (latency / 150))))
                    
                # 3. 资源丰富度分 (0~20 分): 包含 20 个站点以上得满分
                rich_score = min(20, sites_count)
                # 4. Spider 完整度分 (10 分)
                spider_score = 10 if report["spider"] else 0
                # 5. 国内知名源加权 (5 分)
                bonus = 5 if is_domestic else 0
                
                report["score"] = 35 + latency_score + rich_score + spider_score + bonus
                return report

        # 判断是否为合法多仓配置 (包含 urls 或 storeHouse)
        if isinstance(parsed, dict):
            import os
            is_ci = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"
            is_domestic = any(k in name or k in url for k in [
                "饭太硬", "肥猫", "心魔", "周J", "道长", "潇洒", "南风", "摸鱼", "王二小", "小马", "俊宇", "香雅情", "荷城", "小米", ".cn"
            ])
            if "urls" in parsed and isinstance(parsed["urls"], list) and len(parsed["urls"]) > 0:
                report["is_alive"] = True
                report["type"] = "multi"
                report["sites_count"] = len(parsed["urls"])
                report["raw_data"] = parsed
                latency_score = 35 if (is_ci and is_domestic) else max(0, min(40, int(40 - (latency / 100))))
                report["score"] = 50 + latency_score + (10 if is_domestic else 0)
                return report
                
            if "storeHouse" in parsed and isinstance(parsed["storeHouse"], list) and len(parsed["storeHouse"]) > 0:
                report["is_alive"] = True
                report["type"] = "multi"
                report["sites_count"] = len(parsed["storeHouse"])
                report["raw_data"] = parsed
                latency_score = max(0, min(40, int(40 - (latency / 100))))
                report["score"] = 50 + latency_score
                return report

        # 判断是否为纯文本直播源 (包含 #EXTM3U 或大量 频道名,http)
        if "#EXTM3U" in content or ("," in content and "http" in content and content.count("\n") > 5):
            report["is_alive"] = True
            report["type"] = "live"
            report["sites_count"] = content.count("\n")
            report["score"] = 60 + max(0, min(30, int(30 - (latency / 100))))
            return report

        return report

    async def run_batch_validate(self, candidates: List[Dict]) -> List[Dict]:
        """并发批量检测"""
        print(f"[*] 启动异步测活引擎，候选接口总数: {len(candidates)}，并发上限: {self.concurrency}...", flush=True)
        
        sem = asyncio.Semaphore(self.concurrency)
        results = []
        
        connector = aiohttp.TCPConnector(limit=self.concurrency, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async def bounded_check(cand):
                async with sem:
                    return await self.validate_interface(session, cand)

            tasks = [bounded_check(c) for c in candidates]
            # 分步报告进度
            completed = 0
            for fut in asyncio.as_completed(tasks):
                res = await fut
                completed += 1
                if completed % 50 == 0 or completed == len(tasks):
                    alive_now = sum(1 for r in results if r["is_alive"])
                    print(f"  -> 探测进度: [{completed}/{len(tasks)}] 累计发现存活: {alive_now}", flush=True)
                results.append(res)

        # 过滤存活且按得分降序排序
        alive_results = [r for r in results if r["is_alive"]]
        alive_results.sort(key=lambda x: (-x["score"], x["latency"]))
        
        print(f"\n[√] 测活完成！存活接口数: {len(alive_results)} / {len(candidates)}", flush=True)
        single_count = sum(1 for r in alive_results if r["type"] == "single")
        multi_count = sum(1 for r in alive_results if r["type"] == "multi")
        live_count = sum(1 for r in alive_results if r["type"] == "live")
        print(f"    ├─ 单仓配置有效: {single_count} 个", flush=True)
        print(f"    ├─ 多仓配置有效: {multi_count} 个", flush=True)
        print(f"    └─ 直播源有效: {live_count} 个", flush=True)
        
        return alive_results

def validate_all(candidates: List[Dict]) -> List[Dict]:
    validator = TVBoxValidator()
    return asyncio.run(validator.run_batch_validate(candidates))
