import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0'}
url = 'https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no=227'
res = requests.get(url, headers=headers)
res.encoding = 'euc-kr'
soup = BeautifulSoup(res.text, 'html.parser')

# Print first 3 stock rows raw HTML to inspect structure
rows = soup.select('tr')
count = 0
for row in rows:
    if row.select_one('div.name_area'):
        print("=== ROW ===")
        print(row.prettify()[:1500])
        count += 1
        if count >= 2:
            break
