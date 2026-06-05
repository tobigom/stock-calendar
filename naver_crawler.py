"""
네이버 금융 페이지에서 주식 관련 일정을 크롤링하는 모듈

크롤링 소스:
1. IPO/공모주 일정: https://finance.naver.com/sise/ipo.naver
2. 네이버 금융 메인: https://finance.naver.com/

출력 형식: [{"date": "YYYY-MM-DD", "title": "...", "type": "korea"}, ...]
저장 파일: korea_events.json
"""

from __future__ import annotations
import requests
from bs4 import BeautifulSoup
import json
import re
import logging
from datetime import datetime, timedelta


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# 공모주 상장 예정일 계산
# ============================================================
# 일반적으로 청약일로부터 영업일 기준 약 14일 후 상장
# (청약 마감일 기준이지만, 여기서는 청약 시작일 기준으로 계산)

def _get_next_business_days(start_date: datetime, days: int) -> list[datetime]:
    """
    시작일로부터 영업일 기준 days일 후까지의 날짜 목록 반환
    
    Args:
        start_date: 시작일
        days: 영업일 수
    
    Returns:
        [datetime, ...] 영업일 날짜 목록
    """
    result = []
    current = start_date
    while len(result) < days:
        current += timedelta(days=1)
        # 월~금(0~4)만 영업일
        if current.weekday() < 5:
            result.append(current)
    return result


def _estimate_listing_date(subscribe_start: str) -> str:
    """
    청약 시작일로부터 상장 예정일 계산
    
    일반적인 공모주 일정:
    - 청약일(D-day): 수요예측 후 청약
    - 청약 마감(D+2~3): 2~3일간 청약
    - 납입일(D+5~7): 청약 마감 후 3~4영업일 후
    - 상장일(D+12~16): 납입일 후 약 7~10영업일 후
    → 청약 시작일 기준 약 14영업일 후
    
    Args:
        subscribe_start: 청약 시작일 (YYYY-MM-DD)
    
    Returns:
        상장 예정일 (YYYY-MM-DD)
    """
    try:
        start = datetime.strptime(subscribe_start, "%Y-%m-%d")
        # 청약 시작일로부터 14영업일 후
        business_days = _get_next_business_days(start, 14)
        if business_days:
            return business_days[-1].strftime("%Y-%m-%d")
    except Exception:
        pass
    return ""


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 연도 추론용 (YY 형식 날짜 보정)
CURRENT_YEAR = datetime.now().year
CURRENT_CENTURY = CURRENT_YEAR // 100


def _normalize_date(date_str: str) -> str:
    """
    다양한 날짜 형식을 YYYY-MM-DD로 통일

    지원 형식:
    - 26.06.08  → 2026-06-08
    - 2026-06-08 → 2026-06-08
    - 26.05.26~05.27 → 첫 번째 날짜 반환 (26.05.26 → 2026-05-26)
    """
    if not date_str:
        return ""

    # YYYY-MM-DD 형식
    m = re.search(r"(\d{4})[.-](\d{2})[.-](\d{2})", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # YY.MM.DD 형식 (앞 두 자리만 있는 경우)
    m = re.search(r"(\d{2})[.](\d{2})[.](\d{2})", date_str)
    if m:
        yy = int(m.group(1))
        full_year = CURRENT_CENTURY * 100 + yy
        return f"{full_year:04d}-{m.group(2)}-{m.group(3)}"

    # YY.MM.DD~MM.DD 형식 (범위의 첫 날짜)
    m = re.search(r"(\d{2})[.](\d{2})[.](\d{2})~(\d{2})[.](\d{2})", date_str)
    if m:
        yy = int(m.group(1))
        full_year = CURRENT_CENTURY * 100 + yy
        return f"{full_year:04d}-{m.group(2)}-{m.group(3)}"

    return ""


def _extract_stock_name(cell_text: str) -> str:
    """
    IPO 테이블 셀 텍스트에서 종목명 추출

    예: "종목코스닥피스피스스튜디오공모가21,500..." -> "피스피스스튜디오"
    """
    # "종목" 다음에 나오고 "공모가" 전까지의 텍스트
    m = re.search(r"종목\s*([^\d]+?)(?:공모가|\d)", cell_text)
    if m:
        name = m.group(1).strip()
    else:
        name = cell_text.split("공모가")[0].strip() if "공모가" in cell_text else cell_text[:30]

    # 시장구분 접두사 제거
    name = re.sub(r"^(코스피|코스닥|코넥스)\s*", "", name).strip()
    return name if name else cell_text[:15]


def fetch_ipo_schedule() -> list:
    """
    네이버 금융 IPO 페이지에서 공모주 일정을 크롤링
    - 청약일 + 상장일 모두 추출

    Returns:
        [{"date": "YYYY-MM-DD", "title": "공모주 청약: ...", "type": "ipo"}, ...]
        [{"date": "YYYY-MM-DD", "title": "공모주 상장: ...", "type": "ipo"}, ...]
    """
    events = []
    url = "https://finance.naver.com/sise/ipo.naver"

    try:
        logger.info(f"IPO 페이지 요청 중: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # 인코딩 처리 (EUC-KR)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        # IPO 테이블 찾기 (class="type_5" 또는 첫 번째 테이블)
        table = soup.find("table", class_="type_5")
        if not table:
            table = soup.find("table")
        if not table:
            logger.warning("IPO 페이지에서 테이블을 찾을 수 없습니다.")
            return events

        rows = table.find_all("tr")
        logger.info(f"IPO 테이블 행 수: {len(rows)}")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 1:
                continue

            cell_text = cells[0].get_text(strip=True)

            # 종목명 추출
            title = _extract_stock_name(cell_text)
            if not title or len(title) < 2:
                continue

            # ============================================================
            # [방법 1] 정규식으로 "상장", "청약" 키워드 기반 날짜 추출
            # ============================================================
            # 상장일 찾기: "상장 26.07.01" 또는 "상장일 26.07.01"
            listing_dates = re.findall(r"상장(?:일)?\s*(\d{2}\.\d{2}\.\d{2})", cell_text)
            # 청약일 찾기: "청약 26.06.24~06.25" 또는 "청약일 26.06.24"
            subscribe_dates = re.findall(
                r"청약(?:일)?\s*(\d{2}\.\d{2}\.\d{2}(?:~\d{2}\.\d{2})?)", cell_text
            )

            # ============================================================
            # [방법 2] HTML 구조 기반 파싱 (td 내부 span/a 태그 분석)
            # ============================================================
            if not listing_dates and not subscribe_dates:
                # td 내부의 모든 텍스트 노드를 분리하여 분석
                for child in cells[0].children:
                    child_text = child.get_text(strip=True) if hasattr(child, 'get_text') else ''
                    if not child_text:
                        continue
                    
                    # "상장 26.07.01" 패턴
                    ld = re.findall(r"상장(?:일)?\s*(\d{2}\.\d{2}\.\d{2})", child_text)
                    listing_dates.extend(ld)
                    
                    # "청약 26.06.24~06.25" 패턴
                    sd = re.findall(
                        r"청약(?:일)?\s*(\d{2}\.\d{2}\.\d{2}(?:~\d{2}\.\d{2})?)", child_text
                    )
                    subscribe_dates.extend(sd)

            # ============================================================
            # [방법 3] 전체 텍스트에서 모든 날짜 추출 후 청약/상장 컨텍스트 매핑
            # ============================================================
            if not listing_dates and not subscribe_dates:
                # "상장"이라는 단어 앞뒤로 날짜 찾기
                all_dates = re.findall(r"(\d{2}\.\d{2}\.\d{2})", cell_text)
                
                for i, d in enumerate(all_dates):
                    # 날짜 앞뒤 컨텍스트 확인
                    context_before = cell_text[:cell_text.find(d)][-20:]
                    context_after = cell_text[cell_text.find(d) + len(d):][:20]
                    
                    if "상장" in context_before or "상장" in context_after:
                        listing_dates.append(d)
                    elif "청약" in context_before or "청약" in context_after:
                        subscribe_dates.append(d)

            # ============================================================
            # 결과 저장
            # ============================================================
            # 상장일 이벤트
            for ld in listing_dates:
                normalized = _normalize_date(ld)
                if normalized:
                    events.append({
                        "date": normalized,
                        "title": f"공모주 상장: {title}",
                        "type": "ipo",
                    })
                    logger.info(f"  [상장] {normalized} - {title}")

            # 청약일 이벤트 (첫 날짜)
            for sd in subscribe_dates:
                normalized = _normalize_date(sd)
                if normalized:
                    events.append({
                        "date": normalized,
                        "title": f"공모주 청약: {title}",
                        "type": "ipo",
                    })
                    logger.info(f"  [청약] {normalized} - {title}")

            # 청약/상장 패턴이 모두 없으면 날짜 패턴에서 추론 (fallback)
            if not listing_dates and not subscribe_dates:
                date_patterns = re.findall(
                    r"(\d{2}\.\d{2}\.\d{2}(?:~\d{2}\.\d{2})?)", cell_text
                )
                for dp in date_patterns:
                    normalized = _normalize_date(dp)
                    if normalized:
                        events.append({
                            "date": normalized,
                            "title": f"IPO 일정: {title}",
                            "type": "ipo",
                        })

        logger.info(f"IPO 일정 {len(events)}건 수집 완료")

        # ============================================================
        # 청약일만 있고 상장일이 없는 종목 → 상장 예정일 자동 계산
        # ============================================================
        # 청약일 이벤트와 상장일 이벤트를 매핑하여 상장일이 누락된 종목 찾기
        subscribe_events = [e for e in events if "청약" in e["title"]]
        listing_events = [e for e in events if "상장" in e["title"]]
        
        # 이미 상장일이 있는 종목명 목록
        listed_stocks = set()
        for le in listing_events:
            # "공모주 상장: 종목명" 에서 종목명 추출
            stock_name = le["title"].replace("공모주 상장: ", "").strip()
            listed_stocks.add(stock_name)
        
        # 청약일만 있고 상장일이 없는 종목 → 상장 예정일 계산
        estimated_count = 0
        for se in subscribe_events:
            stock_name = se["title"].replace("공모주 청약: ", "").strip()
            if stock_name not in listed_stocks:
                # 상장 예정일 계산
                estimated_date = _estimate_listing_date(se["date"])
                if estimated_date:
                    events.append({
                        "date": estimated_date,
                        "title": f"공모주 상장(예상): {stock_name}",
                        "type": "ipo",
                    })
                    estimated_count += 1
                    logger.info(f"  [상장예상] {estimated_date} - {stock_name} (청약 {se['date']} 기준 14영업일 후)")
        
        if estimated_count > 0:
            logger.info(f"  → 상장 예정일 {estimated_count}건 자동 추가 완료")

    except requests.exceptions.RequestException as e:
        logger.error(f"IPO 페이지 요청 실패: {e}")
    except Exception as e:
        logger.error(f"IPO 페이지 파싱 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return events



def fetch_market_events() -> list:
    """
    네이버 금융 메인 페이지에서 주요 일정 정보를 크롤링
    (현재는 뉴스 헤드라인이 아닌 실제 일정성 데이터만 수집)

    Returns:
        [{"date": "YYYY-MM-DD", "title": "...", "type": "korea"}, ...]
    """
    events = []
    url = "https://finance.naver.com/"

    try:
        logger.info(f"네이버 금융 메인 페이지 요청 중: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        # '일정' 관련 섹션 찾기
        schedule_section = soup.find(string=re.compile("일정|캘린더|달력"))
        if schedule_section:
            parent = schedule_section.find_parent(["div", "section"])
            if parent:
                items = parent.find_all(["li", "tr", "div"])
                for item in items:
                    text = item.get_text(strip=True)
                    if len(text) > 5:
                        date_match = re.search(
                            r"(\d{1,2})[./](\d{1,2})", text
                        )
                        if date_match:
                            month, day = date_match.group(1), date_match.group(2)
                            date_str = f"{CURRENT_YEAR}-{int(month):02d}-{int(day):02d}"
                            events.append({
                                "date": date_str,
                                "title": text[:80],
                                "type": "korea",
                            })

        logger.info(f"네이버 금융 메인에서 {len(events)}건 수집 완료")

    except requests.exceptions.RequestException as e:
        logger.error(f"네이버 금융 메인 페이지 요청 실패: {e}")
    except Exception as e:
        logger.error(f"네이버 금융 메인 페이지 파싱 중 오류: {e}")

    return events


def save_to_json(events: list, filename: str = None) -> bool:
    """
    이벤트 리스트를 JSON 파일로 저장

    Args:
        events: 이벤트 리스트
        filename: 저장할 파일명 (기본값: C:\stock_calendar\korea_events.json)

    Returns:
        성공 여부
    """
    if filename is None:
        filename = r"C:\stock_calendar\korea_events.json"
    try:
        # 날짜순 정렬
        events.sort(key=lambda x: x["date"])

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ {filename} 저장 완료 (총 {len(events)}건)")
        return True

    except Exception as e:
        logger.error(f"JSON 파일 저장 실패: {e}")
        return False


def main():
    """메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("네이버 금융 크롤러 시작")
    logger.info("=" * 50)

    all_events = []

    # 1. IPO 일정 크롤링
    try:
        ipo_events = fetch_ipo_schedule()
        all_events.extend(ipo_events)
        logger.info(f"  → IPO 일정: {len(ipo_events)}건")
    except Exception as e:
        logger.error(f"IPO 크롤링 실패: {e}")

    # 2. 네이버 금융 메인 일정 크롤링
    try:
        market_events = fetch_market_events()
        all_events.extend(market_events)
        logger.info(f"  → 금융 메인 일정: {len(market_events)}건")
    except Exception as e:
        logger.error(f"금융 메인 크롤링 실패: {e}")

    # 3. 중복 제거 (동일 날짜 + 동일 제목)
    unique_events = []
    seen = set()
    for event in all_events:
        key = (event["date"], event["title"])
        if key not in seen:
            seen.add(key)
            unique_events.append(event)

    # 4. 저장
    if unique_events:
        save_to_json(unique_events)
    else:
        logger.warning("⚠️ 수집된 일정이 없습니다.")

    # 5. 결과 출력
    logger.info("-" * 50)
    logger.info(f"총 {len(unique_events)}건의 일정이 수집되었습니다.")
    for event in unique_events:
        logger.info(f"  [{event['date']}] [{event['type']}] {event['title']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
