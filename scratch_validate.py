import sys, datetime, json
sys.path.insert(0, r'd:\작업\windsurf\StockAnalyze\backend')

# Test the full pipeline as the API would
from core.data_fetcher import get_stock_ohlcv
import pandas as pd

ticker = '005930'
today = datetime.date.today()
dt_start = datetime.datetime(today.year - 1, today.month, today.day)
padded_start = (dt_start - datetime.timedelta(days=365)).strftime('%Y%m%d')
end_date = today.strftime('%Y%m%d')

df = get_stock_ohlcv(ticker, padded_start, end_date)
df = df.copy().sort_index(ascending=True)

for ma in [20, 60, 120]:
    df[f'MA_{ma}'] = df['Close'].rolling(window=ma).mean()

df['BB_Basis'] = df['Close'].rolling(window=20).mean()
bb_std = df['Close'].rolling(window=20).std()
df['BB_Upper'] = df['BB_Basis'] + 2 * bb_std
df['BB_Lower'] = df['BB_Basis'] - 2 * bb_std

df = df[df.index >= dt_start]
df = df.ffill().bfill()
df = df.dropna(subset=['Open','High','Low','Close'])
df['Date'] = df.index.strftime('%Y-%m-%d')
df = df.replace([float('inf'), float('-inf')], None)
df = df.where(pd.notnull(df), None)

records = df.to_dict(orient='records')
print(f"Total records: {len(records)}")
if records:
    r = records[0]
    print(f"First date: {r['Date']}")
    print(f"OHLCV: O={r['Open']} H={r['High']} L={r['Low']} C={r['Close']} V={r['Volume']}")
    print(f"MA20={r.get('MA_20'):.2f}  MA60={r.get('MA_60'):.2f}  MA120={r.get('MA_120'):.2f}")
    print(f"BB_Basis={r.get('BB_Basis'):.2f}  BB_Upper={r.get('BB_Upper'):.2f}  BB_Lower={r.get('BB_Lower'):.2f}")
    print(f"Date format OK: {'Date' in r and len(r['Date'])==10}")
    
    # Check for any NaN
    nan_keys = [k for k,v in r.items() if v is None and k not in ('Date',)]
    print(f"None-valued fields in first row: {nan_keys}")
    
    last = records[-1]
    print(f"\nLast date: {last['Date']}")
    print(f"Sorted ascending: {records[0]['Date'] < records[-1]['Date']}")
