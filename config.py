import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# OMDb API配置
# 请从 http://www.omdbapi.com/apikey.aspx 获取免费的API密钥
# 然后设置环境变量 OMDB_API_KEY 或直接在下面填写
# 注意：OMDb API同时提供IMDb和烂番茄(Rotten Tomatoes)的评分数据
OMDB_API_KEY = os.getenv('OMDB_API_KEY', 'dab94b1c')

# 豆瓣API配置（如果有）
# 注意：豆瓣API需要申请，目前使用模拟数据
DOUBAN_API_KEY = os.getenv('DOUBAN_API_KEY', '')

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
