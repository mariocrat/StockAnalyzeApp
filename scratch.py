import yfinance as yf
import time

start = time.time()
data = yf.download("005930.KS 000660.KS 035420.KS", start="2026-04-29", end="2026-05-06")['Close']
print(f"Took {time.time()-start:.2f}s")
print(data.head())
