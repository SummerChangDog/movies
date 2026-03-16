from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json
from urllib.parse import quote, unquote
from config import Config, OMDB_API_KEY
from douban_movie_scraper import DoubanMovieScraper
from movie_translator import get_omdb_name, get_douban_name
from rt_scraper import RTScraper
from imdb_scraper import IMDbRatingScraper

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

@app.route('/api/proxy-image')
def proxy_image():
    """
    图片代理接口，用于绕过豆瓣防盗链。
    豆瓣 CDN 要求 Referer 为 douban.com，浏览器直接加载会被拒绝。
    本接口由服务器携带正确 Referer 取回图片后转发给浏览器。
    用法: /api/proxy-image?url=<encoded_image_url>
    """
    img_url = request.args.get('url', '').strip()
    if not img_url:
        return jsonify({'error': '缺少 url 参数'}), 400

    # 安全校验：只允许代理豆瓣图片域名
    allowed_hosts = ('img1.doubanio.com', 'img2.doubanio.com',
                     'img3.doubanio.com', 'img9.doubanio.com',
                     'img.doubanio.com')
    from urllib.parse import urlparse
    parsed = urlparse(img_url)
    if not any(parsed.netloc.endswith(h) for h in allowed_hosts):
        return jsonify({'error': '仅支持代理豆瓣图片'}), 403

    try:
        headers = {
            'Referer': 'https://movie.douban.com/',
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
        }
        resp = requests.get(img_url, headers=headers, timeout=10, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        return Response(resp.content, content_type=content_type)
    except Exception as e:
        print(f"[ProxyImage] 代理图片失败: {e}")
        return jsonify({'error': '图片获取失败'}), 502

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

            # 按优先级获取英文名并查询 OMDb：
            #   方法一：豆瓣详情页中直接含有 IMDb 链接（最准确，用 ID 直查）
            #   方法二：豆瓣 suggest API 的 sub_title 字段（如 'Jane Eyre'）
            #   方法三：从豆瓣合并标题（如"简爱 Jane Eyre"）正则提取英文名
            english_title = None
            omdb_retry = None
            if douban_full:
                imdb_id_from_douban = douban_full.get('imdb_id', '')
                subtitle_from_douban = douban_full.get('subtitle', '')

                print(f"[OMDb查询] imdb_id='{imdb_id_from_douban}', subtitle='{subtitle_from_douban}', title='{douban_full.get('title','')}'")

                # 方法一：IMDb ID 直查
                if imdb_id_from_douban:
                    print(f"[OMDb] 方法一：用 IMDb ID '{imdb_id_from_douban}' 直接查询")
                    omdb_retry = search_omdb_by_id(imdb_id_from_douban)
                    if omdb_retry:
                        english_title = omdb_retry.get('Title', '')
                        print(f"[OMDb] 方法一成功，标题={english_title}, IMDb={omdb_retry.get('imdbRating')}")
                    else:
                        print(f"[OMDb] 方法一失败（无有效 API Key 或查询出错）")

                # 方法二：豆瓣 suggest subtitle（英文原名）
                if not omdb_retry and subtitle_from_douban:
                    english_title = subtitle_from_douban
                    print(f"[OMDb] 方法二：用豆瓣 subtitle '{english_title}' 搜索")
                    omdb_retry = search_omdb(english_title)
                    if omdb_retry:
                        print(f"[OMDb] 方法二成功，标题={omdb_retry.get('Title')}, IMDb={omdb_retry.get('imdbRating')}")
                    else:
                        print(f"[OMDb] 方法二失败（未找到 '{english_title}'）")

                # 方法三：从豆瓣合并标题正则提取英文名
                if not omdb_retry:
                    combined = douban_full.get('title', '')
                    en_match = _re.search(r'[A-Za-z][A-Za-z0-9\s:\',!?&\-]{2,}', combined)
                    if en_match:
                        english_title = en_match.group(0).strip()
                        print(f"[OMDb] 方法三：从豆瓣标题提取英文名 '{english_title}'")
                        omdb_retry = search_omdb(english_title)
                        if omdb_retry:
                            print(f"[OMDb] 方法三成功，标题={omdb_retry.get('Title')}, IMDb={omdb_retry.get('imdbRating')}")
                        else:
                            print(f"[OMDb] 方法三失败，三种方法均无法获取 OMDb 数据")
                    else:
                        print(f"[OMDb] 方法三：豆瓣标题 '{combined}' 无英文名可提取")
            else:
                print(f"[OMDb] 豆瓣详情获取失败，无法进行 OMDb 查询")

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
                # 豆瓣图片需要经过代理才能在浏览器中正常显示
                final_poster = wrap_douban_poster(douban_poster)

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
            # 若通过 IMDb ID 获得了 omdb_retry 但 english_title 为空，
            # 则从 OMDb 返回数据中取 Title 字段作为英文名
            rt_english_title = english_title
            if not rt_english_title and omdb_retry:
                rt_english_title = omdb_retry.get('Title', '')
                if rt_english_title:
                    print(f"[RT] 使用 OMDb 返回的英文标题抓取 RT 评分: {rt_english_title}")
            if rt_english_title:
                rt_source = omdb_retry if omdb_retry else {}
                douban_year = douban_full.get('year', '') if douban_full else ''
                rt_data = get_rotten_tomatoes_scores(rt_source, rt_english_title,
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
    imdb_id_for_dist = omdb_data.get('imdbID', '')
    if omdb_data.get('imdbRating') and omdb_data.get('imdbRating') != 'N/A':
        imdb_entry = {
            'score': omdb_data.get('imdbRating'),
            'votes': parse_votes(omdb_data.get('imdbVotes', '0'))
        }
        # 附加 IMDb 评分分布
        if imdb_id_for_dist:
            try:
                imdb_scraper_obj = IMDbRatingScraper()
                imdb_dist = imdb_scraper_obj.get_rating_distribution(imdb_id_for_dist)
                if imdb_dist:
                    imdb_entry['rating_distribution'] = imdb_dist
                    print(f"[IMDb] 获取到评分分布，共 {len(imdb_dist)} 段")
            except Exception as e:
                print(f"[IMDb] 获取评分分布失败: {e}")
        movie_info['imdb'] = imdb_entry

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
                    # 豆瓣图片需要经过代理才能在浏览器中正常显示
                    movie_info['poster'] = wrap_douban_poster(douban_info['poster'])
                    print(f"[Poster] OMDb 无海报，使用豆瓣海报（搜索词：{cand}）")
                    break
        except Exception as e:
            print(f"[Poster] 获取豆瓣海报失败: {e}")

    return movie_info

# OMDb 专用 Session：禁用系统代理（避免本地 VPN/Clash 代理超时）
_omdb_session = requests.Session()
_omdb_session.trust_env = False  # 不读取 HTTP_PROXY / HTTPS_PROXY 等环境变量


def search_omdb_by_id(imdb_id: str):
    """通过 IMDb ID 直接查询 OMDb API，获取电影详情"""
    if not imdb_id:
        return None
    if not (OMDB_API_KEY and OMDB_API_KEY != 'your-api-key-here'):
        print(f"[OMDb] 无有效 API Key，跳过 IMDb ID 查询: {imdb_id}")
        return None
    try:
        print(f"[OMDb] 通过 IMDb ID 查询: {imdb_id}")
        params = {
            'apikey': OMDB_API_KEY,
            'i': imdb_id,
            'plot': 'full'
        }
        resp = _omdb_session.get(OMDB_BASE_URL, params=params, timeout=15)
        data = resp.json()
        if data.get('Response') == 'True':
            return data
        print(f"[OMDb] IMDb ID 查询无结果: {data.get('Error', '')}")
    except Exception as e:
        print(f"[OMDb] IMDb ID 查询出错: {e}")
    return None


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
            # 尝试使用真实API（使用专用 Session，禁用系统代理）
            search_params = {
                'apikey': OMDB_API_KEY,
                's': movie_name,
                'type': 'movie'
            }

            search_response = _omdb_session.get(OMDB_BASE_URL, params=search_params, timeout=15)
            search_data = search_response.json()

            if search_data.get('Response') == 'True' and search_data.get('Search'):
                # 获取第一个搜索结果的详细信息
                imdb_id = search_data['Search'][0]['imdbID']

                detail_params = {
                    'apikey': OMDB_API_KEY,
                    'i': imdb_id,
                    'plot': 'full'
                }

                detail_response = _omdb_session.get(OMDB_BASE_URL, params=detail_params, timeout=15)
                return detail_response.json()
            else:
                print(f"OMDb search no result: {search_data.get('Error', 'unknown')}")
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
    """获取豆瓣评分（分数、票数及评分分布）
    
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
            # 使用 search_movie 获取完整信息（含评分分布）
            movie_info = scraper.search_movie(name)
            if movie_info and movie_info.get('rating', 0) > 0:
                result = {
                    'score': str(movie_info['rating']),
                    'votes': movie_info.get('votes', 0)
                }
                # 附加评分分布（若有）
                dist = movie_info.get('rating_distribution', {})
                if dist:
                    result['rating_distribution'] = dist
                    print(f"[Douban] 获取到评分分布: {dist}")
                return result

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

def wrap_douban_poster(url: str) -> str:
    """
    若 URL 是豆瓣图片域名，则将其转为本地代理地址，
    避免浏览器因防盗链无法直接加载豆瓣图片。
    非豆瓣 URL 原样返回。
    """
    if not url:
        return url
    douban_hosts = ('img1.doubanio.com', 'img2.doubanio.com',
                    'img3.doubanio.com', 'img9.doubanio.com',
                    'img.doubanio.com')
    from urllib.parse import urlparse, urlencode
    parsed = urlparse(url)
    if any(parsed.netloc.endswith(h) for h in douban_hosts):
        return '/api/proxy-image?' + urlencode({'url': url})
    return url

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
    print("提示：建议使用 'python run.py' 启动，以便交互式输入 API Key。")
    print("直接运行 app.py 时，请确保已通过环境变量或 .env 文件配置好所有 API Key。")
    app.run(debug=True, host='0.0.0.0', port=5000)
