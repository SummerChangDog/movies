"""诊断脚本：追踪"简爱"搜索的每一步（无 emoji 版）"""
import sys
import os

print("=== Diagnosis Start ===")

from config import OMDB_API_KEY
has_key = bool(OMDB_API_KEY and OMDB_API_KEY != 'your-api-key-here')
print(f"[Step 1] OMDB_API_KEY: {'SET (' + OMDB_API_KEY[:4] + '...)' if has_key else 'NOT SET or invalid'}")

print("\n[Step 2] Douban search for Jane Eyre...")
from douban_movie_scraper import DoubanMovieScraper
scraper = DoubanMovieScraper(delay_enable=False)
info = scraper.search_movie('\u7b80\u7231')
if info:
    print(f"  title: {info.get('title')}")
    print(f"  rating: {info.get('rating')}")
    print(f"  year: {info.get('year')}")
    print(f"  imdb_id: '{info.get('imdb_id', '')}'")
    print(f"  subtitle: '{info.get('subtitle', '')}'")
    print(f"  poster: {info.get('poster','')[:80]}")
else:
    print("  FAILED: Douban returned None")

subtitle = info.get('subtitle', '') if info else ''
imdb_id = info.get('imdb_id', '') if info else ''

if imdb_id and has_key:
    print(f"\n[Step 3a] Query OMDb by IMDb ID '{imdb_id}'...")
    import requests
    resp = requests.get('http://www.omdbapi.com/', params={
        'apikey': OMDB_API_KEY, 'i': imdb_id, 'plot': 'full'
    }, timeout=10)
    data = resp.json()
    print(f"  Response={data.get('Response')}, IMDb={data.get('imdbRating')}, Title={data.get('Title')}")
elif imdb_id and not has_key:
    print(f"\n[Step 3a] IMDb ID found: '{imdb_id}' but NO OMDB_API_KEY - cannot query")

if subtitle and not imdb_id:
    print(f"\n[Step 3b] Query OMDb by subtitle '{subtitle}'...")
    if has_key:
        import requests
        resp = requests.get('http://www.omdbapi.com/', params={
            'apikey': OMDB_API_KEY, 's': subtitle, 'type': 'movie'
        }, timeout=10)
        data = resp.json()
        print(f"  Response={data.get('Response')}, count={len(data.get('Search', []))}")
        if data.get('Search'):
            first = data['Search'][0]
            print(f"  First result: {first.get('Title')} ({first.get('Year')}) imdbID={first.get('imdbID')}")
            # get details
            resp2 = requests.get('http://www.omdbapi.com/', params={
                'apikey': OMDB_API_KEY, 'i': first['imdbID'], 'plot': 'full'
            }, timeout=10)
            d2 = resp2.json()
            print(f"  IMDb Rating: {d2.get('imdbRating')}, Votes: {d2.get('imdbVotes')}")
        else:
            print(f"  Error: {data.get('Error')}")
    else:
        print(f"  NO OMDB_API_KEY - cannot query OMDb")
        print(f"  NOTE: subtitle='{subtitle}' is available but needs OMDB_API_KEY to get IMDb score")

print("\n=== Diagnosis Complete ===")
