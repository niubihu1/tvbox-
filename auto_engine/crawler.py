"""
crawler.py - 全网 TVBox 接口并发抓取与解析模块
采用线程池并发抓取网络源，极速解析本地汇总大库
"""
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from auto_engine.config import USER_SOURCES, EXPANDED_SOURCES, LOCAL_SUMMARY_FILE, GITHUB_PROXIES

URL_PATTERN = re.compile(r'https?://[^\s<>"\',;\)\]\}\\\^`]+', re.IGNORECASE)

EXCLUDE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.apk', '.zip', '.7z', '.tar', '.gz', '.css', '.md'}

def clean_extracted_url(url: str) -> str:
    url = url.strip().strip('"\'()[]{}<>,;。，、：:\\^`')
    # 处理类似 http...json, 的尾随符号
    while url and url[-1] in '.,;:)>\'"}]':
        url = url[:-1]
    return url

def is_valid_interface_url(url: str) -> bool:
    if not url.startswith("http://") and not url.startswith("https://"):
        return False
    if "127.0.0.1" in url or "localhost" in url:
        return False
    if len(url) < 12:
        return False
    # 必须含有域名主机点号
    domain_part = url.split("://", 1)[1].split("/", 1)[0]
    if "." not in domain_part:
        return False
    lower = url.lower()
    for ext in EXCLUDE_EXTS:
        if lower.endswith(ext):
            return False
    if any(k in lower for k in ["weixin.qq.com", "baidu.com/s", "pan.quark.cn", "drive.uc.cn", "github.com/login", "alipay.com"]):
        return False
    return True

class TVBoxCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "okhttp/4.9.0 Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.candidates: Dict[str, Dict] = {}

    def add_candidate(self, name: str, url: str, source: str):
        url = clean_extracted_url(url)
        if is_valid_interface_url(url) and url not in self.candidates:
            self.candidates[url] = {
                "name": name.strip() if name else "全网精选源",
                "url": url,
                "source": source
            }

    def crawl_local_summary_file(self) -> int:
        if not LOCAL_SUMMARY_FILE.exists():
            print(f"[!] 本地大库文件未找到: {LOCAL_SUMMARY_FILE}", flush=True)
            return 0
            
        print(f"[*] 正在解析本地汇总库: {LOCAL_SUMMARY_FILE.name}", flush=True)
        count = 0
        try:
            with open(LOCAL_SUMMARY_FILE, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith("//"):
                        continue
                    
                    name = ""
                    url = ""
                    if "http://" in line or "https://" in line:
                        parts = re.split(r'[:：\s\t]+(?=https?://)', line, maxsplit=1)
                        if len(parts) == 2:
                            name, url = parts[0], parts[1]
                        else:
                            url = parts[0]
                            
                    matches = URL_PATTERN.findall(url if url else line)
                    for m in matches:
                        if is_valid_interface_url(m):
                            self.add_candidate(name=name, url=m, source="本地大库汇总")
                            count += 1
        except Exception as e:
            print(f"[!] 读取本地大库异常: {e}", flush=True)
            
        print(f"[+] 本地汇总库解析完成，发现 {count} 个候选链接 (去重后 {len(self.candidates)} 个)", flush=True)
        return count

    def _fetch_single_source(self, item: Dict):
        name = item["name"]
        url = item["url"]
        found = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                matches = URL_PATTERN.findall(resp.text)
                for m in matches:
                    if is_valid_interface_url(m):
                        found.append((f"{name}_源", m, name))
            elif "raw.githubusercontent.com" in url:
                # 尝试带镜像代理拉取
                for proxy in GITHUB_PROXIES[:2]:
                    try:
                        p_resp = requests.get(proxy + url, headers=self.headers, timeout=4)
                        if p_resp.status_code == 200:
                            matches = URL_PATTERN.findall(p_resp.text)
                            for m in matches:
                                if is_valid_interface_url(m):
                                    found.append((f"{name}_源", m, f"{name}(加速)"))
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        return name, found

    def crawl_online_sources(self):
        print(f"[*] 启动多线程并发抓取在线渠道 (共 {len(USER_SOURCES) + len(EXPANDED_SOURCES)} 个渠道)...", flush=True)
        
        # 1. 注入直接配置源
        for item in EXPANDED_SOURCES:
            self.add_candidate(name=item["name"], url=item["url"], source="行业精选长效源")

        # 2. 多线程并发请求在线渠道
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._fetch_single_source, src) for src in USER_SOURCES]
            for fut in as_completed(futures):
                name, found = fut.result()
                if found:
                    for sname, surl, ssrc in found:
                        self.add_candidate(sname, surl, ssrc)
                    print(f"  -> [{name}] 成功提取 {len(found)} 个候选接口", flush=True)
                else:
                    print(f"  -> [{name}] 抓取完成 (未发现新链接或超时)", flush=True)

    def run_all(self) -> List[Dict]:
        self.crawl_local_summary_file()
        self.crawl_online_sources()
        print(f"\n[√] 全网抓取汇总完成！共收集有效候选接口 {len(self.candidates)} 个。", flush=True)
        return list(self.candidates.values())
