import cloudscraper
import json

scraper = cloudscraper.create_scraper()

# Test 1: ForexFactory
print("=== Test 1: ForexFactory ===")
resp = scraper.get('https://www.forexfactory.com/calendar', timeout=20)
print('Status:', resp.status_code, 'Length:', len(resp.text))
if 'calendar__row' in resp.text:
    print('SUCCESS: Found calendar rows')
elif 'calendar' in resp.text.lower():
    print('Found calendar keyword')
print('First 200:', resp.text[:200])
print()

# Test 2: Investing.com main page
print("=== Test 2: Investing.com main ===")
resp2 = scraper.get('https://www.investing.com/', timeout=20)
print('Status:', resp2.status_code, 'Length:', len(resp2.text))
if 'economicCalendarData' in resp2.text:
    print('SUCCESS: Found economicCalendarData')
print('First 200:', resp2.text[:200])
print()

# Test 3: Investing.com economic calendar page
print("=== Test 3: Investing.com economic-calendar ===")
resp3 = scraper.get('https://www.investing.com/economic-calendar/', timeout=20)
print('Status:', resp3.status_code, 'Length:', len(resp3.text))
if 'economicCalendarData' in resp3.text:
    print('SUCCESS: Found economicCalendarData')
print('First 200:', resp3.text[:200])
print()

# Save responses
with open(r'C:\stock_calendar\test_forex.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)
with open(r'C:\stock_calendar\test_investing_main.html', 'w', encoding='utf-8') as f:
    f.write(resp2.text)
with open(r'C:\stock_calendar\test_investing_cal.html', 'w', encoding='utf-8') as f:
    f.write(resp3.text)
print("All responses saved.")
