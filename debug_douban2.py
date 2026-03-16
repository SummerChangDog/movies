# -*- coding: utf-8 -*-
"""测试各种豆瓣访问策略"""
import re
import sys
import requests
from bs4 import BeautifulSoup

HEADERS_BASE = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

results = []

def log(msg):
    print(msg)
    results.append(msg)

# ---- 测试1: Session预热后访问API ----
log("=== TEST1: Session warmup then search API ===")
try:
    s = requests.Session()
    s.headers.update(HEADERS_BASE)
    r = s.get('https://movie.douban.com/', timeout=15)
    log(f"  homepage: {r.status_code}, cookies: {list(s.cookies.keys())}")
    r2 = s.get('https://movie.douban.com/j/subject_suggest?q=%E8%8A%AD%E6%AF%94', timeout=10)
    log(f"  suggest API: {r2.status_code}")
    log(f"  response[:200]: {r2.text[:200]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 测试2: Frodo移动端API ----
log("\n=== TEST2: Frodo mobile API ===")
try:
    frodo_h = {
        'User-Agent': 'api-client/1 com.douban.frodo/7.18.0(1127) Android/29 product/shamu vendor/OPPO model/OPPO  rom/android  network/wifi  platform/mobile',
        'Accept': 'application/json',
    }
    r3 = requests.get(
        'https://frodo.douban.com/api/v2/search/movie?q=%E8%8A%AD%E6%AF%94&count=3',
        headers=frodo_h, timeout=10
    )
    log(f"  status: {r3.status_code}")
    log(f"  response[:300]: {r3.text[:300]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 测试3: 直接详情页（肖申克ID=1292052）Session预热后 ----
log("\n=== TEST3: Direct detail page with warmed session ===")
try:
    s2 = requests.Session()
    s2.headers.update(HEADERS_BASE)
    s2.get('https://movie.douban.com/', timeout=15)
    r4 = s2.get('https://movie.douban.com/subject/1292052/', timeout=15)
    log(f"  status: {r4.status_code}, length: {len(r4.text)}")
    if r4.status_code == 200:
        jld = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', r4.text)
        votes_m = re.search(r'"ratingCount"\s*:\s*"?(\d+)"?', r4.text)
        log(f"  ratingValue(JSON-LD): {jld.group(1) if jld else 'NOT FOUND'}")
        log(f"  ratingCount(JSON-LD): {votes_m.group(1) if votes_m else 'NOT FOUND'}")
        soup = BeautifulSoup(r4.text, 'html.parser')
        el = soup.find('strong', class_='ll rating_num')
        log(f"  strong.ll.rating_num: {el.get_text(strip=True) if el else 'NOT FOUND'}")
        per = soup.find_all('span', class_='rating_per')
        log(f"  rating_per count: {len(per)}, values: {[e.get_text(strip=True) for e in per]}")
        votes_el = soup.find('span', property='v:votes')
        log(f"  v:votes element: {votes_el.get_text(strip=True) if votes_el else 'NOT FOUND'}")
    else:
        log(f"  response[:300]: {r4.text[:300]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 测试4: 直接访问详情页不预热 ----
log("\n=== TEST4: Direct detail page without warmup ===")
try:
    r5 = requests.get('https://movie.douban.com/subject/1292052/', headers=HEADERS_BASE, timeout=15)
    log(f"  status: {r5.status_code}, length: {len(r5.text)}")
    if r5.status_code == 200:
        jld = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', r5.text)
        log(f"  ratingValue: {jld.group(1) if jld else 'NOT FOUND'}")
    else:
        log(f"  response[:200]: {r5.text[:200]}")
except Exception as e:
    log(f"  ERROR: {e}")

# ---- 输出到文件 ----
with open('debug_douban2_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
print("\nResults also written to debug_douban2_result.txt")
