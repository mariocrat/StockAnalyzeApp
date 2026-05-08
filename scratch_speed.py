import sys, time
sys.path.insert(0, r'd:\작업\windsurf\StockAnalyze\backend')
from core.data_fetcher import get_krx_themes

print("Test 1: get_krx_themes (cold call)")
t0 = time.time()
themes, names, returns_map = get_krx_themes()
t1 = time.time()
print(f"  Time: {t1-t0:.2f}s")
print(f"  Themes: {len(themes)}, Names: {len(names)}")
first_theme = list(themes.keys())[0]
print(f"  First theme: '{first_theme}', stocks: {themes[first_theme][:3]}")
print(f"  Returns sample: {list(returns_map.get(first_theme, {}).items())[:3]}")

print("\nTest 2: get_krx_themes (cached call)")
t0 = time.time()
themes2, _, _ = get_krx_themes()
t1 = time.time()
print(f"  Time: {t1-t0:.4f}s (should be ~0ms)")
