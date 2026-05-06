import yfinance as yf
import time

tickers = ["005930", "000660", "035420", "035720"] * 50 # 200 tickers
yf_tickers = [f"{t}.KS" for t in tickers]

start = time.time()
# verbose=False to suppress output
data = yf.download(yf_tickers, start="2026-04-29", end="2026-05-06", group_by="ticker", threads=True, progress=False)
print(f"Took {time.time()-start:.2f}s")
