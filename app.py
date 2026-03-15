from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json
from urllib.parse import quote
from config import Config, OMDB_API_KEY
from douban_movie_scraper import DoubanMovieScraper
from movie_translator import get_omdb_name, get_douban_name
from rt_scraper import RTScraper

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

    # ---- 使用大模型翻译获取中英文名称 ----
    # get_omdb_name：中文→英文（英文直接返回）
    # get_douban_name：英文→中文（中文直接返回）
    omdb_search_name = get_omdb_name(movie_name)
    douban_search_name = get_douban_name(movie_name)

    if omdb_search_name != movie_name:
        print(f"中文搜索，大模型翻译为英文: {movie_name} -> {omdb_search_name}")
    if douban_search_name != movie_name:
        print(f"英文搜索，大模型翻译为中文: {movie_name} -> {douban_search_name}")

    # 先尝试 OMDb 搜索
    omdb_data = search_omdb(omdb_search_name)

    # ---- 如果 OMDb 找不到（如非英语电影），尝试豆瓣单独返回结果 ----
    if not omdb_data:
        import re as _re
        print(f"OMDb 未找到 '{omdb_search_name}'，尝试仅通过豆瓣返回数据")
        douban_data = get_douban_rating(douban_search_name, movie_name)
        if douban_data and douban_data.get('score', 0) and float(douban_data['score']) > 0:
            # 用豆瓣搜索结果中的电影信息构建基本数据
            douban_full = get_douban_full_info(douban_search_name, movie_name)

            # 从豆瓣合并标题（如"闪灵 The Shining"）中提取英文名，用于 OMDb/RT 查询
            english_title = None
            if douban_full:
                combined = douban_full.get('title', '')
                en_match = _re.search(r'[A-Za-z][A-Za-z0-9\s:\',!?&\-]{2,}', combined)
                if en_match:
                    english_title = en_match.group(0).strip()
                    print(f"从豆瓣标题提取英文名: {english_title}")

            # 用英文名重试 OMDb（可能获取到 IMDb 评分）
            omdb_retry = None
            if english_title:
                omdb_retry = search_omdb(english_title)

            # 确定海报：优先豆瓣，若无则回退到 OMDb 重试结果
            douban_poster = (douban_full.get('poster', '') if douban_full else '') or ''
            if not douban_poster or douban_poster == 'N/A':
                # 豆瓣无海报，尝试 OMDb 重试结果
                omdb_poster = (omdb_retry.get('Poster', '') if omdb_retry else '') or ''
                if omdb_poster == 'N/A':
                    omdb_poster = ''
                final_poster = omdb_poster
                if final_poster:
                    print(f"[Poster] 豆瓣无海报，使用 OMDb 海报")
            else:
                final_poster = douban_poster

            movie_info = {
                'title': douban_full.get('title', movie_name) if douban_full else movie_name,
                'year': douban_full.get('year', '') if douban_full else '',
                'genre': '、'.join(douban_full.get('genres', [])) if douban_full else '',
                'director': '、'.join(douban_full.get('directors', [])) if douban_full else '',
                'actors': '、'.join(douban_full.get('casts', [])) if douban_full else '',
                'plot': douban_full.get('summary', '') if douban_full else '',
                'poster': final_poster,
                'imdb': None,
                'rottenTomatoes': None,
                'douban': douban_data
            }

            # 如果 OMDb 重试成功，填入 IMDb 评分
            if omdb_retry:
                if omdb_retry.get('imdbRating') and omdb_retry.get('imdbRating') != 'N/A':
                    movie_info['imdb'] = {
                        'score': omdb_retry['imdbRating'],
                        'votes': parse_votes(omdb_retry.get('imdbVotes', '0'))
                    }

            # 用英文名抓取 RT 评分（传入年份以提高匹配准确性）
            if english_title:
                rt_source = omdb_retry if omdb_retry else {}
                douban_year = douban_full.get('year', '') if douban_full else ''
                rt_data = get_rotten_tomatoes_scores(rt_source, english_title,
                                                     year=douban_year)
                if rt_data:
                    movie_info['rottenTomatoes'] = rt_data

            return movie_info
        return None

    # 确定海报：优先 OMDb，若无则从豆瓣获取
    omdb_poster = omdb_data.get('Poster', '') or ''
    if omdb_poster == 'N/A':
        omdb_poster = ''

    # 构建返回数据（暂用 OMDb 海报，稍后可能被豆瓣海报替换）
    movie_info = {
        'title': omdb_data.get('Title', ''),
        'year': omdb_data.get('Year', ''),
        'genre': omdb_data.get('Genre', ''),
        'director': omdb_data.get('Director', ''),
        'actors': omdb_data.get('Actors', ''),
        'plot': omdb_data.get('Plot', ''),
        'poster': omdb_poster,
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

    # 烂番茄评分（OMDb 专业分 + RT 网站抓取观众分）
    rt_data = get_rotten_tomatoes_scores(omdb_data, omdb_search_name,
                                         year=omdb_data.get('Year', ''))
    if rt_data:
        movie_info['rottenTomatoes'] = rt_data

    # 豆瓣评分
    douban_data = get_douban_rating(douban_search_name, movie_name, omdb_data.get('imdbID'))
    if douban_data:
        movie_info['douban'] = douban_data

    # ---- 海报回退：若 OMDb 无海报，尝试从豆瓣获取 ----
    if not omdb_poster:
        try:
            scraper = DoubanMovieScraper(delay_enable=True)
            # 按候选顺序搜索：中文名优先，再尝试原始输入
            poster_candidates = [douban_search_name]
            if movie_name != douban_search_name:
                poster_candidates.append(movie_name)
            for cand in poster_candidates:
                douban_info = scraper.search_movie(cand)
                if douban_info and douban_info.get('poster'):
                    movie_info['poster'] = douban_info['poster']
                    print(f"[Poster] OMDb 无海报，使用豆瓣海报（搜索词：{cand}）")
                    break
        except Exception as e:
            print(f"[Poster] 获取豆瓣海报失败: {e}")

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

def get_rotten_tomatoes_scores(omdb_data, movie_name, year=None):
    """
    获取烂番茄评分：
    - 专业评分（Tomatometer）：优先从 OMDb 数据中提取，其次用 Metascore 代替
    - 观众评分（Audience Score）：从 RT 网站直接抓取

    :param omdb_data: OMDb API 返回的电影数据（可为空 dict）
    :param movie_name: 英文电影名（用于 RT 网站搜索）
    :param year: 上映年份（可选，用于区分同名电影）
    :return: {'critic': '87', 'audience': '91'} 或 None
    """
    rt_data = {}

    # 1. 专业评分：从 OMDb 的 Ratings 数组提取
    ratings = omdb_data.get('Ratings', [])
    for rating in ratings:
        if rating.get('Source') == 'Rotten Tomatoes':
            rt_data['critic'] = rating.get('Value', '').replace('%', '')
            break

    # 备用：用 Metascore 作为专业评分
    if 'critic' not in rt_data:
        metascore = omdb_data.get('Metascore', '')
        if metascore and metascore != 'N/A':
            rt_data['critic'] = metascore

    # 2. 观众评分（同时也可补充专业分）：直接从 RT 网站抓取
    try:
        rt_scraper_obj = RTScraper()
        scraped = rt_scraper_obj.get_movie_scores(movie_name, year=year)
        if scraped:
            # RT 网站的专业分覆盖优先级更高（来源最权威）
            if scraped.get('critic'):
                rt_data['critic'] = scraped['critic']
            if scraped.get('audience'):
                rt_data['audience'] = scraped['audience']
    except Exception as e:
        print(f"[RT] 抓取评分失败: {e}")

    return rt_data if rt_data else None

def get_douban_rating(search_name, original_name, imdb_id=None):
    """获取豆瓣评分（仅返回分数和票数）
    
    Args:
        search_name: 用于豆瓣搜索的名称（优先用中文）
        original_name: 用户原始输入的名称
        imdb_id: IMDb ID（可选）
    """
    try:
        print(f"Getting Douban rating for: {search_name} (original: {original_name})")
        scraper = DoubanMovieScraper(delay_enable=True)

        # 构建搜索候选列表：优先中文名，再原始名，再英文名（若不同）
        candidates = [search_name]
        if original_name and original_name != search_name:
            candidates.append(original_name)

        for name in candidates:
            rating_info = scraper.get_movie_rating_only(name)
            print(f"Douban rating for '{name}': {rating_info}")
            if rating_info and rating_info.get('score', 0) > 0:
                return {
                    'score': str(rating_info['score']),
                    'votes': rating_info['votes']
                }

        return None

    except Exception as e:
        print(f"获取豆瓣评分时出错: {str(e)}")
        return None


def get_douban_full_info(search_name, original_name):
    """获取豆瓣电影完整信息（用于 OMDb 找不到时填充基本信息）
    
    Args:
        search_name: 优先用中文名搜索
        original_name: 用户原始输入
    """
    try:
        scraper = DoubanMovieScraper(delay_enable=True)
        candidates = [search_name]
        if original_name and original_name != search_name:
            candidates.append(original_name)

        for name in candidates:
            info = scraper.search_movie(name)
            if info and info.get('rating', 0) > 0:
                return info

        return None

    except Exception as e:
        print(f"获取豆瓣完整信息时出错: {str(e)}")
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