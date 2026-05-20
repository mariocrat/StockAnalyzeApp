import pandas as pd
import datetime

# Create a dummy df_t
dates = pd.date_range(start="2024-04-10", end="2024-05-18", freq="B")
df_t = pd.DataFrame({
    'Close': [100 + i for i in range(len(dates))]
}, index=dates)

start_dt = pd.to_datetime("2024-04-17")
end_dt = pd.to_datetime("2024-05-17")

open_row = df_t[df_t.index <= start_dt]
close_row = df_t[df_t.index <= end_dt]

if not open_row.empty and not close_row.empty:
    open_p = open_row['Close'].iloc[-1]
    close_p = close_row['Close'].iloc[-1]
    print(f"open_p: {open_p}, close_p: {close_p}")
else:
    print("Empty rows")
