import time
from backend.core.data_fetcher import get_krx_themes

start = time.time()
themes, names = get_krx_themes()
end = time.time()
print(f"Time taken to get themes: {end - start:.2f} seconds")
