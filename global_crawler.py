"""
글로벌 경제 캘린더 크롤러 (개선 버전)
- ForexFactory (메인): HTML 파싱으로 경제 캘린더 데이터 추출
- Investing.com (백업): FilterAjaxLoad API 직접 호출 + 대체 엔드포인트 시도
"""
from __future__ import annotations
import json
import re
import os
import time
from datetime import datetime, timedelta
from typing import Optional

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

try:
    import requests
except ImportError:
    requests = None

# ============================================================
# 1. Investing.com 크롤러 (백업)
# ============================================================

INVESTING_URL = "https://www.investing.com/economic-calendar/"
INVESTING_FILTER_URL = "https://www.investing.com/economic-calendar/FilterAjaxLoad"

# 중요도가 높은 주요 통화 목록
MAJOR_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF"}

# ============================================================
# 중요도 3(🔴) - 무조건 포함해야 할 핵심 지표
# ============================================================
CORE_INDICATORS = [
    "Nonfarm Payrolls", "Unemployment Rate", "CPI", "Core CPI",
    "PCE", "Core PCE", "GDP", "Interest Rate Decision",
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
    "GDP Price Index", "Core Retail Sales",
]

# ============================================================
# 중요도 2(🟡) - 지수에 영향이 큰 것만 선별 포함
# ============================================================
SECONDARY_INDICATORS = [
    "GDP", "CPI", "Core CPI",
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
    "Speaks",
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

KEY_INDICATORS = CORE_INDICATORS + SECONDARY_INDICATORS


def fetch_investing_calendar(
    days_back: int = 7,
    days_forward: int = 60,
    min_importance: int = 2,
) -> list[dict]:
    """
    Investing.com에서 경제 캘린더 데이터를 가져옵니다.
    FilterAjaxLoad API를 직접 호출하는 방식 (cloudscraper 사용)
    """
    if cloudscraper is None:
        print("[Investing] cloudscraper not installed, trying requests...")
        return _fetch_investing_with_requests(days_back, days_forward, min_importance)

    scraper = cloudscraper.create_scraper()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": INVESTING_URL,
        "Origin": "https://www.investing.com",
    }

    today = datetime.now()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    payload = {
        "country[]": ["5", "32", "37", "72"],  # US, CN, JP, KR
        "importance[]": ["2", "3"],
        "dateFrom": date_from,
        "dateTo": date_to,
        "timeZone": "18",  # KST
        "currentTab": "calendar",
        "limit": "200",
    }

    try:
        resp = scraper.post(
            INVESTING_FILTER_URL,
            data=payload,
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[Investing] FilterAjaxLoad returned status {resp.status_code}")
            return _fetch_investing_with_requests(days_back, days_forward, min_importance)

        # 응답이 HTML인지 JSON인지 확인
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type or resp.text.strip().startswith("{"):
            data = resp.json()
            rows = data.get("rows", data.get("data", data.get("events", [])))
            if isinstance(rows, str):
                # HTML 형태로 반환된 경우 파싱
                return _parse_investing_html(rows, min_importance)
            return _parse_investing_json(rows, min_importance)
        else:
            # HTML 응답 (Next.js 페이지)
            return _parse_investing_nextjs(resp.text, min_importance)

    except Exception as e:
        print(f"[Investing] Failed: {e}")
        return _fetch_investing_with_requests(days_back, days_forward, min_importance)


def _fetch_investing_with_requests(days_back, days_forward, min_importance):
    """requests 라이브러리로 Investing.com 시도"""
    if requests is None:
        print("[Investing] requests not installed, skipping")
        return []

    session = requests.Session()
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
        # 먼저 메인 페이지 방문 (쿠키 획득)
        resp = session.get(INVESTING_URL, headers=headers, timeout=30)
        resp.raise_for_status()

        # __NEXT_DATA__ 추출 시도
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL
        )
        if match:
            try:
                data = json.loads(match.group(1))
                state = data["props"]["pageProps"]["state"]
                cal_store = state["economicCalendarStore"]
                events_by_date = cal_store.get("calendarEventsByDate", {})
                return _parse_nextjs_events(events_by_date, min_importance)
            except (KeyError, json.JSONDecodeError) as e:
                print(f"[Investing] __NEXT_DATA__ parse failed: {e}")

        # FilterAjaxLoad 시도
        today = datetime.now()
        date_from = today.strftime("%Y-%m-%d")
        date_to = (today + timedelta(days=days_forward)).strftime("%Y-%m-%d")

        ajax_headers = {
            **headers,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": INVESTING_URL,
            "Origin": "https://www.investing.com",
        }
        payload = {
            "country[]": ["5", "32", "37", "72"],
            "importance[]": ["2", "3"],
            "dateFrom": date_from,
            "dateTo": date_to,
            "timeZone": "18",
            "currentTab": "calendar",
            "limit": "200",
        }
        resp2 = session.post(
            INVESTING_FILTER_URL, data=payload, headers=ajax_headers, timeout=30
        )
        if resp2.status_code == 200:
            if resp2.text.strip().startswith("{"):
                data = resp2.json()
                rows = data.get("rows", data.get("data", data.get("events", [])))
                if isinstance(rows, str):
                    return _parse_investing_html(rows, min_importance)
                return _parse_investing_json(rows, min_importance)

        print(f"[Investing] All methods failed (last status: {resp2.status_code})")
        return []

    except Exception as e:
        print(f"[Investing] requests method failed: {e}")
        return []


def _parse_nextjs_events(events_by_date, min_importance):
    """__NEXT_DATA__에서 추출한 이벤트 파싱"""
    result = []
    for date_str, events in events_by_date.items():
        for ev in events:
            importance = int(ev.get("importance", "0"))
            currency = ev.get("currency", "")
            event_name = ev.get("event", "")

            if importance < min_importance:
                continue
            if currency not in MAJOR_CURRENCIES:
                continue

            is_core = any(kw.lower() in event_name.lower() for kw in CORE_INDICATORS)
            is_secondary = any(kw.lower() in event_name.lower() for kw in SECONDARY_INDICATORS)
            is_low_impact = any(kw.lower() in event_name.lower() for kw in LOW_IMPACT_KEYWORDS)

            if importance == 3:
                if not is_core and not is_secondary:
                    continue
            elif importance == 2:
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

    print(f"[Investing] Collected {len(result)} events from __NEXT_DATA__")
    return result


def _parse_investing_json(rows, min_importance):
    """FilterAjaxLoad JSON 응답 파싱"""
    result = []
    for row in rows:
        if isinstance(row, dict):
            importance = int(row.get("importance", row.get("importance_level", "0")))
            currency = row.get("currency", row.get("country", ""))
            event_name = row.get("event", row.get("title", ""))
            date_str = row.get("date", row.get("start_date", ""))

            if not date_str:
                continue
            # 날짜 형식 정규화
            date_str = date_str[:10] if len(date_str) >= 10 else date_str

            if importance < min_importance:
                continue
            if currency not in MAJOR_CURRENCIES:
                continue

            is_core = any(kw.lower() in event_name.lower() for kw in CORE_INDICATORS)
            is_secondary = any(kw.lower() in event_name.lower() for kw in SECONDARY_INDICATORS)
            is_low_impact = any(kw.lower() in event_name.lower() for kw in LOW_IMPACT_KEYWORDS)

            if importance == 3:
                if not is_core and not is_secondary:
                    continue
            elif importance == 2:
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

    print(f"[Investing] Collected {len(result)} events from FilterAjaxLoad JSON")
    return result


def _parse_investing_html(html_text, min_importance):
    """FilterAjaxLoad HTML 응답 파싱"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[Investing] BeautifulSoup not installed, skipping HTML parse")
        return []

    result = []
    soup = BeautifulSoup(html_text, "lxml")
    rows = soup.select("tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 5:
            continue

        # 날짜
        date_cell = row.select_one("td.time, td.date, td.first")
        date_str = ""
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            m = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
            if m:
                date_str = m.group(1)

        if not date_str:
            continue

        # 통화
        curr_cell = row.select_one("td.flagCur, td.currency, td.left.flagCur")
        currency = ""
        if curr_cell:
            currency = curr_cell.get_text(strip=True).upper()

        if currency not in MAJOR_CURRENCIES:
            continue

        # 이벤트명
        event_cell = row.select_one("td.event, td.left.event")
        event_name = event_cell.get_text(strip=True) if event_cell else ""

        # 중요도 (별/불 표시)
        imp_cell = row.select_one("td.sentiment, td.importance, td.left.imp")
        importance = 2  # 기본값
        if imp_cell:
            bulls = imp_cell.select("i.bull, span.bold, .greenIcon")
            importance = len(bulls)

        if importance < min_importance:
            continue

        is_core = any(kw.lower() in event_name.lower() for kw in CORE_INDICATORS)
        is_secondary = any(kw.lower() in event_name.lower() for kw in SECONDARY_INDICATORS)
        is_low_impact = any(kw.lower() in event_name.lower() for kw in LOW_IMPACT_KEYWORDS)

        if importance == 3:
            if not is_core and not is_secondary:
                continue
        elif importance == 2:
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

    print(f"[Investing] Collected {len(result)} events from HTML parse")
    return result


# ============================================================
# 2. ForexFactory 크롤러 (메인)
# ============================================================

FOREX_FACTORY_URL = "https://www.forexfactory.com/calendar"

CURRENCY_IMPORTANCE = {
    "USD": 3,
    "CNY": 3,
    "JPY": 2,
    "EUR": 2,
    "GBP": 2,
    "AUD": 1,
    "CAD": 1,
    "CHF": 1,
    "NZD": 1,
    "All": 2,  # OPEC, G7 등 다국가 이벤트
}


def fetch_forexfactory_calendar(
    days_back: int = 7,
    days_forward: int = 60,
    min_impact: int = 2,
) -> list[dict]:
    """
    ForexFactory에서 경제 캘린더 데이터를 가져옵니다.
    cloudscraper + BeautifulSoup 사용 (Cloudflare 우회)
    """
    if cloudscraper is None:
        print("[ForexFactory] cloudscraper not installed, trying requests...")
        return _fetch_forexfactory_requests(days_back, days_forward, min_impact)

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
        resp = scraper.get(FOREX_FACTORY_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[ForexFactory] Failed with cloudscraper: {e}")
        return _fetch_forexfactory_requests(days_back, days_forward, min_impact)

    return _parse_forexfactory_html(html, days_back, days_forward, min_impact)


def _fetch_forexfactory_requests(days_back, days_forward, min_impact):
    """requests로 ForexFactory 시도 (백업)"""
    if requests is None:
        print("[ForexFactory] requests not installed, skipping")
        return []

    session = requests.Session()
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
        resp = session.get(FOREX_FACTORY_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[ForexFactory] Failed with requests: {e}")
        return []

    return _parse_forexfactory_html(html, days_back, days_forward, min_impact)


def _parse_forexfactory_html(html, days_back, days_forward, min_impact):
    """ForexFactory HTML 파싱"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[ForexFactory] BeautifulSoup not installed, skipping")
        return []

    soup = BeautifulSoup(html, "lxml")

    today = datetime.now()
    start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    # ForexFactory impact level mapping (class name -> importance)
    IMPACT_MAP = {
        "icon--ff-impact-ora": 3,  # Orange = High impact
        "icon--ff-impact-yel": 2,  # Yellow = Medium impact
        "icon--ff-impact-gra": 1,  # Gray = Low impact
    }

    result = []
    current_date = None

    # ForexFactory HTML 구조: 각 행은 <tr class="calendar__row">
    rows = soup.select("tr.calendar__row")
    if not rows:
        rows = soup.select("tr[data-event-id]")
    if not rows:
        rows = soup.select("table.calendar__table tr")

    if not rows:
        print("[ForexFactory] No rows found with any selector")
        return []

    for row in rows:
        # 날짜 셀 확인 (date separator rows have date, regular rows don't)
        date_cell = row.select_one("td.calendar__date")
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            if date_text:
                # "SunJun 7" -> "Jun 7"
                date_text = re.sub(r"(Sun|Mon|Tue|Wed|Thu|Fri|Sat)", "", date_text).strip()
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
        currency = curr_cell.get_text(strip=True).upper() if curr_cell else ""
        if currency not in CURRENCY_IMPORTANCE:
            continue

        # 이벤트명
        event_cell = row.select_one("td.calendar__event")
        event_name = event_cell.get_text(strip=True) if event_cell else ""
        if not event_name:
            continue

        # Impact: class name으로 중요도 판별
        impact_cell = row.select_one("td.calendar__impact")
        impact_count = 0
        if impact_cell:
            impact_span = impact_cell.select_one("span.icon--ff-impact-ora, span.icon--ff-impact-yel, span.icon--ff-impact-gra")
            if impact_span:
                for cls in impact_span.get("class", []):
                    if cls in IMPACT_MAP:
                        impact_count = IMPACT_MAP[cls]
                        break

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
    """
    all_events = []

    # ForexFactory 먼저 시도 (더 안정적)
    if use_forexfactory:
        try:
            events = fetch_forexfactory_calendar(days_back, days_forward, min_importance)
            all_events.extend(events)
        except Exception as e:
            print(f"[GlobalCrawler] ForexFactory error: {e}")

    # Investing.com 백업
    if use_investing:
        try:
            events = fetch_investing_calendar(days_back, days_forward, min_importance)
            all_events.extend(events)
        except Exception as e:
            print(f"[GlobalCrawler] Investing.com error: {e}")

    # 중복 제거
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
    print("[Global Calendar Crawler - 개선 버전]")
    print("=" * 60)

    # ForexFactory 먼저 시도
    print("\n[1] ForexFactory에서 데이터 수집 중...")
    events = fetch_forexfactory_calendar()

    if not events:
        print("   -> ForexFactory 실패, Investing.com 시도")
        events = fetch_investing_calendar()

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
