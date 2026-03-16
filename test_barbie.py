"""测试芭比电影的 IMDb 和 RT 评分分布"""
from rt_scraper import RTScraper
from imdb_scraper import IMDbRatingScraper

print('=== 测试 IMDb 芭比评分分布 ===')
imdb = IMDbRatingScraper()
dist = imdb.get_rating_distribution('tt1517268')
if dist:
    for k in sorted(dist.keys(), key=lambda x: int(x), reverse=True):
        v = dist[k]
        bar = '#' * int(v['percent'] / 2)
        print(f'  {k:>2}star  {v["percent"]:5.1f}%  {bar}')
else:
    print('  未获取到 IMDb 分布')

print()
print('=== 测试 RT 芭比评分分布 ===')
rt = RTScraper()
scores = rt.get_movie_scores('Barbie', year='2023')
if scores:
    print(f'  critic: {scores.get("critic")}%')
    print(f'  audience: {scores.get("audience")}%')
    rdist = scores.get('rating_distribution', {})
    if rdist:
        print('  分布:')
        if rdist.get('critics'):
            print(f'    专业: 新鲜={rdist["critics"]["fresh"]}%, 腐烂={rdist["critics"]["rotten"]}%')
        if rdist.get('audience'):
            print(f'    观众: 喜欢={rdist["audience"]["liked"]}%, 不喜欢={rdist["audience"]["disliked"]}%')
    else:
        print('  未获取到 RT 分布')
else:
    print('  未获取到 RT 评分')
