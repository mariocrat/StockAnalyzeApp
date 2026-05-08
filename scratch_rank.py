import sys, time
sys.path.insert(0, r'd:\작업\windsurf\StockAnalyze\backend')
from core.metrics import calculate_theme_rankings

import datetime
today = datetime.date.today()
start = (today - datetime.timedelta(days=7)).strftime('%Y%m%d')
end = today.strftime('%Y%m%d')

print("Test: calculate_theme_rankings (cold call)")
t0 = time.time()
df = calculate_theme_rankings(start, end)
t1 = time.time()
print(f"  Time: {t1-t0:.2f}s")
print(f"  Themes ranked: {len(df)}")
if not df.empty:
    print(df[['Rank','Theme','Avg Return (%)']].head(5).to_string())

print("\nTest: calculate_theme_rankings (cached call)")
t0 = time.time()
df2 = calculate_theme_rankings(start, end)
t1 = time.time()
print(f"  Time: {t1-t0:.4f}s")
