import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# OMDb API配置
# 请从 http://www.omdbapi.com/apikey.aspx 获取免费的API密钥
# 通过环境变量 OMDB_API_KEY 或 .env 文件设置，或在启动时由 run.py 交互式收集
# 注意：OMDb API同时提供IMDb和烂番茄(Rotten Tomatoes)的评分数据
OMDB_API_KEY = os.getenv('OMDB_API_KEY', '')

# 豆瓣API配置（如果有）
# 注意：豆瓣API需要申请，目前使用模拟数据
DOUBAN_API_KEY = os.getenv('DOUBAN_API_KEY', '')

# 豆瓣 Cookie 配置（用于绕过豆瓣登录验证）
# 从浏览器登录豆瓣后，打开开发者工具 → Application → Cookies → douban.com
# 复制 bid 和 dbcl2 的值填入下方
DOUBAN_COOKIE_BID    = os.getenv('DOUBAN_COOKIE_BID', '')
DOUBAN_COOKIE_DBCL2  = os.getenv('DOUBAN_COOKIE_DBCL2', '')

# 烂番茄API说明
# 烂番茄评分通过OMDb API获取，无需单独的API密钥
# OMDb API返回的数据中包含了烂番茄的专业评分(Tomatometer)

# 应用配置
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # 缓存配置
    CACHE_DIR = 'cache'
    CACHE_DURATION_HOURS = 24  # 缓存持续时间（小时）
