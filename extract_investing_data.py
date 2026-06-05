import re, json

with open(r'C:\stock_calendar\test_investing_cal.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Extract __NEXT_DATA__
match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    
    # Navigate to economicCalendarStore
    try:
        state = data['props']['pageProps']['state']
        cal_store = state['economicCalendarStore']
        events_by_date = cal_store.get('calendarEventsByDate', {})
        
        print(f'Found events for {len(events_by_date)} dates')
        
        total_events = 0
        for date_str, events in sorted(events_by_date.items()):
            for ev in events:
                importance = int(ev.get('importance', '0'))
                currency = ev.get('currency', '')
                event_name = ev.get('event', '')
                event_type = ev.get('type', '')
                
                # Only US events with importance >= 2
                if currency == 'USD' and importance >= 2:
                    total_events += 1
                    print(f'  [{date_str}] (imp={importance}) {event_name}')
        
        print(f'\nTotal US high-importance events: {total_events}')
        
        # Also show some non-US important events
        print('\n--- Other important events (imp>=2) ---')
        for date_str, events in sorted(events_by_date.items()):
            for ev in events:
                importance = int(ev.get('importance', '0'))
                currency = ev.get('currency', '')
                event_name = ev.get('event', '')
                if currency != 'USD' and importance >= 2:
                    print(f'  [{date_str}] {currency} (imp={importance}) {event_name}')
                    
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
