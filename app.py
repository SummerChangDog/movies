from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json
from urllib.parse import quote
from config import Config, OMDB_API_KEY
from douban_movie_scraper import DoubanMovieScraper

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# 缓存配置
CACHE_DIR = Config.CACHE_DIR
CACHE_DURATION = timedelta(hours=Config.CACHE_DURATION_HOURS)

# API配置
OMDB_BASE_URL = 'http://www.omdbapi.com/'

# 确保缓存目录存在
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

@app.route('/api/test')
def test_api():
    """测试API端点"""
    return jsonify({'status': 'API is working!'})

@app.route('/api/search', methods=['POST'])
def search_movie():
    """搜索电影并返回聚合评分"""
    try:
        data = request.get_json()
        movie_name = data.get('movie_name', '').strip()
        
        if not movie_name:
            return jsonify({'error': '请输入电影名称'}), 400
        
        # 验证输入，移除潜在的危险字符
        # 只允许字母、数字、空格、中文字符和一些常见符号
        import re
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9\s\-\':,.!?&]+$', movie_name):
            return jsonify({'error': '电影名称包含不支持的字符'}), 400
        
        # 限制输入长度
        if len(movie_name) > 100:
            return jsonify({'error': '电影名称过长'}), 400
        
        # 检查缓存
        cache_file = get_cache_filename(movie_name)
        cached_data = load_from_cache(cache_file)
        if cached_data:
            return jsonify(cached_data)
        
        # 获取电影数据
        movie_data = get_movie_data(movie_name)
        
        if not movie_data:
            return jsonify({'error': '未找到该电影'}), 404
        
        # 保存到缓存
        save_to_cache(cache_file, movie_data)
        
        return jsonify(movie_data)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': '服务器错误，请稍后重试'}), 500

def get_movie_data(movie_name):
    """获取电影数据"""
    # 首先通过OMDb API搜索电影
    omdb_data = search_omdb(movie_name)
    
    if not omdb_data:
        return None
    
    # 构建返回数据
    movie_info = {
        'title': omdb_data.get('Title', ''),
        'year': omdb_data.get('Year', ''),
        'genre': omdb_data.get('Genre', ''),
        'director': omdb_data.get('Director', ''),
        'actors': omdb_data.get('Actors', ''),
        'plot': omdb_data.get('Plot', ''),
        'poster': omdb_data.get('Poster', ''),
        'imdb': None,
        'rottenTomatoes': None,
        'douban': None
    }
    
    # IMDb评分
    if omdb_data.get('imdbRating') and omdb_data.get('imdbRating') != 'N/A':
        movie_info['imdb'] = {
            'score': omdb_data.get('imdbRating'),
            'votes': parse_votes(omdb_data.get('imdbVotes', '0'))
        }
    
    # 烂番茄评分
    rt_data = extract_rotten_tomatoes(omdb_data)
    if rt_data:
        movie_info['rottenTomatoes'] = rt_data
    
    # 豆瓣评分（使用模拟数据或豆瓣API）
    douban_data = get_douban_rating(movie_name, omdb_data.get('imdbID'))
    if douban_data:
        movie_info['douban'] = douban_data
    
    return movie_info

def search_omdb(movie_name):
    """通过OMDb API搜索电影"""
    
    # 临时模拟数据，用于测试
    mock_data = {
        'Inception': {
            'Title': 'Inception',
            'Year': '2010',
            'Genre': 'Action, Sci-Fi, Thriller',
            'Director': 'Christopher Nolan',
            'Actors': 'Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page',
            'Plot': 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.',
            'Poster': 'https://m.media-amazon.com/images/M/MV5BMjAxMzY3NjcxNF5BMl5BanBnXkFtZTcwNTI5OTM0Mw@@._V1_SX300.jpg',
            'imdbRating': '8.8',
            'imdbVotes': '2,250,000',
            'imdbID': 'tt1375666',
            'Ratings': [
                {'Source': 'Rotten Tomatoes', 'Value': '87%'}
            ],
            'Metascore': '74'
        },
        'The Shawshank Redemption': {
            'Title': 'The Shawshank Redemption',
            'Year': '1994',
            'Genre': 'Drama',
            'Director': 'Frank Darabont',
            'Actors': 'Tim Robbins, Morgan Freeman, Bob Gunton',
            'Plot': 'Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.',
            'Poster': 'https://m.media-amazon.com/images/M/MV5BMDFkYTc0MGEtZmNhMC00ZDIzLWFmNTEtODM1ZmRlYWMwMWFmXkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_SX300.jpg',
            'imdbRating': '9.3',
            'imdbVotes': '2,600,000',
            'imdbID': 'tt0111161',
            'Ratings': [
                {'Source': 'Rotten Tomatoes', 'Value': '91%'}
            ],
            'Metascore': '81'
        },
        '肖申克的救赎': {
            'Title': 'The Shawshank Redemption',
            'Year': '1994',
            'Genre': 'Drama',
            'Director': 'Frank Darabont',
            'Actors': 'Tim Robbins, Morgan Freeman, Bob Gunton',
            'Plot': 'Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.',
            'Poster': 'https://m.media-amazon.com/images/M/MV5BMDFkYTc0MGEtZmNhMC00ZDIzLWFmNTEtODM1ZmRlYWMwMWFmXkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_SX300.jpg',
            'imdbRating': '9.3',
            'imdbVotes': '2,600,000',
            'imdbID': 'tt0111161',
            'Ratings': [
                {'Source': 'Rotten Tomatoes', 'Value': '91%'}
            ],
            'Metascore': '81'
        }
    }
    
    # 检查是否有有效的API密钥
    if OMDB_API_KEY and OMDB_API_KEY != 'your-api-key-here':
        print(f"Searching OMDb for: {movie_name}")
        print(f"Using API key: {OMDB_API_KEY[:4]}...")
        
        try:
            # 尝试使用真实API
            search_params = {
                'apikey': OMDB_API_KEY,
                's': movie_name,
                'type': 'movie'
            }
            
            search_response = requests.get(OMDB_BASE_URL, params=search_params, timeout=10)
            search_data = search_response.json()
            
            if search_data.get('Response') == 'True' and search_data.get('Search'):
                # 获取第一个搜索结果的详细信息
                imdb_id = search_data['Search'][0]['imdbID']
                
                detail_params = {
                    'apikey': OMDB_API_KEY,
                    'i': imdb_id,
                    'plot': 'full'
                }
                
                detail_response = requests.get(OMDB_BASE_URL, params=detail_params, timeout=10)
                return detail_response.json()
        except Exception as e:
            print(f"OMDb API error: {str(e)}")
    
    # 如果API调用失败或没有有效密钥，使用模拟数据
    print("Using mock data for testing (OMDb API key invalid or not set)")
    return mock_data.get(movie_name, None)

def extract_rotten_tomatoes(omdb_data):
    """从OMDb数据中提取烂番茄评分"""
    rt_data = {}
    
    # 从Ratings数组中查找烂番茄评分
    ratings = omdb_data.get('Ratings', [])
    for rating in ratings:
        if rating.get('Source') == 'Rotten Tomatoes':
            rt_data['critic'] = rating.get('Value', '').replace('%', '')
            break
    
    # 如果有Metascore，可以作为参考
    if omdb_data.get('Metascore') and omdb_data.get('Metascore') != 'N/A':
        # Metascore通常与专业评分相关
        if 'critic' not in rt_data:
            # 将Metascore转换为百分比形式
            rt_data['critic'] = omdb_data.get('Metascore')
    
    return rt_data if rt_data else None

def get_douban_rating(movie_name, imdb_id=None):
    """获取豆瓣评分"""
    try:
        # 创建豆瓣爬虫实例
        scraper = DoubanMovieScraper(delay_enable=True)
        
        # 获取电影评分信息
        rating_info = scraper.get_movie_rating_only(movie_name)
        
        if rating_info and rating_info['score'] > 0:
            return {
                'score': str(rating_info['score']),
                'votes': rating_info['votes']
            }
        
        # 如果直接搜索没有结果，尝试不同的搜索词
        # 例如，如果是英文名，尝试常见的中文译名
        alternative_names = {
            'The Shawshank Redemption': '肖申克的救赎',
            'Inception': '盗梦空间',
            'Interstellar': '星际穿越',
            'The Dark Knight': '蝙蝠侠：黑暗骑士',
            'The Godfather': '教父',
            'Forrest Gump': '阿甘正传'
        }
        
        if movie_name in alternative_names:
            alt_name = alternative_names[movie_name]
            rating_info = scraper.get_movie_rating_only(alt_name)
            if rating_info and rating_info['score'] > 0:
                return {
                    'score': str(rating_info['score']),
                    'votes': rating_info['votes']
                }
        
        return None
        
    except Exception as e:
        print(f"获取豆瓣评分时出错: {str(e)}")
        return None

def parse_votes(votes_str):
    """解析投票数字符串"""
    try:
        return int(votes_str.replace(',', ''))
    except:
        return 0

def get_cache_filename(movie_name):
    """生成缓存文件名"""
    # 清理文件名中的特殊字符
    safe_name = "".join(c for c in movie_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    return os.path.join(CACHE_DIR, f"{safe_name}.json")

def load_from_cache(cache_file):
    """从缓存加载数据"""
    if not os.path.exists(cache_file):
        return None
    
    try:
        # 检查缓存是否过期
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - file_time > CACHE_DURATION:
            return None
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def save_to_cache(cache_file, data):
    """保存数据到缓存"""
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

if __name__ == '__main__':
    # 检查是否设置了API密钥
    if not OMDB_API_KEY:
        print("警告：未设置OMDB_API_KEY，请在环境变量或config.py中设置")
        print("您可以从 http://www.omdbapi.com/apikey.aspx 获取免费的API密钥")
    
    # 运行Flask应用
    app.run(debug=True, host='0.0.0.0', port=5000)