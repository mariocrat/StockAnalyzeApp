import time
from pykrx import stock

try:
    start = time.time()
    df1 = stock.get_market_ohlcv("20260501", market="ALL")
    df2 = stock.get_market_ohlcv("20260508", market="ALL")
    end = time.time()
    print(f"KRX time: {end - start:.2f} seconds")
    print(f"Data1 length: {len(df1)}")
    print(f"Data2 length: {len(df2)}")
except Exception as e:
    print(f"Error: {e}")
