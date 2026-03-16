"""
IMDb 评分分布爬虫
从 IMDb 电影页面爬取各星级（1-10星）的投票数量和百分比
"""
import re
import json
import random
import requests

IMDB_BASE_URL = "https://www.imdb.com"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class IMDbRatingScraper:
    """IMDb 评分分布爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        })

    # ------------------------------------------------------------------ #
    #  递归搜索 JSON 中的直方图数据
    # ------------------------------------------------------------------ #

    def _find_histogram(self, data, depth=0):
        """
        递归在 JSON 结构中查找 IMDb 评分直方图数据。
        直方图数据通常存储为 histogramValues 或 ratingHistogram 字段，
        包含一个列表，每项有 rating 和 voteCount（或 votes）字段。
        """
        if depth > 10:
            return None
        if isinstance(data, dict):
            # 检查是否包含直方图关键字段
            for key in ('histogramValues', 'ratingHistogram', 'ratingDistribution'):
                if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                    first = data[key][0]
                    if isinstance(first, dict) and ('rating' in first or 'ratingValue' in first):
                        return data[key]
            # 递归搜索所有值
            for v in data.values():
                result = self._find_histogram(v, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_histogram(item, depth + 1)
                if result:
                    return result
        return None

    # ------------------------------------------------------------------ #
    #  方法0：IMDb GraphQL API（最可靠）
    # ------------------------------------------------------------------ #

    def _fetch_from_graphql(self, imdb_id: str) -> dict:
        """
        使用 IMDb GraphQL API 获取评分直方图。
        正确路径：aggregateRatingsBreakdown -> histogram -> histogramValues { rating, voteCount }
        """
        try:
            url = "https://api.graphql.imdb.com/"
            query = """
            query {
              title(id: "%s") {
                aggregateRatingsBreakdown {
                  histogram {
                    histogramValues {
                      rating
                      voteCount
                    }
                  }
                }
              }
            }
            """ % imdb_id
            payload = {"query": query}
            headers = {
                "Content-Type": "application/json",
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/graphql+json, application/json",
                "x-imdb-client-name": "imdb-web-next-amsterdam",
                "x-imdb-user-country": "US",
                "x-imdb-user-language": "en-US",
                "Origin": "https://www.imdb.com",
                "Referer": f"https://www.imdb.com/title/{imdb_id}/ratings/",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # 解析 GraphQL 响应
            histogram_values = (
                data.get("data", {})
                    .get("title", {})
                    .get("aggregateRatingsBreakdown", {})
                    .get("histogram", {})
                    .get("histogramValues", [])
            )
            if histogram_values:
                print(f"[IMDbScraper] GraphQL 获取到 {len(histogram_values)} 条直方图数据")
                return self._parse_histogram(histogram_values)
            else:
                print(f"[IMDbScraper] GraphQL 返回空直方图: {str(data)[:200]}")
        except Exception as e:
            print(f"[IMDbScraper] GraphQL 请求失败: {e}")
        return {}

    # ------------------------------------------------------------------ #
    #  从 IMDb 页面获取评分分布
    # ------------------------------------------------------------------ #

    def get_rating_distribution(self, imdb_id: str) -> dict:
        """
        获取 IMDb 某部电影的评分分布（1-10星各占比例和票数）。

        :param imdb_id: IMDb 电影 ID（如 'tt1375666'）
        :return: {
            '10': {'votes': 123456, 'percent': 35.2},
            '9':  {'votes': 98765,  'percent': 28.0},
            ...
            '1':  {'votes': 1234,   'percent': 0.35}
        }  若无法获取则返回空字典。
        """
        if not imdb_id:
            return {}

        # 方法0（最可靠）：IMDb 官方 GraphQL API
        result = self._fetch_from_graphql(imdb_id)
        if result:
            return result

        # 方法1：主电影页面（含 __NEXT_DATA__ JSON）
        result = self._fetch_from_title_page(imdb_id)
        if result:
            return result

        # 方法2：独立评分页面 /title/{id}/ratings/
        result = self._fetch_from_ratings_page(imdb_id)
        if result:
            return result

        print(f"[IMDbScraper] 无法获取 {imdb_id} 的评分分布")
        return {}

    def _fetch_from_title_page(self, imdb_id: str) -> dict:
        """从 IMDb 主页 __NEXT_DATA__ JSON 提取评分直方图"""
        try:
            url = f"{IMDB_BASE_URL}/title/{imdb_id}/"
            print(f"[IMDbScraper] 请求主页: {url}")
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            text = resp.text

            # 提取 __NEXT_DATA__ JSON 块
            next_data_m = re.search(
                r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            if next_data_m:
                try:
                    data = json.loads(next_data_m.group(1))
                    histogram = self._find_histogram(data)
                    if histogram:
                        print(f"[IMDbScraper] 从 __NEXT_DATA__ 找到直方图，共 {len(histogram)} 条")
                        return self._parse_histogram(histogram)
                except Exception as e:
                    print(f"[IMDbScraper] __NEXT_DATA__ 解析失败: {e}")

            # 尝试其他内嵌 JSON
            json_blocks = re.findall(
                r'<script[^>]+type="application/(?:json|ld\+json)"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            for raw in json_blocks:
                if 'histogram' not in raw.lower() and 'ratingDistribution' not in raw:
                    continue
                try:
                    data = json.loads(raw)
                    histogram = self._find_histogram(data)
                    if histogram:
                        print(f"[IMDbScraper] 从内嵌 JSON 找到直方图")
                        return self._parse_histogram(histogram)
                except Exception:
                    continue

        except Exception as e:
            print(f"[IMDbScraper] 主页请求失败: {e}")
        return {}

    def _fetch_from_ratings_page(self, imdb_id: str) -> dict:
        """从 IMDb /ratings/ 子页面爬取评分直方图"""
        try:
            url = f"{IMDB_BASE_URL}/title/{imdb_id}/ratings/"
            print(f"[IMDbScraper] 请求评分页: {url}")
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            text = resp.text

            # 尝试 __NEXT_DATA__
            next_data_m = re.search(
                r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            if next_data_m:
                try:
                    data = json.loads(next_data_m.group(1))
                    histogram = self._find_histogram(data)
                    if histogram:
                        print(f"[IMDbScraper] 从评分页 __NEXT_DATA__ 找到直方图")
                        return self._parse_histogram(histogram)
                except Exception as e:
                    print(f"[IMDbScraper] 评分页解析失败: {e}")

            # 旧版评分页面：HTML 表格行 pattern
            # 格式: <div class="leftAligned">10</div> ... <div class="leftAligned">xxx,xxx</div>
            rows = re.findall(
                r'<td[^>]*>\s*<div[^>]+class="[^"]*leftAligned[^"]*"[^>]*>\s*(\d+)\s*</div>\s*</td>'
                r'.*?'
                r'<td[^>]*>\s*<div[^>]+class="[^"]*leftAligned[^"]*"[^>]*>\s*([\d,]+)\s*</div>',
                text, re.DOTALL
            )
            if rows:
                total_votes = sum(int(v.replace(',', '')) for _, v in rows)
                if total_votes > 0:
                    distribution = {}
                    for star, votes_str in rows:
                        votes = int(votes_str.replace(',', ''))
                        pct = round(votes / total_votes * 100, 1)
                        distribution[star] = {'votes': votes, 'percent': pct}
                    print(f"[IMDbScraper] 从旧版 HTML 表格提取到 {len(distribution)} 个评分段")
                    return distribution

        except Exception as e:
            print(f"[IMDbScraper] 评分页请求失败: {e}")
        return {}

    def _parse_histogram(self, histogram: list) -> dict:
        """
        将 IMDb 直方图列表解析为统一的 dict 格式：
        { '10': {'votes': N, 'percent': P}, ..., '1': {'votes': N, 'percent': P} }

        支持多种字段命名：
        - {'rating': 10, 'voteCount': 1234}
        - {'ratingValue': 10, 'votes': 1234}
        - {'rating': 10, 'count': 1234}
        """
        distribution = {}
        total_votes = 0

        parsed_items = []
        for item in histogram:
            star = item.get('rating') or item.get('ratingValue')
            votes = item.get('voteCount') or item.get('votes') or item.get('count', 0)
            if star is not None and votes is not None:
                try:
                    star_int = int(star)
                    votes_int = int(votes)
                    parsed_items.append((star_int, votes_int))
                    total_votes += votes_int
                except (ValueError, TypeError):
                    continue

        if total_votes == 0:
            return {}

        for star_int, votes_int in parsed_items:
            pct = round(votes_int / total_votes * 100, 1)
            distribution[str(star_int)] = {
                'votes': votes_int,
                'percent': pct
            }

        # 确保覆盖 1-10 所有星级（缺失的填 0）
        for i in range(1, 11):
            distribution.setdefault(str(i), {'votes': 0, 'percent': 0.0})

        print(f"[IMDbScraper] 解析完成，总票数={total_votes}，分布={list(distribution.keys())}")
        return distribution


# ------------------------------------------------------------------ #
#  测试代码
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    scraper = IMDbRatingScraper()
    test_ids = [
        ("肖申克的救赎", "tt0111161"),
        ("盗梦空间", "tt1375666"),
        ("星际穿越", "tt0816692"),
    ]
    for name, imdb_id in test_ids:
        print(f"\n{'='*50}\n{name} ({imdb_id})")
        dist = scraper.get_rating_distribution(imdb_id)
        if dist:
            for star in sorted(dist.keys(), key=lambda x: int(x), reverse=True):
                info = dist[star]
                bar = '█' * int(info['percent'] / 2)
                print(f"  {star:>2}星: {info['percent']:5.1f}%  {bar}")
        else:
            print("  未获取到分布数据")
