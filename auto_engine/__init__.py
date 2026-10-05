"""
auto_engine - TVBox 自动化接口巡检、重组与全网源汇聚系统
"""
import sys

# 解决 Windows 默认控制台编码 GBK 导致 emoji 崩溃问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

__version__ = "1.0.0"
