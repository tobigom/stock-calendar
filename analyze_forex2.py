from bs4 import BeautifulSoup

with open(r'C:\stock_calendar\test_forex.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'lxml')
rows = soup.select('tr.calendar__row')

with open(r'C:\stock_calendar\analyze_forex2_output.txt', 'w', encoding='utf-8') as out:
    out.write(f'Found {len(rows)} calendar rows\n\n')
    
    for i, row in enumerate(rows[:20]):
        # Date
        date_cell = row.select_one('td.calendar__date')
        date = date_cell.get_text(strip=True) if date_cell else 'N/A'
        
        # Currency
        curr_cell = row.select_one('td.calendar__currency')
        curr = curr_cell.get_text(strip=True) if curr_cell else 'N/A'
        
        # Event
        event_cell = row.select_one('td.calendar__event')
        event = event_cell.get_text(strip=True) if event_cell else 'N/A'
        
        # Impact - detailed analysis
        impact_cell = row.select_one('td.calendar__impact')
        impact_html = str(impact_cell)[:400] if impact_cell else 'N/A'
        
        # Count all span/i elements
        all_spans = impact_cell.find_all(['span', 'i']) if impact_cell else []
        span_classes = [s.get('class') for s in all_spans]
        
        # Count by class pattern
        impact_spans = impact_cell.select('span[class*="impact"], i[class*="impact"]') if impact_cell else []
        
        # Count by any element with impact in class
        any_impact = impact_cell.find_all(class_=lambda c: c and 'impact' in ' '.join(c) if c else False) if impact_cell else []
        
        out.write(f'--- Row {i+1} ---\n')
        out.write(f'Date: {date}\n')
        out.write(f'Currency: {curr}\n')
        out.write(f'Event: {event}\n')
        out.write(f'Impact HTML: {impact_html}\n')
        out.write(f'All span/i: {len(all_spans)}, classes: {span_classes}\n')
        out.write(f'Impact spans: {len(impact_spans)}\n')
        out.write(f'Any impact elements: {len(any_impact)}\n\n')
