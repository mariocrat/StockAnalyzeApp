import time
from pykrx import stock

start = time.time()
df = stock.get_market_price_change_by_ticker("20260501", "20260508", market="ALL")
end = time.time()
print(f"KRX time: {end - start:.2f} seconds")
print(f"Data length: {len(df)}")
