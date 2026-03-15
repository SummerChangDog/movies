"""
豆瓣电影数据爬虫
基于网页爬取，无需API密钥
使用 requests.Session 处理豆瓣 PoW（工作量证明）反爬挑战
"""
import re
import time
import random
import hashlib
import json
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

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
    """豆瓣电影爬虫（支持自动绕过 PoW 验证）"""

    def __init__(self, delay_enable=True):
        """
        初始化爬虫
        :param delay_enable: 是否启用随机延迟
        """
        self.delay_enable = delay_enable
        self._user_agent = random.choice(USER_AGENTS)
        # 使用 Session 维护 Cookie，使 PoW 验证状态持久化
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self._user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        })

    def random_delay(self):
        """随机延迟，避免请求过快"""
        if self.delay_enable:
            time.sleep(random.uniform(0.5, 2.0))

    # ------------------------------------------------------------------ #
    #  PoW 挑战处理
    # ------------------------------------------------------------------ #

    def _solve_pow(self, cha, difficulty=4):
        """
        求解豆瓣 SHA-512 工作量证明挑战：
        找到最小正整数 nonce，使 sha512(cha + str(nonce)) 的十六进制以 difficulty 个 '0' 开头
        """
        target = '0' * difficulty
        nonce = 0
        while True:
            nonce += 1
            h = hashlib.sha512((cha + str(nonce)).encode('utf-8')).hexdigest()
            if h.startswith(target):
                return nonce

    def _fetch_page(self, url):
        """
        获取豆瓣页面内容，自动处理 PoW 挑战（重定向到 sec.douban.com/c）
        :param url: 目标页面 URL
        :return: 页面 HTML 字符串，失败返回 None
        """
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()

            # 检测是否触发了 PoW 挑战
            if 'id="cha"' not in resp.text:
                return resp.text  # 无挑战，直接返回

            print(f"[DoubanScraper] 检测到 PoW 挑战，正在计算...")

            # 提取挑战参数
            tok_m = re.search(r'id="tok"[^>]*value="([^"]+)"', resp.text)
            cha_m = re.search(r'id="cha"[^>]*value="([^"]+)"', resp.text)
            red_m = re.search(r'id="red"[^>]*value="([^"]+)"', resp.text)

            if not (tok_m and cha_m):
                print(f"[DoubanScraper] 无法提取挑战参数")
                return None

            tok = tok_m.group(1)
            cha_val = cha_m.group(1)
            red = red_m.group(1) if red_m else url

            # 求解 PoW
            nonce = self._solve_pow(cha_val, difficulty=4)
            print(f"[DoubanScraper] PoW 求解完成，nonce={nonce}")

            # 从跳转后的实际 URL 构建 POST 端点
            # 豆瓣会将请求先重定向到 sec.douban.com/c，故 action 应取重定向后 URL 的 base
            base_url = resp.url.split('/')[0] + '//' + resp.url.split('/')[2]
            # 表单 action 为 /c，拼在 base_url 后
            action_url = base_url + '/c'
            print(f"[DoubanScraper] POST 到: {action_url}")

            post_resp = self.session.post(
                action_url,
                data={'tok': tok, 'cha': cha_val, 'sol': str(nonce), 'red': red},
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': base_url,
                    'Referer': resp.url,
                },
                timeout=15,
                allow_redirects=True,
            )
            print(f"[DoubanScraper] 挑战验证完成，状态={post_resp.status_code}，URL={post_resp.url}")
            return post_resp.text

        except requests.RequestException as e:
            print(f"[DoubanScraper] 页面请求失败: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  电影 ID 查找
    # ------------------------------------------------------------------ #

    def get_movie_id(self, movie_name):
        """通过电影名获取豆瓣电影ID（先 API，后搜索页）"""
        movie_id = self._get_movie_id_from_api(movie_name)
        if movie_id:
            return movie_id
        print(f"[DoubanScraper] API 失败，尝试搜索页")
        return self._get_movie_id_from_search_page(movie_name)

    def _get_movie_id_from_api(self, movie_name):
        """使用搜索建议 JSON API 获取电影ID"""
        try:
            url = f"{DOUBAN_MOVIE_SEARCH_URL}?q={requests.utils.quote(movie_name)}"
            print(f"[DoubanScraper] API URL: {url}")
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            print(f"[DoubanScraper] API response: {data}")
            for item in data:
                if item.get('type') == 'movie':
                    movie_id = item.get('id')
                    print(f"[DoubanScraper] Found movie ID from API: {movie_id}")
                    return movie_id
        except Exception as e:
            print(f"[DoubanScraper] API error: {e}")
        return None

    def _get_movie_id_from_search_page(self, movie_name):
        """从搜索结果页面提取电影ID"""
        try:
            url = f"{DOUBAN_MOVIE_SEARCH_PAGE_URL}?search_text={requests.utils.quote(movie_name)}&cat=1002"
            print(f"[DoubanScraper] Search page URL: {url}")
            self.random_delay()
            content = self._fetch_page(url)
            if content:
                matches = re.findall(r'https://movie\.douban\.com/subject/(\d+)/', content)
                if matches:
                    print(f"[DoubanScraper] Found movie ID from search page: {matches[0]}")
                    return matches[0]
            print(f"[DoubanScraper] No movie ID found in search page")
        except Exception as e:
            print(f"[DoubanScraper] Search page error: {e}")
        return None

    # ------------------------------------------------------------------ #
    #  电影详情抓取
    # ------------------------------------------------------------------ #

    def get_movie_details(self, movie_id):
        """
        获取电影详细信息（评分、标题、导演等）
        :param movie_id: 豆瓣电影ID
        :return: 电影信息字典，失败返回 None
        """
        try:
            self.random_delay()
            url = DOUBAN_MOVIE_DETAIL_URL.format(id=movie_id)
            content = self._fetch_page(url)
            if not content:
                return None

            soup = BeautifulSoup(content, 'html.parser')
            movie_info = {}

            # 标题
            title_elem = soup.find('span', property='v:itemreviewed')
            movie_info['title'] = title_elem.get_text(strip=True) if title_elem else ''

            # 评分
            rating_elem = soup.find('strong', class_='ll rating_num')
            rating_text = rating_elem.get_text(strip=True) if rating_elem else ''
            # 备用：从 JSON-LD 提取
            if not rating_text:
                jld = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', content)
                rating_text = jld.group(1) if jld else ''
            try:
                movie_info['rating'] = float(rating_text) if rating_text else 0
            except ValueError:
                movie_info['rating'] = 0

            # 评价人数
            votes_elem = soup.find('span', property='v:votes')
            votes_text = votes_elem.get_text(strip=True) if votes_elem else ''
            try:
                movie_info['votes'] = int(votes_text) if votes_text else 0
            except ValueError:
                movie_info['votes'] = 0

            # 年份
            year_elem = soup.find('span', class_='year')
            if year_elem:
                year_m = re.search(r'\d{4}', year_elem.get_text())
                movie_info['year'] = year_m.group() if year_m else ''

            # 导演
            movie_info['directors'] = [d.get_text(strip=True) for d in soup.find_all('a', rel='v:directedBy')]

            # 主演（前5）
            movie_info['casts'] = [c.get_text(strip=True) for c in soup.find_all('a', rel='v:starring')[:5]]

            # 类型
            movie_info['genres'] = [g.get_text(strip=True) for g in soup.find_all('span', property='v:genre')]

            # 制片国家
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

            # 简介
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
            print(f"[DoubanScraper] 获取电影详情时出错: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  对外接口
    # ------------------------------------------------------------------ #

    def search_movie(self, movie_name):
        """
        搜索电影并返回详情
        :param movie_name: 电影名称
        :return: 电影信息字典或 None
        """
        try:
            movie_id = self.get_movie_id(movie_name)
            if not movie_id:
                return None
            return self.get_movie_details(movie_id)
        except Exception as e:
            print(f"[DoubanScraper] 搜索电影时出错: {e}")
            return None

    def get_movie_rating_only(self, movie_name):
        """
        仅获取电影评分信息
        :param movie_name: 电影名称
        :return: {'score': 评分, 'votes': 评价人数}
        """
        print(f"[DoubanScraper] Starting search for: {movie_name}")
        movie_info = self.search_movie(movie_name)
        if movie_info:
            print(f"[DoubanScraper] Found movie info: {movie_info.get('title')} - Rating: {movie_info.get('rating')}")
            return {
                'score': movie_info.get('rating', 0),
                'votes': movie_info.get('votes', 0)
            }
        print(f"[DoubanScraper] No movie info found for: {movie_name}")
        return {'score': 0, 'votes': 0}


# ------------------------------------------------------------------ #
#  测试代码
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    scraper = DoubanMovieScraper()

    test_movies = ['肖申克的救赎', 'The Shawshank Redemption', '星际穿越']

    for movie in test_movies:
        print(f"\n{'='*50}\n搜索电影: {movie}")
        result = scraper.search_movie(movie)
        if result:
            print(f"标题: {result['title']}")
            print(f"评分: {result['rating']}")
            print(f"评价人数: {result['votes']}")
            print(f"年份: {result.get('year', 'N/A')}")
            print(f"导演: {', '.join(result.get('directors', []))}")
        else:
            print("未找到电影信息")
