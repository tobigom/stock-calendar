"""
주식 캘린더 통합 HTML 생성기 (update_calendar.py)

- korea_events.json (네이버 국내 일정) + global_events.json (Investing 글로벌 일정) 병합
- 동일 날짜 + 동일 제목 중복 제거
- FullCalendar v6 기반 HTML 생성 (korea=주황, global=파랑)
- 결과: index.html

사용법:
    python update_calendar.py
"""
import json
import os
import sys

# ============================================================
# 설정
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KOREA_JSON = os.path.join(BASE_DIR, "korea_events.json")
GLOBAL_JSON = os.path.join(BASE_DIR, "global_events.json")
QUALITATIVE_JSON = os.path.join(BASE_DIR, "qualitative_events.json")
OUTPUT_HTML = os.path.join(BASE_DIR, "index.html")


def load_json(filepath: str) -> list:
    """JSON 파일을 읽어 리스트로 반환. 파일이 없으면 빈 리스트."""
    if not os.path.exists(filepath):
        print(f"  [SKIP] {os.path.basename(filepath)} 파일 없음")
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  [OK] {os.path.basename(filepath)}: {len(data)}건 로드")
        return data
    except Exception as e:
        print(f"  [WARN] {os.path.basename(filepath)} 로드 실패: {e}")
        return []


def merge_and_deduplicate(*event_lists: list) -> list:
    """
    여러 리스트를 병합하고 (date, title) 기준 중복 제거.
    앞쪽 리스트의 이벤트가 우선순위 높음.
    
    특별 처리:
    - "공모주 상장(예상): 종목명" 과 "공모주 상장: 종목명" 이 동시에 있으면
      확정일(상장)을 우선하고 예상일 제거
    """
    seen = set()
    merged = []

    for events in event_lists:
        for event in events:
            key = (event.get("date", ""), event.get("title", ""))
            if key not in seen:
                seen.add(key)
                merged.append(event)

    # ============================================================
    # "공모주 상장(예상)" 중복 제거 로직
    # 같은 종목에 대해 확정 상장일이 있으면 예상일 제거
    # ============================================================
    # 확정 상장일 종목명 목록
    confirmed_listing_stocks = set()
    for ev in merged:
        title = ev.get("title", "")
        if title.startswith("공모주 상장: ") and "(예상)" not in title:
            stock_name = title.replace("공모주 상장: ", "").strip()
            confirmed_listing_stocks.add(stock_name)
    
    # 예상 상장일 중 확정일이 있는 종목 제거
    filtered = []
    for ev in merged:
        title = ev.get("title", "")
        if title.startswith("공모주 상장(예상): "):
            stock_name = title.replace("공모주 상장(예상): ", "").strip()
            if stock_name in confirmed_listing_stocks:
                continue  # 확정일이 있으면 예상일 제거
        filtered.append(ev)
    
    merged = filtered

    # 날짜순 정렬
    merged.sort(key=lambda x: x.get("date", ""))
    return merged



def generate_html(events: list) -> str:
    """
    FullCalendar v6 기반 HTML 템플릿 생성.
    - type == "korea"  → 주황색 (#f39c12)
    - type == "global" → 파란색 (#3498db)
    - type == "qualitative" → category별 세분화된 색상
    - type == "futures_options" → 진회색 (#2c3e50)
    - 그 외 타입(ipo, macro, earnings, dividend 등)도 각각 색상 유지
    """
    events_json = json.dumps(events, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📈 주식 일정 통합 캘린더</title>
    <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.css' rel='stylesheet' />
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js'></script>
    <style>
        body {{
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            background-color: #f0f2f5;
            margin: 0;
            padding: 20px;
        }}
        #calendar-container {{
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}
        h2 {{
            text-align: center;
            color: #222;
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 1.6em;
        }}
        .legend {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 10px 20px;
            margin-bottom: 16px;
            font-size: 0.85em;
            color: #555;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .legend-dot {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 3px;
            flex-shrink: 0;
        }}
        /* ============================================================
           이벤트 타입별 색상 (기본 타입)
           ============================================================ */
        .fc-event-korea {{ background-color: #f39c12 !important; border-color: #f39c12 !important; }}
        .fc-event-global {{ background-color: #3498db !important; border-color: #3498db !important; }}
        .fc-event-ipo {{ background-color: #e74c3c !important; border-color: #e74c3c !important; }}
        .fc-event-macro {{ background-color: #3498db !important; border-color: #3498db !important; }}
        .fc-event-earnings {{ background-color: #9b59b6 !important; border-color: #9b59b6 !important; }}
        .fc-event-dividend {{ background-color: #2ecc71 !important; border-color: #2ecc71 !important; }}
        .fc-event-telegram {{ background-color: #e67e22 !important; border-color: #e67e22 !important; }}
        .fc-event-futures_options {{ background-color: #2c3e50 !important; border-color: #2c3e50 !important; }}
        /* ============================================================
           정성 분석(Qualitative) 카테고리별 세분화 색상
           ============================================================ */
        .fc-event-qualitative-인사\\/방문 {{ background-color: #e67e22 !important; border-color: #e67e22 !important; }}
        .fc-event-qualitative-통화정책 {{ background-color: #c0392b !important; border-color: #c0392b !important; }}
        .fc-event-qualitative-정부정책 {{ background-color: #8e44ad !important; border-color: #8e44ad !important; }}
        .fc-event-qualitative-국제관계 {{ background-color: #2c3e50 !important; border-color: #2c3e50 !important; }}
        .fc-event-qualitative-정치 {{ background-color: #7f8c8d !important; border-color: #7f8c8d !important; }}
        .fc-event-qualitative-컨퍼런스 {{ background-color: #16a085 !important; border-color: #16a085 !important; }}
        .fc-event-qualitative-경제지표 {{ background-color: #2980b9 !important; border-color: #2980b9 !important; }}
        /* ============================================================
           툴팁 스타일 (FullCalendar 기본 툴팁 + 커스텀)
           ============================================================ */
        .fc-event {{
            cursor: pointer;
        }}
        .fc-event[title]:hover::after {{
            content: attr(title);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.85);
            color: #fff;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            white-space: nowrap;
            z-index: 1000;
            pointer-events: none;
            margin-bottom: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
    </style>
</head>
<body>

    <div id="calendar-container">
        <h2>📈 주식 일정 통합 캘린더</h2>
        <div class="legend">
            <span class="legend-item">
                <span class="legend-dot" style="background:#f39c12;"></span> 국내
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#3498db;"></span> 해외
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#e74c3c;"></span> IPO
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#9b59b6;"></span> 실적
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#2ecc71;"></span> 배당
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#e67e22;"></span> 인사/방문
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#c0392b;"></span> 통화정책
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#8e44ad;"></span> 정부정책
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#16a085;"></span> 컨퍼런스
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#2980b9;"></span> 경제지표
            </span>
            <span class="legend-item">
                <span class="legend-dot" style="background:#2c3e50;"></span> 선물옵션
            </span>
        </div>
        <div id='calendar'></div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var calendarEl = document.getElementById('calendar');
            var rawEvents = {events_json};

            var events = rawEvents.map(function(item) {{
                var cls = 'fc-event-' + (item.type || 'korea');
                // 정성 분석 이벤트는 category별로 세분화
                if (item.type === 'qualitative' && item.category) {{
                    cls = 'fc-event-qualitative-' + item.category;
                }}
                return {{
                    title: item.title,
                    start: item.date,
                    className: cls
                }};
            }});

            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: 'dayGridMonth',
                locale: 'ko',
                height: 'auto',
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek'
                }},
                events: events,
                eventDidMount: function(info) {{
                    // 모든 이벤트에 마우스 호버 시 전체 제목 표시 (툴팁)
                    info.el.title = info.event.title;
                }}
            }});

            calendar.render();
        }});
    </script>
</body>
</html>"""


def main():
    print("=" * 60)
    print("  [주식 캘린더 통합 생성기] (update_calendar.py)")
    print("=" * 60)

    # 1. JSON 파일 로드
    print("\n[1/5] 국내 일정 로드 중...")
    korea_events = load_json(KOREA_JSON)

    print("\n[2/5] 해외 일정 로드 중...")
    global_events = load_json(GLOBAL_JSON)

    print("\n[3/5] 정성 분석 일정 로드 중...")
    qualitative_events = load_json(QUALITATIVE_JSON)

    # 2. 병합 및 중복 제거
    print("\n[4/5] 데이터 병합 및 중복 제거 중...")
    merged = merge_and_deduplicate(korea_events, global_events, qualitative_events)
    total_before = len(korea_events) + len(global_events) + len(qualitative_events)
    print(f"  → 병합 전: 국내 {len(korea_events)}건 + 해외 {len(global_events)}건 + 정성 {len(qualitative_events)}건 = {total_before}건")
    print(f"  → 병합 후 (중복 제거): {len(merged)}건")

    if not merged:
        print("\n  ⚠️ 표시할 일정이 없습니다. 샘플 데이터를 사용합니다.")
        merged = [
            {"date": "2026-06-08", "title": "공모주 청약: 에이치비 테크", "type": "ipo"},
            {"date": "2026-06-12", "title": "미국 소비자물가지수(CPI) 발표", "type": "macro"},
            {"date": "2026-06-18", "title": "엔비디아(NVDA) 실적 발표", "type": "earnings"},
            {"date": "2026-06-25", "title": "삼성전자 배당금 지급일", "type": "dividend"},
        ]

    # 3. HTML 생성
    print("\n[4/4] HTML 캘린더 생성 중...")
    html_content = generate_html(merged)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  [OK] {OUTPUT_HTML} 생성 완료!")
    print(f"  [INFO] 총 {len(merged)}건의 일정 포함")

    # 4. 요약 출력
    print("\n" + "=" * 60)
    print("  [일정 요약]")
    print("=" * 60)
    type_count = {}
    for ev in merged:
        t = ev.get("type", "unknown")
        type_count[t] = type_count.get(t, 0) + 1
    for t, cnt in sorted(type_count.items()):
        print(f"    {t:12s}: {cnt}건")
    print("=" * 60)
    print(f"  파일을 더블클릭하여 브라우저에서 확인하세요.")
    print("=" * 60)


if __name__ == "__main__":
    main()
