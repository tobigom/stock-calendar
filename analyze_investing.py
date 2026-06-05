from bs4 import BeautifulSoup
import re, json

with open(r'C:\stock_calendar\test_investing_cal.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Look for JSON data in Next.js __NEXT_DATA__
match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    print('Found __NEXT_DATA__')
    props = data.get('props', {}).get('pageProps', {})
    print('Keys:', list(props.keys())[:20])
else:
    print('No __NEXT_DATA__ found')

# Look for economicCalendar
if 'economicCalendar' in html:
    print('\nFound economicCalendar in HTML')
    idx = html.index('economicCalendar')
    print(html[max(0,idx-200):idx+500])
else:
    print('\nNo economicCalendar found')

# Look for any JSON data
json_matches = re.findall(r'\{[^{}]*"date"[^{}]*"title"[^{}]*\}', html)
print(f'\nFound {len(json_matches)} potential JSON date/title objects')
