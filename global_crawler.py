"""
글로벌 경제 캘린더 크롤러
- Investing.com (메인): Next.js __NEXT_DATA__에서 경제 캘린더 데이터 추출
- ForexFactory (백업): HTML 파싱으로 경제 캘린더 데이터 추출
"""
from __future__ import annotations
import json
import re
import os
from datetime import datetime, timedelta
from typing import Optional

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

# ============================================================
# 1. Investing.com 크롤러 (메인)
# ============================================================

INVESTING_URL = "https://www.investing.com/economic-calendar/"

# 중요도가 높은 주요 통화 목록
MAJOR_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF"}

# ============================================================
# 중요도 3(🔴) - 무조건 포함해야 할 핵심 지표
# ============================================================
CORE_INDICATORS = [
    "Nonfarm Payrolls", "Unemployment Rate", "CPI", "Core CPI",
    "PCE", "Core PCE", "GDP", "GDP", "Interest Rate Decision",
    "FOMC", "Fed", "Federal Funds", "Average Hourly Earnings",
    "ISM Manufacturing", "ISM Services", "ISM Non-Manufacturing",
    "Retail Sales", "Industrial Production", "Consumer Confidence",
    "Michigan Consumer Sentiment", "Existing Home Sales",
    "New Home Sales", "Durable Goods Orders", "Factory Orders",
    "Jobless Claims", "Initial Jobless Claims", "Continuing Claims",
    "Trade Balance", "Current Account", "Treasury",
    "Powell", "Lagarde", "Bailey", "Kuroda", "Ueda",
    "BOJ", "BOE", "ECB", "PBOC", "FOMC Minutes",
    "Employment Cost Index", "Productivity", "Labor Costs",
    "Building Permits", "Housing Starts", "Philadelphia Fed",
    "Empire State Manufacturing", "NAHB Housing Market",
    "Wholesale Inventories", "Business Inventories",
    "Import Prices", "Export Prices", "PPI", "Core PPI",
    "Consumer Credit", "Personal Income", "Personal Spending",
    "GDP", "GDP Price Index", "Core Retail Sales",
]

# ============================================================
# 중요도 2(🟡) - 지수에 영향이 큰 것만 선별 포함
# ============================================================
SECONDARY_INDICATORS = [
    "GDP",  # GDP는 중요도 2도 포함
    "CPI", "Core CPI",
    "Retail Sales", "Industrial Production",
    "Consumer Confidence", "Michigan",
    "ISM", "PMI",
    "Existing Home Sales", "New Home Sales",
    "Durable Goods", "Factory Orders",
    "Jobless Claims",
    "Trade Balance",
    "Powell", "Lagarde", "Bailey", "Kuroda", "Ueda",
    "FOMC", "Fed",
    "BOJ", "BOE", "ECB", "PBOC",
    "Interest Rate",
    "Inflation",
    "Employment",
    "Manufacturing",
    "Services",
    "Housing",
    "Treasury",
    "Budget",
    "Current Account",
    "Import", "Export",
    "Personal Income", "Personal Spending",
    "Consumer Credit",
]

# ============================================================
# 중요도 2(🟡) 중에서도 제외할 저영향 지표
# ============================================================
LOW_IMPACT_KEYWORDS = [
    "CFTC", "Baker Hughes", "Rig Count",
    "Participation Rate", "U6 Unemployment",
    "speculative net positions",
    "10-Year Bond Auction", "30-Year Bond Auction",
    "5-Year Note Auction", "2-Year Note Auction",
    "3-Year Note Auction", "7-Year Note Auction",
    "20-Year Bond Auction",
    "TIPS Breakeven",
    "Dallas Fed", "Richmond Fed", "Kansas City Fed",
    "Chicago Fed", "Atlanta Fed", "San Francisco Fed",
    "NY Fed", "St. Louis Fed", "Cleveland Fed",
    "Speaks",  # 일반 인사 발언 (의장급 제외)
    "Treasury Secretary",
    "API Weekly", "EIA Weekly",
    "MBA Mortgage", "Mortgage",
    "Redbook", "Johnson Redbook",
    "ICSC", "Chain Store",
    "Bloomberg", "Commodity",
    "Wards", "Auto Sales",
    "Total Vehicle Sales",
    "Domestic Vehicle Sales",
    "4-Week Bill", "8-Week Bill", "13-Week Bill",
    "26-Week Bill", "52-Week Bill",
    "Holiday", "Market Holiday",
]

# 한국 주식 시장에 영향이 큰 주요 경제 지표 키워드 (레거시 호환)
KEY_INDICATORS = CORE_INDICATORS + SECONDARY_INDICATORS


def fetch_investing_calendar(
    days_back: int = 7,
    days_forward: int = 60,
    min_importance: int = 2,
) -> list[dict]:
    """
    Investing.com에서 경제 캘린더 데이터를 가져옵니다.
    
    Args:
        days_back: 과거 몇 일까지 포함할지
        days_forward: 미래 몇 일까지 포함할지
        min_importance: 최소 중요도 (1=낮음, 2=중간, 3=높음)
    
    Returns:
        [{"date": "2026-06-04", "title": "...", "type": "macro", "currency": "USD", "importance": 3}, ...]
    """
    if cloudscraper is None:
        print("[Investing] cloudscraper not installed, skipping")
        return []

    scraper = cloudscraper.create_scraper()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        resp = scraper.get(INVESTING_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[Investing] Failed to fetch page: {e}")
        return []

    # __NEXT_DATA__ 추출
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        print("[Investing] No __NEXT_DATA__ found")
        return []

    try:
        data = json.loads(match.group(1))
        state = data["props"]["pageProps"]["state"]
        cal_store = state["economicCalendarStore"]
        events_by_date = cal_store.get("calendarEventsByDate", {})
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[Investing] Failed to parse calendar data: {e}")
        return []

    # 날짜 범위 계산
    today = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    result = []
    for date_str, events in events_by_date.items():
        if date_str < start_date or date_str > end_date:
            continue

        for ev in events:
            importance = int(ev.get("importance", "0"))
            currency = ev.get("currency", "")
            event_name = ev.get("event", "")
            event_type = ev.get("type", "")

            # 중요도 필터
            if importance < min_importance:
                continue

            # 주요 통화만 포함 (USD, EUR, JPY, CNY 등)
            if currency not in MAJOR_CURRENCIES:
                continue

            # ============================================================
            # 중요도 기반 필터링 (정성적 판단)
            # ============================================================
            # 중요도 3(🔴): 핵심 지표는 CORE_INDICATORS에 매칭되면 무조건 포함
            # 중요도 2(🟡): SECONDARY_INDICATORS에 매칭되고 LOW_IMPACT_KEYWORDS에 해당하지 않으면 포함
            # 중요도 1(🟢): 기본적으로 제외 (min_importance=2)

            is_core = any(kw.lower() in event_name.lower() for kw in CORE_INDICATORS)
            is_secondary = any(kw.lower() in event_name.lower() for kw in SECONDARY_INDICATORS)
            is_low_impact = any(kw.lower() in event_name.lower() for kw in LOW_IMPACT_KEYWORDS)

            if importance == 3:
                # 중요도 3: CORE_INDICATORS에 매칭되거나 USD 주요 지표면 포함
                if not is_core and not is_secondary:
                    continue
            elif importance == 2:
                # 중요도 2: SECONDARY_INDICATORS에 매칭되어야 하며, LOW_IMPACT 제외
                if not is_secondary:
                    continue
                if is_low_impact:
                    continue
            else:
                continue

            title = f"[{currency}] {event_name}"
            if importance == 3:
                title = f"🔴 {title}"
            elif importance == 2:
                title = f"🟡 {title}"

            result.append({
                "date": date_str,
                "title": title,
                "type": "macro",
                "currency": currency,
                "importance": importance,
                "source": "investing.com",
            })

    print(f"[Investing] Collected {len(result)} events from {len(events_by_date)} dates")
    return result


# ============================================================
# 2. ForexFactory 크롤러 (백업)
# ============================================================

FOREX_FACTORY_URL = "https://www.forexfactory.com/calendar"

# 통화별 중요도 매핑 (주식 시장 영향도)
CURRENCY_IMPORTANCE = {
    "USD": 3,  # 미국 - 가장 중요
    "CNY": 3,  # 중국 - 한국 수출 영향
    "JPY": 2,  # 일본
    "EUR": 2,  # 유로존
    "GBP": 2,  # 영국
    "AUD": 1,  # 호주
    "CAD": 1,  # 캐나다
    "CHF": 1,  # 스위스
    "NZD": 1,  # 뉴질랜드
}


def fetch_forexfactory_calendar(
    days_back: int = 7,
    days_forward: int = 60,
    min_impact: int = 2,
) -> list[dict]:
    """
    ForexFactory에서 경제 캘린더 데이터를 가져옵니다.
    
    Args:
        days_back: 과거 몇 일까지 포함할지
        days_forward: 미래 몇 일까지 포함할지
        min_impact: 최소 impact (1~3, 별 개수)
    
    Returns:
        [{"date": "2026-06-04", "title": "...", "type": "macro", "currency": "USD", "importance": 3}, ...]
    """
    if cloudscraper is None:
        print("[ForexFactory] cloudscraper not installed, skipping")
        return []

    scraper = cloudscraper.create_scraper()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = scraper.get(FOREX_FACTORY_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[ForexFactory] Failed to fetch page: {e}")
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    rows = soup.select("tr.calendar__row")
    if not rows:
        print("[ForexFactory] No calendar rows found")
        return []

    today = datetime.now()
    start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    result = []
    current_date = None

    for row in rows:
        # 날짜 셀 확인 (date separator 역할)
        date_cell = row.select_one("td.calendar__date")
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            if date_text:
                # "SunMay 31" -> "May 31" -> 날짜 파싱
                date_text = date_text.replace("Sun", "").replace("Mon", "").replace("Tue", "").replace("Wed", "").replace("Thu", "").replace("Fri", "").replace("Sat", "")
                date_text = date_text.strip()
                try:
                    parsed = datetime.strptime(date_text, "%b %d")
                    current_date = parsed.replace(year=today.year).strftime("%Y-%m-%d")
                except ValueError:
                    continue

        if not current_date:
            continue

        if current_date < start_date or current_date > end_date:
            continue

        # 통화
        curr_cell = row.select_one("td.calendar__currency")
        currency = curr_cell.get_text(strip=True) if curr_cell else ""
        if currency not in CURRENCY_IMPORTANCE:
            continue

        # 이벤트명
        event_cell = row.select_one("td.calendar__event")
        event_name = event_cell.get_text(strip=True) if event_cell else ""

        # Impact (별 개수)
        impact_cell = row.select_one("td.calendar__impact")
        impact_spans = impact_cell.select('span[class*="impact"]') if impact_cell else []
        impact_count = len(impact_spans)

        if impact_count < min_impact:
            continue

        # 통화 중요도 가중치 적용
        currency_weight = CURRENCY_IMPORTANCE.get(currency, 1)
        final_importance = impact_count * currency_weight

        title = f"[{currency}] {event_name}"
        if final_importance >= 6:
            title = f"🔴 {title}"
        elif final_importance >= 4:
            title = f"🟡 {title}"

        result.append({
            "date": current_date,
            "title": title,
            "type": "macro",
            "currency": currency,
            "importance": final_importance,
            "source": "forexfactory.com",
        })

    print(f"[ForexFactory] Collected {len(result)} events")
    return result


# ============================================================
# 3. 통합 크롤러
# ============================================================

def fetch_global_events(
    days_back: int = 7,
    days_forward: int = 60,
    min_importance: int = 2,
    use_investing: bool = True,
    use_forexfactory: bool = True,
) -> list[dict]:
    """
    모든 소스에서 글로벌 경제 이벤트를 수집합니다.
    
    Args:
        days_back: 과거 몇 일까지 포함할지
        days_forward: 미래 몇 일까지 포함할지
        min_importance: 최소 중요도
        use_investing: Investing.com 사용 여부
        use_forexfactory: ForexFactory 사용 여부
    
    Returns:
        통합된 이벤트 리스트
    """
    all_events = []

    if use_investing:
        try:
            events = fetch_investing_calendar(days_back, days_forward, min_importance)
            all_events.extend(events)
        except Exception as e:
            print(f"[GlobalCrawler] Investing.com error: {e}")

    if use_forexfactory:
        try:
            events = fetch_forexfactory_calendar(days_back, days_forward, min_importance)
            all_events.extend(events)
        except Exception as e:
            print(f"[GlobalCrawler] ForexFactory error: {e}")

    # 중복 제거 (같은 날짜 + 같은 제목)
    seen = set()
    unique_events = []
    for ev in all_events:
        key = (ev["date"], ev["title"])
        if key not in seen:
            seen.add(key)
            unique_events.append(ev)

    # 날짜순 정렬
    unique_events.sort(key=lambda x: x["date"])
    return unique_events


# ============================================================
# 4. JSON 저장/로드
# ============================================================

def save_events_to_json(events: list[dict], filepath: str = None):
    """이벤트를 JSON 파일로 저장합니다."""
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), "global_events.json")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(events)} events to {filepath}")
    return filepath


def load_events_from_json(filepath: str = None) -> list[dict]:
    """JSON 파일에서 이벤트를 로드합니다."""
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), "global_events.json")
    
    if not os.path.exists(filepath):
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 5. 메인 실행
# ============================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("[Global Calendar Crawler]")
    print("=" * 60)
    
    # Investing.com 시도
    print("\n[1] Investing.com에서 데이터 수집 중...")
    investing_events = fetch_investing_calendar()
    
    if not investing_events:
        print("   -> Investing.com 실패, ForexFactory로 대체")
        events = fetch_forexfactory_calendar()
    else:
        events = investing_events
    
    if events:
        save_events_to_json(events)
        
        # 요약 출력
        print(f"\n[Result] 총 {len(events)}개 이벤트 수집됨")
        
        # 날짜별 통계
        from collections import Counter
        date_counts = Counter(ev["date"] for ev in events)
        print("\n[Date] 날짜별 이벤트 수:")
        for date, count in sorted(date_counts.items()):
            print(f"   {date}: {count}개")
        
        # 중요도별 통계
        imp_counts = Counter(ev["importance"] for ev in events)
        print(f"\n[Importance] 중요도별:")
        for imp, count in sorted(imp_counts.items(), reverse=True):
            print(f"   중요도 {imp}: {count}개")
    else:
        print("\n[Error] 데이터 수집 실패")
        print("   인터넷 연결을 확인하거나 나중에 다시 시도해주세요.")
        sys.exit(1)
