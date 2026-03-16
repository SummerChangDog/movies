# -*- coding: utf-8 -*-
"""测试完整浏览器指纹头 + 移动端主页策略"""
import re
import requests
from bs4 import BeautifulSoup

results = []
def log(msg): print(msg); results.append(str(msg))

# ---- 方案A: 完整Chrome浏览器指纹头 ----
log("=== PLAN-A: Full Chrome fingerprint headers ===")
try:
    full_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    s = requests.Session()
    r = s.get('https://movie.douban.com/', headers=full_headers, timeout=15)
    log(f"  homepage status: {r.status_code}, cookies: {list(s.cookies.keys())}")
    # 用主页获取的Cookie继续请求
    full_headers['Referer'] = 'https://movie.douban.com/'
    full_headers['Sec-Fetch-Site'] = 'same-origin'
    r2 = s.get('https://movie.douban.com/j/subject_suggest?q=%E8%8A%AD%E6%AF%94',
               headers={**full_headers, 'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'X-Requested-With': 'XMLHttpRequest'}, timeout=10)
    log(f"  suggest API status: {r2.status_code}")
    log(f"  suggest API response[:300]: {r2.text[:300]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 方案B: 移动端m.douban.com ----
log("\n=== PLAN-B: Mobile site m.douban.com ===")
try:
    mob_h = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    r3 = requests.get('https://m.douban.com/movie/subject/1292052/', headers=mob_h, timeout=15, allow_redirects=True)
    log(f"  mobile detail status: {r3.status_code}, length: {len(r3.text)}, url: {r3.url}")
    if r3.status_code == 200:
        jld = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', r3.text)
        log(f"  ratingValue: {jld.group(1) if jld else 'NOT FOUND'}")
        # 看看有什么评分相关内容
        rating_hits = re.findall(r'[0-9]\.[0-9]', r3.text[:5000])
        log(f"  x.x patterns in first 5000 chars: {rating_hits[:10]}")
    else:
        log(f"  response[:200]: {r3.text[:200]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 方案C: 豆瓣API v2 (不需要apikey的公开端点) ----
log("\n=== PLAN-C: Douban API v2 subject direct ===")
try:
    api_h = {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)'}
    # 旧版公开API（已知肖申克ID）
    r4 = requests.get('https://api.douban.com/v2/movie/subject/1292052', headers=api_h, timeout=10)
    log(f"  old API v2 status: {r4.status_code}")
    log(f"  response[:300]: {r4.text[:300]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 方案D: 通过Referer欺骗（伪装成从豆瓣内部跳转） ----
log("\n=== PLAN-D: Referer spoofing with full session ===")
try:
    s4 = requests.Session()
    headers_d = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://www.douban.com/',
    }
    # 手动设置bid cookie
    s4.cookies.set('bid', 'abc123xyz', domain='.douban.com')
    r5 = s4.get('https://movie.douban.com/subject/1292052/', headers=headers_d, timeout=15)
    log(f"  status: {r5.status_code}, length: {len(r5.text)}")
    if r5.status_code == 200:
        jld = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', r5.text)
        log(f"  ratingValue: {jld.group(1) if jld else 'NOT FOUND'}")
    else:
        log(f"  response[:200]: {r5.text[:200]}")
except Exception as e:
    log(f"  ERROR: {e}")

with open('debug_douban3_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
log("\nWritten to debug_douban3_result.txt")
