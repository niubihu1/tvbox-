"""
config.py - TVBox 自动巡检与采集配置文件
"""
from pathlib import Path

# 根目录与路径
ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_DOWNLOAD_DIR = Path(r"C:\Users\admin\Downloads\2026年9月16号TVBox影视接口地址汇总\2026年9月16号TVBox影视接口地址汇总")
LOCAL_SUMMARY_FILE = LOCAL_DOWNLOAD_DIR / "2026年9月16号TVBox影视接口地址汇总.txt"

# 用户提供的全网数据源与监控仓库
USER_SOURCES = [
    # GitHub 仓库
    {"name": "TVAPP", "type": "github_repo", "url": "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md"},
    {"name": "lizhe0326", "type": "github_repo", "url": "https://raw.githubusercontent.com/lizhe0326/tvbox/main/README.md"},
    {"name": "cyao2q_files", "type": "github_repo", "url": "https://raw.githubusercontent.com/cyao2q/files/master/README.md"},
    {"name": "tushen6_Tomorrow", "type": "github_repo", "url": "https://raw.githubusercontent.com/tushen6/Tomorrow/master/README.md"},
    {"name": "noimank", "type": "github_repo", "url": "https://raw.githubusercontent.com/noimank/tvbox/main/README.md"},
    {"name": "Zhou-Li-Bin_QingNing", "type": "github_repo", "url": "https://raw.githubusercontent.com/Zhou-Li-Bin/Tvbox-QingNing/main/README.md"},
    {"name": "qist_tvbox", "type": "github_repo", "url": "https://raw.githubusercontent.com/qist/tvbox/master/README.md"},
    {"name": "wuxierj_TVBox", "type": "github_repo", "url": "https://raw.githubusercontent.com/wuxierj/TVBox/main/README.md"},
    
    # 网页与接口站
    {"name": "zhihu_article", "type": "webpage", "url": "https://zhuanlan.zhihu.com/p/2059482717654348198"},
    {"name": "xlsn0w_gitee", "type": "webpage", "url": "https://gitee.com/xlsn0w/tvbox-source-address/raw/master/README.md"},
    {"name": "yinghezhinan", "type": "webpage", "url": "https://yinghezhinan.com/tvbox-jsonlist/"},
    {"name": "easy321_jk", "type": "webpage", "url": "https://easy321.top/jk/"},
]

# 补充的一线高品质长效源与基线仓库（全网高共识度主流源池）
EXPANDED_SOURCES = [
    # 饭太硬
    {"name": "饭太硬主力线", "type": "direct_config", "url": "http://www.饭太硬.com/tv"},
    {"name": "饭太硬备用线", "type": "direct_config", "url": "http://饭太硬.net/tv"},
    # 肥猫
    {"name": "肥猫主力线", "type": "direct_config", "url": "http://肥猫.com"},
    {"name": "肥猫备用线", "type": "direct_config", "url": "http://肥猫.net/tv"},
    # 道长 dr_py
    {"name": "道长drpy源", "type": "direct_config", "url": "https://raw.githubusercontent.com/hjdhnx/dr_py/main/index.json"},
    # 俊于 / 潇洒 / 南风
    {"name": "潇洒接口", "type": "direct_config", "url": "https://raw.githubusercontent.com/PizazzGY/TVBox/main/api.json"},
    {"name": "南风接口", "type": "direct_config", "url": "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json"},
    {"name": "香雅情", "type": "direct_config", "url": "https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json"},
    {"name": "王二小", "type": "direct_config", "url": "http://tvbox.王二小放牛娃.top"},
    {"name": "荷城茶秀", "type": "direct_config", "url": "http://rihou.cc:88/荷城茶秀"},
    # 摸鱼儿
    {"name": "摸鱼儿主力线", "type": "direct_config", "url": "http://我不是.摸鱼儿.cc"},
    # 巧技
    {"name": "巧技接口", "type": "direct_config", "url": "http://pandown.pro/tvbox/tvbox.json"},
    # 小马
    {"name": "小马接口", "type": "direct_config", "url": "https://szyyds.cn/tv/x.json"},
    # 心魔
    {"name": "心魔接口", "type": "direct_config", "url": "https://raw.githubusercontent.com/yw88075/tvbox/main/yw.json"},
    # 俊宇
    {"name": "俊宇接口", "type": "direct_config", "url": "http://home.jundie.top:81/top98.json"},
    # 菜妮丝
    {"name": "菜妮丝接口", "type": "direct_config", "url": "https://tvbox.cainisi.cf"},
    # 欧歌
    {"name": "欧歌接口", "type": "direct_config", "url": "http://m.nxog.top/api.php?mz=xb&id=1&b=欧歌"},
]

# GitHub 加速镜像前缀池
GITHUB_PROXIES = [
    "https://wget.la/",
    "https://ghproxy.net/",
    "https://gh-proxy.com/",
    "https://mirror.ghproxy.com/",
    "https://github.moeyy.xyz/",
]

# 检测阈值与控制参数
CHECK_TIMEOUT = 6          # 单个请求超时时间（秒）
MAX_CONCURRENCY = 40       # 异步检测最大并发数
MIN_SCORE_THRESHOLD = 50   # 站点保留最低得分阈值 (0-100)
MAX_SITES_OUTPUT = 100     # 1.json 保留的最大精选站点数（达到100个）

# 100 个优质源的黄金分类配额
CATEGORY_QUOTAS = {
    "online": 40,   # 免登录在线影视 (dr_py / 网页爬虫，老人小孩开箱即播)
    "pan": 35,      # 4K 原画与网盘/磁力 (玩偶/至臻/蜡笔/阿里/夸克/UC，发烧友高画质)
    "cms": 15,      # 稳定全网综合采集站 (暴风/红牛/量子/极速，全面兜底)
    "special": 10   # 特色专区 (体育看球/课堂少儿/动漫巴士/预告)
}

# 输出目标文件
OUTPUT_CONFIG_1 = ROOT_DIR / "1.json"
OUTPUT_CONFIG_TV8 = ROOT_DIR / "tv8.json"
OUTPUT_REPO_TXT = ROOT_DIR / "自用仓库.txt"
OUTPUT_LIVE_TXT = ROOT_DIR / "直播源" / "v.txt"

