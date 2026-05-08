import time
import requests

start = time.time()
res = requests.get('http://localhost:8000/api/themes?start_date=20260501&end_date=20260508')
end = time.time()
print(f"Time taken: {end - start:.2f} seconds")
print(f"Status: {res.status_code}")
print(f"Response length: {len(res.text)}")
