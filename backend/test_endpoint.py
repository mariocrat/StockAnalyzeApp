import pandas as pd
import datetime
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
try:
    response = client.get("/api/stock/005930?start_date=20150101&end_date=20240101&interval=1d")
    print(response.status_code)
    print(response.json())
except Exception as e:
    import traceback
    traceback.print_exc()
