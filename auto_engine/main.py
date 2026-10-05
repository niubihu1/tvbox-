import sys
from pathlib import Path

# 确保 Windows 终端输出 UTF-8 避免 Emoji 编码异常
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import argparse
from auto_engine.crawler import TVBoxCrawler
from auto_engine.validator import validate_all
from auto_engine.composer import TVBoxComposer
from auto_engine.config import ROOT_DIR

DATA_DIR = ROOT_DIR / "auto_engine" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_FILE = DATA_DIR / "candidates.json"
ALIVE_FILE = DATA_DIR / "alive_results.json"

def run_pipeline(crawl: bool = True, check: bool = True, rebuild: bool = True):
    print("=" * 60)
    print("🚀 TVBox 自动化接口巡检、重组与全网源汇聚系统启动")
    print("=" * 60)
    
    candidates = []
    
    # 步骤 1: 全网采集
    if crawl:
        crawler = TVBoxCrawler()
        candidates = crawler.run_all()
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as fp:
            json.dump(candidates, fp, ensure_ascii=False, indent=2)
        print(f"[+] 候选源已持久化至: {CANDIDATES_FILE}")
    else:
        if CANDIDATES_FILE.exists():
            with open(CANDIDATES_FILE, "r", encoding="utf-8") as fp:
                candidates = json.load(fp)
            print(f"[*] 从缓存载入候选接口: {len(candidates)} 个")
        else:
            print("[!] 未找到候选缓存，强制开启爬取...")
            crawler = TVBoxCrawler()
            candidates = crawler.run_all()

    # 步骤 2: 测活检测
    alive_results = []
    if check:
        alive_results = validate_all(candidates)
        # 持久化轻量统计缓存（移除庞大的 raw_data 字段，避免撑大 Git 仓库）
        lightweight_alive = [{k: v for k, v in r.items() if k != "raw_data"} for r in alive_results]
        with open(ALIVE_FILE, "w", encoding="utf-8") as fp:
            json.dump(lightweight_alive, fp, ensure_ascii=False, indent=2)
        print(f"[+] 存活结果(轻量摘要)已持久化至: {ALIVE_FILE} (仅约 {ALIVE_FILE.stat().st_size / 1024:.1f} KB)", flush=True)
    else:
        if ALIVE_FILE.exists():
            with open(ALIVE_FILE, "r", encoding="utf-8") as fp:
                alive_results = json.load(fp)
            print(f"[*] 从缓存载入存活接口: {len(alive_results)} 个")
        else:
            print("[!] 未找到存活缓存，执行测活...")
            alive_results = validate_all(candidates)

    # 步骤 3: 智能重组与文件生成
    if rebuild:
        print("\n[*] 开始执行配置重构与优化输出...")
        composer = TVBoxComposer(alive_results)
        success = composer.run_all()
        if success:
            print("[√] 全部目标文件更新成功！")
        else:
            print("[!] 重组生成存在告警，请检查控制台输出。")

    print("\n" + "=" * 60)
    print("🎉 自动化巡检与重构流水线执行完毕！")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="TVBox 自动接口巡检与重组系统")
    parser.add_argument("--crawl", action="store_true", help="仅执行全网源采集")
    parser.add_argument("--check", action="store_true", help="仅执行接口测活")
    parser.add_argument("--rebuild", action="store_true", help="仅执行重构生成")
    parser.add_argument("--all", action="store_true", default=True, help="完整全流程执行")
    
    args = parser.parse_args()
    
    if args.crawl and not args.check and not args.rebuild:
        run_pipeline(crawl=True, check=False, rebuild=False)
    elif args.check and not args.crawl and not args.rebuild:
        run_pipeline(crawl=False, check=True, rebuild=False)
    elif args.rebuild and not args.crawl and not args.check:
        run_pipeline(crawl=False, check=False, rebuild=True)
    else:
        run_pipeline(crawl=True, check=True, rebuild=True)

if __name__ == "__main__":
    main()
