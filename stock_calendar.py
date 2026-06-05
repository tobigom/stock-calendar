"""
주식 전용 캘린더 HTML 생성기

- naver_crawler.py로 수집한 korea_events.json 데이터를 불러옵니다.
- global_crawler.py로 수집한 global_events.json 데이터를 불러옵니다.
- telegram_events.py로 수집한 telegram_events.json 데이터를 불러옵니다.
- 세 데이터를 병합하여 FullCalendar 기반 HTML 파일로 생성합니다.
- JSON 파일이 없으면 기본 샘플 데이터를 사용합니다.
"""
import json
import os
import sys

# 크롤링된 JSON 파일 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KOREA_EVENTS_JSON = os.path.join(BASE_DIR, "korea_events.json")
GLOBAL_EVENTS_JSON = os.path.join(BASE_DIR, "global_events.json")
TELEGRAM_EVENTS_JSON = os.path.join(BASE_DIR, "telegram_events.json")

# 1. 이벤트 데이터 로드
stock_events = []

# 1-1. 글로벌 경제 이벤트 로드
if os.path.exists(GLOBAL_EVENTS_JSON):
    try:
        with open(GLOBAL_EVENTS_JSON, "r", encoding="utf-8") as f:
            global_events = json.load(f)
        print(f"[OK] {GLOBAL_EVENTS_JSON}에서 {len(global_events)}건의 글로벌 일정을 불러왔습니다.")
        stock_events.extend(global_events)
    except Exception as e:
        print(f"[WARN] 글로벌 JSON 파일 로드 실패: {e}")

# 1-2. 국내 주식 이벤트 로드
if os.path.exists(KOREA_EVENTS_JSON):
    try:
        with open(KOREA_EVENTS_JSON, "r", encoding="utf-8") as f:
            korea_events = json.load(f)
        print(f"[OK] {KOREA_EVENTS_JSON}에서 {len(korea_events)}건의 국내 일정을 불러왔습니다.")
        stock_events.extend(korea_events)
    except Exception as e:
        print(f"[WARN] 국내 JSON 파일 로드 실패: {e}")

# 1-3. 텔레그램 이벤트 로드
if os.path.exists(TELEGRAM_EVENTS_JSON):
    try:
        with open(TELEGRAM_EVENTS_JSON, "r", encoding="utf-8") as f:
            telegram_events = json.load(f)
        print(f"[OK] {TELEGRAM_EVENTS_JSON}에서 {len(telegram_events)}건의 텔레그램 일정을 불러왔습니다.")
        stock_events.extend(telegram_events)
    except Exception as e:
        print(f"[WARN] 텔레그램 JSON 파일 로드 실패: {e}")

# JSON 파일이 없거나 비어있으면 샘플 데이터 사용
if not stock_events:
    print("[INFO] 크롤링된 데이터가 없습니다. 샘플 데이터를 사용합니다.")
    stock_events = [
        {"date": "2026-06-08", "title": "공모주 청약: 에이치비 테크", "type": "ipo"},
        {"date": "2026-06-12", "title": "미국 소비자물가지수(CPI) 발표", "type": "macro"},
        {"date": "2026-06-18", "title": "엔비디아(NVDA) 실적 발표", "type": "earnings"},
        {"date": "2026-06-25", "title": "삼성전자 배당금 지급일", "type": "dividend"},
    ]

# 2. HTML 및 FullCalendar 라이브러리를 활용한 템플릿 작성
html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>나의 주식 전용 캘린더</title>
    <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css' rel='stylesheet' />
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js'></script>
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            background-color: #f4f6f9;
            margin: 0;
            padding: 20px;
        }}
        #calendar-container {{
            max-width: 1100px;
            margin: 0 auto;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        h2 {{
            text-align: center;
            color: #333;
        }}
        /* 이벤트 유형별 색상 지정 */
        .fc-event-ipo {{ background-color: #e74c3c !important; border-color: #e74c3c !important; }}
        .fc-event-macro {{ background-color: #3498db !important; border-color: #3498db !important; }}
        .fc-event-earnings {{ background-color: #9b59b6 !important; border-color: #9b59b6 !important; }}
        .fc-event-dividend {{ background-color: #2ecc71 !important; border-color: #2ecc71 !important; }}
    </style>
</head>
<body>

    <div id="calendar-container">
        <h2>📈 주식 일정 관리 캘린더</h2>
        <div id='calendar'></div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var calendarEl = document.getElementById('calendar');
            
            // 파이썬 데이터를 자바스크립트 배열로 변환
            var rawEvents = {json.dumps(stock_events, ensure_ascii=False)};
            
            // FullCalendar 형식에 맞게 맵핑
            var events = rawEvents.map(function(item) {{
                return {{
                    title: item.title,
                    start: item.date,
                    className: 'fc-event-' + item.type
                }};
            }});

            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: 'dayGridMonth',
                locale: 'ko', // 한국어 설정
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek'
                }},
                events: events
            }});
            
            calendar.render();
        }});
    </script>
</body>
</html>
"""

# 3. HTML 파일로 저장 (깃허브 페이지 연동을 위해 index.html로 변경)
output_path = os.path.join(BASE_DIR, "index.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"[OK] 주식 캘린더({output_path})가 성공적으로 생성되었습니다!")
print(f"   총 {len(stock_events)}건의 일정이 포함되어 있습니다.")
print("   파일을 더블클릭해 브라우저에서 확인하세요.")


