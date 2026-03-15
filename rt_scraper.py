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

    def _name_similarity(self, a: str, b: str) -> float:
        """简单的字符串相似度：共同词数 / 总词数"""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        # 去掉冠词
        stop = {'the', 'a', 'an'}
        a_words -= stop
        b_words -= stop
        if not a_words or not b_words:
            return 0.0
        common = a_words & b_words
        return len(common) / max(len(a_words), len(b_words))

    def _search_movie_path(self, movie_name: str) -> str | None:
        """
        通过 RT 搜索 API 找到电影页面路径（如 /m/the_shining）
        优先从 JSON 结构中找标题匹配度最高的结果
        """
        try:
            url = f"{RT_SEARCH_URL}?search={quote(movie_name)}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            text = resp.text

            # 方法1：从 application/json script 中找带名称匹配的电影路径
            json_matches = re.findall(
                r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            best_path = None
            best_score = 0.0
            for raw in json_matches:
                try:
                    data = json.loads(raw)
                    candidates = self._collect_movie_candidates(data)
                    for path, name in candidates:
                        sim = self._name_similarity(movie_name, name)
                        if sim > best_score:
                            best_score = sim
                            best_path = path
                except Exception:
                    continue
            if best_path and best_score >= 0.5:
                print(f"[RTScraper] JSON搜索匹配: {best_path} (相似度={best_score:.2f})")
                return best_path

            # 方法2：从页面 href 中找 /m/xxx 链接，并尽量匹配名称
            # 先提取 anchor 标签的完整 href + text 组合
            anchors = re.findall(r'href="(/m/[a-z0-9_]+(?:/[a-z0-9_]+)*)"[^>]*>([^<]{0,80})', text)
            best_path = None
            best_score = 0.0
            for path, anchor_text in anchors:
                sim = self._name_similarity(movie_name, anchor_text)
                if sim > best_score:
                    best_score = sim
                    best_path = path
            if best_path and best_score >= 0.4:
                print(f"[RTScraper] href 匹配: {best_path} (相似度={best_score:.2f})")
                return best_path

            # 方法3：退化——取第一个 /m/ 链接（可能不准）
            fallback = re.findall(r'href="(/m/[a-z0-9_]+)"', text)
            if fallback:
                print(f"[RTScraper] href 退化选取: {fallback[0]}")
                return fallback[0]

        except Exception as e:
            print(f"[RTScraper] 搜索失败: {e}")
        return None

    def _collect_movie_candidates(self, data, depth=0) -> list:
        """从 JSON 结构中收集 (path, name) 候选对"""
        results = []
        if depth > 8:
            return results
        if isinstance(data, dict):
            url = data.get("url", "") or data.get("vanity", "")
            name = data.get("name", "") or data.get("title", "")
            if isinstance(url, str) and url.startswith("/m/") and isinstance(name, str) and name:
                results.append((url, name))
            for v in data.values():
                results.extend(self._collect_movie_candidates(v, depth + 1))
        elif isinstance(data, list):
            for item in data:
                results.extend(self._collect_movie_candidates(item, depth + 1))
        return results

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

    def _make_slug(self, text: str) -> str:
        """将电影名转为 RT URL slug"""
        s = text.lower()
        s = s.replace(":", "").replace("'", "").replace("-", "_").replace(" ", "_")
        s = re.sub(r"[^a-z0-9_]", "", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s

    def get_movie_scores(self, movie_name: str, year: str = None, imdb_id: str = None) -> dict | None:
        """
        获取烂番茄专业评分和观众评分
        :param movie_name: 英文电影名
        :param year: 上映年份（可选，用于区分同名电影）
        :param imdb_id: IMDb ID（可选，暂未使用）
        :return: {'critic': '87', 'audience': '91'} 或 None
        """
        print(f"[RTScraper] 开始查询: {movie_name}")

        slug = self._make_slug(movie_name)

        # 去掉开头冠词 the_/a_/an_
        slug_no_article = re.sub(r'^(the|a|an)_', '', slug)

        # 构建候选 slug 列表（按优先级）
        slug_candidates = [slug]
        if slug_no_article != slug:
            slug_candidates.append(slug_no_article)
        if year:
            slug_candidates.append(f"{slug}_{year}")
            if slug_no_article != slug:
                slug_candidates.append(f"{slug_no_article}_{year}")

        # 逐个尝试直接 URL
        for s in slug_candidates:
            scores = self._fetch_scores_from_page(f"/m/{s}")
            if scores:
                return scores

        # 所有直接 URL 失败，通过搜索找路径
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
