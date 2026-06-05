import cloudscraper
import json

scraper = cloudscraper.create_scraper()

# Try Investing.com API endpoint directly
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.investing.com/economic-calendar/',
}

payload = {
    'country[]': ['5', '32', '37', '72'],
    'importance[]': ['2', '3'],
    'dateFrom': '2026-06-01',
    'dateTo': '2026-07-31',
    'timeZone': '18',
    'currentTab': 'calendar',
    'limit': '100',
}

resp = scraper.post('https://www.investing.com/economic-calendar/FilterAjaxLoad',
                     data=payload, headers=headers, timeout=20)

print('Status:', resp.status_code)
print('Length:', len(resp.text))
print('---First 800 chars---')
print(resp.text[:800])
print('---End---')

# Save to file for inspection
with open(r'C:\stock_calendar\investing_response.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)
print('Saved to investing_response.html')
