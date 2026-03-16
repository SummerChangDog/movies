# -*- coding: utf-8 -*-
"""验证 Cookie 配置和爬虫实例初始化"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from config import DOUBAN_COOKIE_BID, DOUBAN_COOKIE_DBCL2
from douban_movie_scraper import DoubanMovieScraper

print("=== Cookie 配置检查 ===")
print(f"DOUBAN_COOKIE_BID   = {repr(DOUBAN_COOKIE_BID)}")
print(f"DOUBAN_COOKIE_DBCL2 = {repr(DOUBAN_COOKIE_DBCL2)}")
cookie_ok = bool(DOUBAN_COOKIE_DBCL2)
print(f"Cookie 已配置: {cookie_ok}")
print()

print("=== 爬虫实例初始化测试 ===")
s = DoubanMovieScraper(bid=DOUBAN_COOKIE_BID, dbcl2=DOUBAN_COOKIE_DBCL2)
print(f"scraper.cookie_available = {s.cookie_available}")
print()

if not cookie_ok:
    print("[INFO] 当前未配置豆瓣 Cookie，豆瓣评分将无法获取。")
    print()
    print("[HOW-TO] 获取方法：")
    print("  1. 浏览器打开 https://www.douban.com 并登录账号")
    print("  2. F12 -> Application -> Cookies -> .douban.com")
    print("  3. 复制 'bid' 和 'dbcl2' 的值")
    print("  4. 填入 .env 文件:")
    print("     DOUBAN_COOKIE_BID=你的bid值")
    print("     DOUBAN_COOKIE_DBCL2=你的dbcl2值")
    print("  5. 重启服务器")
    print()
    print("[UI] 前端豆瓣卡片将显示 '⚠️ 需配置 Cookie' 提示。")
else:
    print("[OK] Cookie 已配置，将尝试使用登录态访问豆瓣。")
