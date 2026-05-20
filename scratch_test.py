import requests
try:
    res = requests.get("http://localhost:8000/api/themes?period=1D", timeout=10)
    print("Status:", res.status_code)
    print("Data:", res.json()[:2])
except Exception as e:
    print("Error:", e)
