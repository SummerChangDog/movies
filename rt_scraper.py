"""
烂番茄（Rotten Tomatoes）评分爬虫
从 RT 网站直接抓取专业评分（Tomatometer）和观众评分（Audience Score）
"""
import re
import json
import random
import requests
from urllib.parse import quote

RT_BASE_URL = "https://www.rottentomatoes.com"
RT_SEARCH_URL = "https://www.rottentomatoes.com/search"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class RTScraper:
    """烂番茄评分爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    # ------------------------------------------------------------------ #
    #  搜索电影，获取 RT 页面路径
    # ------------------------------------------------------------------ #

    def _search_movie_path(self, movie_name: str) -> str | None:
        """
        通过 RT 搜索 API 找到电影页面路径（如 /m/inception）
        :param movie_name: 英文电影名
        :return: 电影页面相对路径，或 None
        """
        try:
            # RT 的搜索接口返回 JSON，包含电影列表
            url = f"{RT_SEARCH_URL}?search={quote(movie_name)}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()

            # RT 将搜索结果嵌在 JSON-LD 或 script 标签里
            # 尝试从页面 script 标签中提取结构化数据
            text = resp.text

            # 方法1：查找 search-results JSON 数据
            # RT 搜索页面中有 <script type="application/json"> 包含结果
            json_matches = re.findall(
                r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            for raw in json_matches:
                try:
                    data = json.loads(raw)
                    # 递归查找包含 movie url 的条目
                    path = self._extract_movie_path_from_json(data, movie_name)
                    if path:
                        return path
                except Exception:
                    continue

            # 方法2：直接从 href 提取 /m/movie_slug 格式链接
            movie_links = re.findall(r'href="(/m/[a-z0-9_]+)"', text)
            if movie_links:
                print(f"[RTScraper] 从搜索页找到路径: {movie_links[0]}")
                return movie_links[0]

        except Exception as e:
            print(f"[RTScraper] 搜索失败: {e}")
        return None

    def _extract_movie_path_from_json(self, data, movie_name: str) -> str | None:
        """递归从 JSON 结构中查找电影页面路径"""
        if isinstance(data, dict):
            # 查找包含 /m/ 路径的 url 字段
            url = data.get("url", "") or data.get("vanity", "")
            if isinstance(url, str) and url.startswith("/m/"):
                name = data.get("name", "") or data.get("title", "")
                if isinstance(name, str):
                    return url
            for v in data.values():
                result = self._extract_movie_path_from_json(v, movie_name)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._extract_movie_path_from_json(item, movie_name)
                if result:
                    return result
        return None

    # ------------------------------------------------------------------ #
    #  从电影页面提取评分
    # ------------------------------------------------------------------ #

    def _fetch_scores_from_page(self, path: str) -> dict | None:
        """
        访问 RT 电影页面，提取专业评分和观众评分
        :param path: 页面路径，如 /m/inception
        :return: {'critic': '87', 'audience': '91'} 或 None
        """
        try:
            url = RT_BASE_URL + path
            print(f"[RTScraper] 访问页面: {url}")
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            text = resp.text

            # 检查是否被重定向到404或错误页
            if '<title>Error' in text or 'Page Not Found' in text:
                return None

            scores = {}

            # ---- 方法1（最可靠）：data-json="reviewsData" script 标签 ----
            # 格式: {"audienceScore":{"score":"91",...},"criticsScore":{"score":"87",...}}
            reviews_data_m = re.search(
                r'<script[^>]+data-json="reviewsData"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            if reviews_data_m:
                try:
                    data = json.loads(reviews_data_m.group(1))
                    critic_info = data.get("criticsScore", {})
                    audience_info = data.get("audienceScore", {})
                    if critic_info.get("score"):
                        scores["critic"] = critic_info["score"]
                    if audience_info.get("score"):
                        scores["audience"] = audience_info["score"]
                    print(f"[RTScraper] 从 reviewsData 提取: {scores}")
                    if scores:
                        return scores
                except Exception as e:
                    print(f"[RTScraper] reviewsData 解析失败: {e}")

            # ---- 方法2：页面内嵌 JSON 大块（含 audienceScore/criticsScore） ----
            json_scripts = re.findall(
                r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            for raw in json_scripts:
                if '"audienceScore"' not in raw and '"criticsScore"' not in raw:
                    continue
                try:
                    data = json.loads(raw)
                    critic_info = data.get("criticsScore", {})
                    audience_info = data.get("audienceScore", {})
                    if isinstance(audience_info, dict) and audience_info.get("score"):
                        scores["audience"] = str(audience_info["score"])
                    if isinstance(critic_info, dict) and critic_info.get("score"):
                        scores["critic"] = str(critic_info["score"])
                    if scores:
                        print(f"[RTScraper] 从内嵌 JSON 提取: {scores}")
                        return scores
                except Exception:
                    continue

            # ---- 方法3：JSON-LD aggregateRating（仅专业分）----
            jsonld_blocks = re.findall(
                r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            for raw in jsonld_blocks:
                try:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        agg = data.get("aggregateRating", {})
                        if agg and agg.get("ratingValue"):
                            scores["critic"] = str(int(float(agg["ratingValue"])))
                except Exception:
                    continue

            if scores:
                print(f"[RTScraper] 评分提取结果: {scores}")
                return scores

        except Exception as e:
            print(f"[RTScraper] 页面抓取失败: {e}")
        return None

    # ------------------------------------------------------------------ #
    #  对外接口
    # ------------------------------------------------------------------ #

    def get_movie_scores(self, movie_name: str, imdb_id: str = None) -> dict | None:
        """
        获取烂番茄专业评分和观众评分
        :param movie_name: 英文电影名
        :param imdb_id: IMDb ID（可选，暂未使用）
        :return: {'critic': '87', 'audience': '91'} 或 None
        """
        print(f"[RTScraper] 开始查询: {movie_name}")

        # 将电影名转为 RT URL slug（小写，空格变下划线）
        slug = movie_name.lower().replace(" ", "_").replace(":", "").replace("'", "").replace("-", "_")
        slug = re.sub(r"[^a-z0-9_]", "", slug)

        # 先尝试直接构造 URL
        direct_path = f"/m/{slug}"
        scores = self._fetch_scores_from_page(direct_path)
        if scores:
            return scores

        # 直接 URL 失败，通过搜索找路径
        path = self._search_movie_path(movie_name)
        if path:
            scores = self._fetch_scores_from_page(path)
            if scores:
                return scores

        print(f"[RTScraper] 未能获取 {movie_name} 的评分")
        return None


# ------------------------------------------------------------------ #
#  测试代码
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    scraper = RTScraper()
    test_movies = ["Inception", "The Shawshank Redemption", "Interstellar"]
    for movie in test_movies:
        print(f"\n{'='*50}\n{movie}")
        result = scraper.get_movie_scores(movie)
        print(f"结果: {result}")
