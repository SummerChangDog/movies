"""
豆瓣电影数据爬虫
基于网页爬取，无需API密钥
"""
import re
import time
import random
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from bs4 import BeautifulSoup
import gzip

# 豆瓣电影相关URL
DOUBAN_MOVIE_SEARCH_URL = "https://movie.douban.com/j/subject_suggest"
DOUBAN_MOVIE_SEARCH_PAGE_URL = "https://search.douban.com/movie/subject_search"
DOUBAN_MOVIE_BASE_URL = "https://movie.douban.com"
DOUBAN_MOVIE_DETAIL_URL = "https://movie.douban.com/subject/{id}/"

# User-Agent列表，用于随机选择
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
]


class DoubanMovieScraper:
    """豆瓣电影爬虫"""
    
    def __init__(self, delay_enable=True):
        """
        初始化爬虫
        :param delay_enable: 是否启用随机延迟
        """
        self.delay_enable = delay_enable
    
    def get_headers(self):
        """获取请求头"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': DOUBAN_MOVIE_BASE_URL
        }
    
    def random_delay(self):
        """随机延迟，避免请求过快"""
        if self.delay_enable:
            delay = random.uniform(0.5, 2.0)
            time.sleep(delay)
    
    def get_response_content(self, response):
        """获取响应内容，处理gzip压缩"""
        encoding = response.info().get('Content-Encoding')
        if encoding == 'gzip':
            content = gzip.decompress(response.read())
        else:
            content = response.read()
        return content.decode('utf-8', errors='ignore')
    
    def search_movie(self, movie_name):
        """
        搜索电影并返回第一个结果的详情
        :param movie_name: 电影名称
        :return: 电影信息字典或None
        """
        try:
            # 使用豆瓣的搜索建议API获取电影ID
            movie_id = self.get_movie_id(movie_name)
            if not movie_id:
                return None
            
            # 获取电影详情
            return self.get_movie_details(movie_id)
            
        except Exception as e:
            print(f"搜索电影时出错: {e}")
            return None
    
    def get_movie_id(self, movie_name):
        """
        通过电影名获取豆瓣电影ID
        先尝试搜索建议API，失败则使用搜索页面
        """
        # 首先尝试搜索建议API
        movie_id = self._get_movie_id_from_api(movie_name)
        if movie_id:
            return movie_id
        
        # 如果API失败，尝试搜索页面
        print(f"[DoubanScraper] API search failed, trying search page")
        return self._get_movie_id_from_search_page(movie_name)
    
    def _get_movie_id_from_api(self, movie_name):
        """使用搜索建议API获取电影ID"""
        try:
            # 构建搜索URL
            params = {'q': movie_name}
            url = f"{DOUBAN_MOVIE_SEARCH_URL}?{urlencode(params)}"
            print(f"[DoubanScraper] API URL: {url}")
            
            # 发送请求
            req = Request(url, headers=self.get_headers())
            response = urlopen(req, timeout=10)
            content = self.get_response_content(response)
            
            # 解析JSON响应
            import json
            data = json.loads(content)
            print(f"[DoubanScraper] API response: {data[:200] if data else 'Empty'}")
            
            # 获取第一个电影结果
            if data and len(data) > 0:
                for item in data:
                    if item.get('type') == 'movie':
                        movie_id = item.get('id')
                        print(f"[DoubanScraper] Found movie ID from API: {movie_id}")
                        return movie_id
            
            return None
            
        except Exception as e:
            print(f"[DoubanScraper] API error: {e}")
            return None
    
    def _get_movie_id_from_search_page(self, movie_name):
        """从搜索页面获取电影ID"""
        try:
            # 构建搜索页面URL
            params = {
                'search_text': movie_name,
                'cat': 1002
            }
            url = f"{DOUBAN_MOVIE_SEARCH_PAGE_URL}?{urlencode(params)}"
            print(f"[DoubanScraper] Search page URL: {url}")
            
            # 添加延迟
            self.random_delay()
            
            # 发送请求
            req = Request(url, headers=self.get_headers())
            response = urlopen(req, timeout=10)
            content = self.get_response_content(response)
            
            # 使用正则表达式提取电影ID
            # 豆瓣电影页面链接格式: https://movie.douban.com/subject/12345/
            pattern = r'https://movie\.douban\.com/subject/(\d+)/'
            matches = re.findall(pattern, content)
            
            if matches:
                movie_id = matches[0]
                print(f"[DoubanScraper] Found movie ID from search page: {movie_id}")
                return movie_id
            
            print(f"[DoubanScraper] No movie ID found in search page")
            return None
            
        except Exception as e:
            print(f"[DoubanScraper] Search page error: {e}")
            return None
    
    def get_movie_details(self, movie_id):
        """
        获取电影详细信息
        :param movie_id: 豆瓣电影ID
        :return: 电影信息字典
        """
        try:
            # 添加随机延迟
            self.random_delay()
            
            # 构建详情页URL
            url = DOUBAN_MOVIE_DETAIL_URL.format(id=movie_id)
            
            # 发送请求
            req = Request(url, headers=self.get_headers())
            response = urlopen(req, timeout=10)
            content = self.get_response_content(response)
            
            # 解析HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # 提取电影信息
            movie_info = {}
            
            # 标题
            title_elem = soup.find('span', property='v:itemreviewed')
            movie_info['title'] = title_elem.get_text(strip=True) if title_elem else ''
            
            # 评分
            rating_elem = soup.find('strong', class_='ll rating_num')
            movie_info['rating'] = float(rating_elem.get_text(strip=True)) if rating_elem else 0
            
            # 评价人数
            votes_elem = soup.find('span', property='v:votes')
            movie_info['votes'] = int(votes_elem.get_text(strip=True)) if votes_elem else 0
            
            # 年份
            year_elem = soup.find('span', class_='year')
            if year_elem:
                year_text = year_elem.get_text(strip=True)
                year_match = re.search(r'\d{4}', year_text)
                movie_info['year'] = year_match.group() if year_match else ''
            
            # 导演
            directors = soup.find_all('a', rel='v:directedBy')
            movie_info['directors'] = [d.get_text(strip=True) for d in directors]
            
            # 主演
            casts = soup.find_all('a', rel='v:starring')
            movie_info['casts'] = [c.get_text(strip=True) for c in casts[:5]]  # 只取前5个
            
            # 类型
            genres = soup.find_all('span', property='v:genre')
            movie_info['genres'] = [g.get_text(strip=True) for g in genres]
            
            # 制片国家/地区
            info_span = soup.find('span', text=re.compile('制片国家/地区'))
            if info_span and info_span.next_sibling:
                movie_info['countries'] = info_span.next_sibling.strip()
            
            # 语言
            lang_span = soup.find('span', text=re.compile('语言'))
            if lang_span and lang_span.next_sibling:
                movie_info['languages'] = lang_span.next_sibling.strip()
            
            # 片长
            runtime_elem = soup.find('span', property='v:runtime')
            movie_info['runtime'] = runtime_elem.get_text(strip=True) if runtime_elem else ''
            
            # 剧情简介
            summary_elem = soup.find('span', property='v:summary')
            movie_info['summary'] = summary_elem.get_text(strip=True) if summary_elem else ''
            
            # 海报
            poster_elem = soup.find('img', rel='v:image')
            movie_info['poster'] = poster_elem.get('src') if poster_elem else ''
            
            # 豆瓣链接
            movie_info['douban_url'] = url
            movie_info['douban_id'] = movie_id
            
            return movie_info
            
        except Exception as e:
            print(f"获取电影详情时出错: {e}")
            return None
    
    def get_movie_rating_only(self, movie_name):
        """
        仅获取电影评分信息（简化版）
        :param movie_name: 电影名称
        :return: {'score': 评分, 'votes': 评价人数} 或 None
        """
        print(f"[DoubanScraper] Starting search for: {movie_name}")
        movie_info = self.search_movie(movie_name)
        
        if movie_info:
            print(f"[DoubanScraper] Found movie info: {movie_info.get('title')} - Rating: {movie_info.get('rating')}")
            return {
                'score': movie_info.get('rating', 0),
                'votes': movie_info.get('votes', 0)
            }
        else:
            print(f"[DoubanScraper] No movie info found for: {movie_name}")
            return {'score': 0, 'votes': 0}


# 测试代码
if __name__ == "__main__":
    scraper = DoubanMovieScraper()
    
    # 测试搜索功能
    test_movies = ['肖申克的救赎', 'The Shawshank Redemption', '星际穿越']
    
    for movie in test_movies:
        print(f"\n搜索电影: {movie}")
        result = scraper.search_movie(movie)
        if result:
            print(f"标题: {result['title']}")
            print(f"评分: {result['rating']}")
            print(f"评价人数: {result['votes']}")
            print(f"年份: {result.get('year', 'N/A')}")
            print(f"导演: {', '.join(result.get('directors', []))}")
        else:
            print("未找到电影信息")