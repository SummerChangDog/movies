"""
豆瓣爬虫详细诊断脚本
逐步测试豆瓣评分获取的每个环节，帮助定位 douban=null 的根本原因
"""
import re
import json
import sys
import io
import requests
from douban_movie_scraper import DoubanMovieScraper

# 强制 UTF-8 输出，避免 Windows GBK 编码报错
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ------------------------------------------------------------------ #
# 1. 直接访问豆瓣搜索建议 API，看是否能得到结果
# ------------------------------------------------------------------ #
def test_api_search(movie_name):
    print(f"\n{'='*60}")
    print(f"[步骤1] 测试豆瓣搜索建议 API: {movie_name}")
    print('='*60)
    try:
        url = f"https://movie.douban.com/j/subject_suggest?q={requests.utils.quote(movie_name)}"
        print(f"  请求 URL: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://movie.douban.com/',
        }
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"  HTTP 状态码: {resp.status_code}")
        print(f"  响应 Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        print(f"  响应内容 (前500字符): {resp.text[:500]}")
        try:
            data = resp.json()
            print(f"  解析 JSON 成功，共 {len(data)} 条结果")
            for item in data[:3]:
                print(f"    - id={item.get('id')}, type={item.get('type')}, title={item.get('title')}, sub_title={item.get('sub_title')}")
            return data
        except Exception as e:
            print(f"  解析 JSON 失败: {e}")
    except Exception as e:
        print(f"  请求失败: {e}")
    return None


# ------------------------------------------------------------------ #
# 2. 直接访问豆瓣电影详情页，检查 HTML 结构
# ------------------------------------------------------------------ #
def test_detail_page(movie_id):
    print(f"\n{'='*60}")
    print(f"[步骤2] 测试豆瓣详情页 (ID={movie_id})")
    print('='*60)
    scraper = DoubanMovieScraper(delay_enable=False)
    url = f"https://movie.douban.com/subject/{movie_id}/"
    print(f"  请求 URL: {url}")
    content = scraper._fetch_page(url)
    if not content:
        print("  ❌ 页面获取失败，返回 None")
        return None
    print(f"  ✅ 页面获取成功，HTML 长度: {len(content)} 字符")

    # 检测是否被重定向到验证页面
    if 'accounts.douban.com' in content:
        print("  ⚠️  页面包含 accounts.douban.com，可能需要登录")
    if '该内容暂不支持访问' in content or '访问频率异常' in content:
        print("  ⚠️  页面包含访问受限提示")
    if 'cha' in content and 'tok' in content:
        print("  ⚠️  页面包含 PoW 挑战字段")

    # 检查各个关键元素
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')

    # 标题
    title_elem = soup.find('span', property='v:itemreviewed')
    print(f"\n  [标题元素] property='v:itemreviewed': {'找到 → ' + title_elem.get_text(strip=True) if title_elem else '❌ 未找到'}")

    # 评分 - 方法1
    rating_elem = soup.find('strong', class_='ll rating_num')
    print(f"  [评分元素] strong.ll.rating_num: {'找到 → ' + rating_elem.get_text(strip=True) if rating_elem else '❌ 未找到'}")

    # 评分 - 方法2：JSON-LD
    jld = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', content)
    print(f"  [评分JSON-LD] ratingValue: {'找到 → ' + jld.group(1) if jld else '❌ 未找到'}")

    # 评分 - 方法3：搜索所有可能包含评分的元素
    all_rating_candidates = soup.find_all('strong')
    print(f"  [所有<strong>元素] 共 {len(all_rating_candidates)} 个:")
    for el in all_rating_candidates[:10]:
        classes = el.get('class', [])
        text = el.get_text(strip=True)
        print(f"    class={classes}, text='{text[:50]}'")

    # 评价人数
    votes_elem = soup.find('span', property='v:votes')
    print(f"  [评价人数] property='v:votes': {'找到 → ' + votes_elem.get_text(strip=True) if votes_elem else '❌ 未找到'}")

    # 评分分布
    rating_per_elems = soup.find_all('span', class_='rating_per')
    print(f"  [评分分布] class='rating_per': 找到 {len(rating_per_elems)} 个元素")
    for el in rating_per_elems:
        print(f"    text='{el.get_text(strip=True)}'")

    # 保存 HTML 以供手动检查
    with open('debug_douban_page.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n  📄 页面 HTML 已保存到 debug_douban_page.html（可用浏览器打开查看）")

    return content


# ------------------------------------------------------------------ #
# 3. 使用完整爬虫流程测试
# ------------------------------------------------------------------ #
def test_full_scraper(movie_name):
    print(f"\n{'='*60}")
    print(f"[步骤3] 完整爬虫流程测试: {movie_name}")
    print('='*60)
    scraper = DoubanMovieScraper(delay_enable=False)

    # 3.1 获取 movie_id
    print("\n  [3.1] 获取 movie_id...")
    movie_id = scraper.get_movie_id(movie_name)
    print(f"  结果: {movie_id}")

    if not movie_id:
        print("  ❌ 无法获取 movie_id，流程终止")
        return

    # 3.2 获取详细信息
    print("\n  [3.2] 获取电影详情...")
    details = scraper.get_movie_details(movie_id)
    if not details:
        print("  ❌ 获取电影详情失败，返回 None")
        return

    print(f"  ✅ 获取详情成功")
    print(f"  title         = {details.get('title')}")
    print(f"  rating        = {details.get('rating')} (类型: {type(details.get('rating')).__name__})")
    print(f"  votes         = {details.get('votes')} (类型: {type(details.get('votes')).__name__})")
    print(f"  rating_distribution = {details.get('rating_distribution')}")
    print(f"  year          = {details.get('year')}")
    print(f"  genres        = {details.get('genres')}")

    # 3.3 检查 get_douban_rating 返回值
    print("\n  [3.3] 模拟 get_douban_rating 逻辑...")
    if details.get('rating', 0) > 0:
        result = {
            'score': str(details['rating']),
            'votes': details.get('votes', 0)
        }
        dist = details.get('rating_distribution', {})
        if dist:
            result['rating_distribution'] = dist
            print(f"  ✅ 豆瓣结果（含评分分布）: {json.dumps(result, ensure_ascii=False, indent=4)}")
        else:
            print(f"  ⚠️  豆瓣结果（无评分分布）: score={result['score']}, votes={result['votes']}")
    else:
        print(f"  ❌ 评分为 0 或不存在，get_douban_rating 将返回 None")
        print(f"     详情: rating={details.get('rating')}, 判断条件 rating > 0 = {details.get('rating', 0) > 0}")


# ------------------------------------------------------------------ #
# 主程序
# ------------------------------------------------------------------ #
if __name__ == '__main__':
    test_movie = sys.argv[1] if len(sys.argv) > 1 else '芭比'
    print(f"\n🎬 开始诊断豆瓣评分 (测试电影: {test_movie})")

    # 步骤1：测试 API 接口
    api_results = test_api_search(test_movie)

    # 如果 API 找到了电影，用其 ID 测试详情页
    movie_id = None
    if api_results:
        for item in api_results:
            if item.get('type') == 'movie':
                movie_id = item.get('id')
                break

    if movie_id:
        # 步骤2：测试详情页 HTML
        test_detail_page(movie_id)
    else:
        print(f"\n  ⚠️  API 未返回 movie_id，跳过步骤2")

    # 步骤3：完整爬虫流程
    test_full_scraper(test_movie)

    print(f"\n{'='*60}")
    print("诊断完成！")
    print("如果 debug_douban_page.html 已生成，请用浏览器打开检查页面结构")
    print("="*60)
