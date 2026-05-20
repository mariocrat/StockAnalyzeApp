from core.data_fetcher import get_theme_returns_historical
import datetime
import pandas as pd

start_dt = datetime.date.today() - datetime.timedelta(days=30)
start_date = start_dt.strftime("%Y%m%d")
end_date = datetime.date.today().strftime("%Y%m%d")

try:
    df = get_theme_returns_historical(start_date, end_date)
    print("Columns:", df.columns if isinstance(df, pd.DataFrame) else type(df))
    print("Head:", df.head() if isinstance(df, pd.DataFrame) else df)
except Exception as e:
    import traceback
    traceback.print_exc()
