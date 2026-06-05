from bs4 import BeautifulSoup

with open(r'C:\stock_calendar\test_forex.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'lxml')

# Find calendar rows
rows = soup.select('tr.calendar__row')
print(f'Found {len(rows)} calendar rows')

# Look at first few rows
for i, row in enumerate(rows[:5]):
    print(f'\n--- Row {i+1} ---')
    # Date
    date_cell = row.select_one('td.calendar__date')
    date = date_cell.get_text(strip=True) if date_cell else 'N/A'
    print(f'Date: {date}')
    
    # Time
    time_cell = row.select_one('td.calendar__time')
    time = time_cell.get_text(strip=True) if time_cell else 'N/A'
    print(f'Time: {time}')
    
    # Currency
    curr_cell = row.select_one('td.calendar__currency')
    curr = curr_cell.get_text(strip=True) if curr_cell else 'N/A'
    print(f'Currency: {curr}')
    
    # Event
    event_cell = row.select_one('td.calendar__event')
    event = event_cell.get_text(strip=True) if event_cell else 'N/A'
    print(f'Event: {event}')
    
    # Impact (importance)
    impact_cell = row.select_one('td.calendar__impact')
    impact_spans = impact_cell.select('span[class*="impact"]') if impact_cell else []
    impact_count = len(impact_spans)
    print(f'Impact (stars): {impact_count}')
    
    # Previous/Forecast
    prev_cell = row.select_one('td.calendar__previous')
    prev = prev_cell.get_text(strip=True) if prev_cell else 'N/A'
    print(f'Previous: {prev}')
    
    forecast_cell = row.select_one('td.calendar__forecast')
    forecast = forecast_cell.get_text(strip=True) if forecast_cell else 'N/A'
    print(f'Forecast: {forecast}')

# Also check for date separator rows (weekly headers)
date_seps = soup.select('tr.calendar__date-separator')
print(f'\n\nFound {len(date_seps)} date separators')
for ds in date_seps[:3]:
    print(f'  Date sep: {ds.get_text(strip=True)}')
