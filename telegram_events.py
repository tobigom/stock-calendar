"""
텔레그램 주식 채널에서 일정 메시지 수집기 (Telethon 기반) - 개선 버전

변경 사항:
1. 세션 파일 없어도 로그인 시도 (자동 로그인)
2. FloodWait 발생 시 자동 대기 후 재시도 (최대 60초)
3. 채널 접근 불가 시 상세 에러 메시지
4. 키워드 대폭 확장
5. 메시지 수집 범위 48시간으로 확장
6. 채널별 메시지 수 제한 증가 (200 -> 500)
"""
import re
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    UsernameNotOccupiedError,
    PeerIdInvalidError,
)

# ============================================================
# [설정] 텔레그램 API 인증 정보
# ============================================================
API_ID = 26220720
API_HASH = "778b9252849089d2b872061e9044e9ed"

# ============================================================
# [설정] 텔레그램 로그인 전화번호
# ============================================================
PHONE_NUMBER = "821087555301"

# ============================================================
# [설정] 수집 대상 텔레그램 채널 (public username)
# ※ 국내 지수/테마/섹터에 직접 영향을 주는 채널만 선별
# ※ 해외 주식 채널은 ForexFactory에서 이미 수집 중이므로 제외
# ============================================================
TARGET_CHANNELS = [
    # ★ 국내 지수/테마/섹터 핵심 채널 (엄선)
    "realtime_stock_news",      # 실시간 주식 뉴스 (37,211명) - 국내 속보
    "stock_messenger",          # 주식 텔레그램 (25,508명) - 국내 종합
    "moneythemestock",          # 머니테마 주식 (18,372명) - 테마/섹터
    "stock_news",               # Stock News (10,048명) - 국내 뉴스
]


# ============================================================
# [설정] 필터 키워드 (국내 지수/테마/섹터에 직접 영향 주는 키워드만 엄선)
# ============================================================
KEYWORDS = [
    # ============================================================
    # ★ 1순위: 국내 지수 직접 영향 (코스피/코스닥 변동 요인)
    # ============================================================
    "코스피", "코스닥", "코스피200", "프로그램 매매", "프로그램매매",
    "외인", "외국인", "기관", "개인", "개미",
    "선물", "옵션", "만기일", "선물옵션", "옵션만기", "선물만기",
    "지수", "지수선물", "지수옵션",
    "변동성", "VIX", "공포", "투심",

    # ============================================================
    # ★ 2순위: 주요 테마/섹터 (국내 주도주)
    # ============================================================
    "반도체", "AI", "인공지능", "로봇", "로보틱스",
    "2차전지", "이차전지", "배터리", "전기차",
    "바이오", "제약", "헬스케어",
    "조선", "방산", "국방",
    "원전", "SMR", "원자력", "에너지",
    "우주", "항공", "드론",
    "엔터", "게임", "웹툰",
    "플랫폼", "클라우드", "소프트웨어",
    "건설", "인프라", "부동산",
    "금융", "은행", "증권", "보험",
    "화학", "정유", "철강", "자동차",

    # ============================================================
    # ★ 3순위: 기업 이벤트 (공시/실적/배당/자본변동)
    # ============================================================
    "공모주", "IPO", "청약", "상장", "상장예정", "기업공개",
    "실적", "어닝", "어닝서프라이즈", "어닝쇼크", "가이던스",
    "배당", "배당락", "배당기준일", "배당금", "중간배당",
    "액면분할", "감자", "증자", "유상증자",
    "전환사채", "CB", "BW", "신주인수권", "워런트",
    "합병", "분할", "스플릿", "상폐", "관리종목",
    "공시", "DART", "반기보고", "사업보고", "분기보고",
    "주주총회", "주총", "임시주총",
    "자사주", "취득", "소각", "매입",

    # ============================================================
    # ★ 4순위: 매크로 (국내 금리/통화정책)
    # ============================================================
    "금리", "기준금리", "한은", "한국은행",
    "FOMC", "연준", "파월", "빅컷", "인상", "인하", "동결",
    "CPI", "소비자물가", "생산자물가", "PCE",
    "GDP", "고용", "실업률", "비농업",
    "관세", "무역", "환율", "원달러", "원/달러",

    # ============================================================
    # ★ 5순위: 해외 주요 종목 (국내 지수에 영향 주는 종목만)
    # ============================================================
    "엔비디아", "NVDA", "테슬라", "TSLA", "애플", "AAPL",
    "마이크로소프트", "MSFT", "메타", "META", "아마존", "AMZN",
    "구글", "알파벳", "GOOGL", "TSMC",
]

# ============================================================
# [설정] 제외 패턴 (이 패턴이 포함된 메시지는 수집하지 않음)
# ============================================================
EXCLUDE_PATTERNS = [
    # 개별 종목 추천/분석 (지수/테마 영향 없는 일상적 종목 분석)
    r"삼성전자\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"SK하이닉스\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"셀트리온\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"LG에너지솔루션\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"삼성바이오로직스\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"현대차\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"기아\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"POSCO\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"NAVER\s*(52주|신고가|신저가|목표가|매수|매도)",
    r"카카오\s*(52주|신고가|신저가|목표가|매수|매도)",

    # 일상적 거래량/시세 정보 (지수 영향 없음)
    r"거래량\s*급증", r"급등\s*주", r"급락\s*주",
    r"상한가", r"하한가", r"상승\s*종목", r"하락\s*종목",
    r"개별\s*종목\s*추천", r"종목\s*분석",

    # 광고/홍보성 메시지
    r"수익\s*인증", r"수익률\s*인증", r"무료\s*수업", r"무료\s*강의",
    r"오픈\s*채팅", r"초대\s*합니다", r"모집\s*합니다",
    r"선물\s*이벤트", r"이벤트\s*참여",

    # 해외 주식 개별 종목 뉴스 (ForexFactory에서 이미 수집)
    r"애플\s*(신고가|신저가|목표가|실적)",
    r"마이크로소프트\s*(신고가|신저가|목표가|실적)",
    r"아마존\s*(신고가|신저가|목표가|실적)",
    r"메타\s*(신고가|신저가|목표가|실적)",
    r"구글\s*(신고가|신저가|목표가|실적)",
    r"테슬라\s*(신고가|신저가|목표가|실적)",
    r"엔비디아\s*(신고가|신저가|목표가|실적)",
]


# ============================================================
# [설정] 저장 파일 경로
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(BASE_DIR, "telegram_events.json")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def extract_date_from_text(text: str):
    """
    메시지 본문에서 YYYY-MM-DD 형식의 날짜를 추출합니다.
    - "2026-06-12", "2026.06.12", "2026/06/12" 형식 우선
    - "6월 12일", "6월12일" 형식 (연도 없으면 현재 연도)
    - "6/12" 미국식 형식
    - "12일"만 있는 경우 (이번달로 간주)
    - "내일", "모레" 같은 상대적 날짜
    """
    # YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # MM월 DD일 (같은 해) - "6월 12일", "6월12일"
    m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if m:
        now = datetime.now()
        month, day = int(m.group(1)), int(m.group(2))
        # 월이 현재 월보다 작으면 다음 해로 간주 (ex: 12월에 "1월" 언급)
        if month < now.month:
            year = now.year + 1
        else:
            year = now.year
        return f"{year:04d}-{month:02d}-{day:02d}"

    # MM/DD (같은 해, 미국식) - 단, 날짜 범위 내에서만
    m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            now = datetime.now()
            # 월이 현재 월보다 작으면 다음 해
            if month < now.month:
                year = now.year + 1
            else:
                year = now.year
            return f"{year:04d}-{month:02d}-{day:02d}"

    # "DD일"만 있는 경우 (이번달로 간주, 단 1~31 범위)
    m = re.search(r"(?<!\d)(\d{1,2})일(?!\d)", text)
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            now = datetime.now()
            # 오늘보다 이전 날짜면 다음달로 간주
            if day < now.day:
                next_month = now.month + 1
                year = now.year
                if next_month > 12:
                    next_month = 1
                    year += 1
                return f"{year:04d}-{next_month:02d}-{day:02d}"
            else:
                return f"{now.year:04d}-{now.month:02d}-{day:02d}"

    # "내일", "모레" 같은 상대적 날짜
    now = datetime.now()
    if "내일" in text or "다음날" in text:
        tomorrow = now + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    if "모레" in text:
        day_after = now + timedelta(days=2)
        return day_after.strftime("%Y-%m-%d")
    if "이번주" in text or "금주" in text:
        # 이번주 금요일 찾기
        days_ahead = 4 - now.weekday()  # 금요일=4
        if days_ahead <= 0:
            days_ahead += 7
        friday = now + timedelta(days=days_ahead)
        return friday.strftime("%Y-%m-%d")
    if "다음주" in text:
        # 다음주 월요일
        days_ahead = 7 - now.weekday()
        next_monday = now + timedelta(days=days_ahead)
        return next_monday.strftime("%Y-%m-%d")

    return None


def extract_title(text: str, max_len: int = 80) -> str:
    """메시지 본문에서 일정 관련 제목을 추출합니다."""
    # 첫 줄 추출
    first_line = text.split("\n")[0].strip()
    if len(first_line) > 5:
        title = first_line
    else:
        title = text.strip()

    # 키워드 기준으로 앞뒤 문맥 추출
    for kw in KEYWORDS:
        if kw in text:
            idx = text.index(kw)
            start = max(0, idx - 20)
            end = min(len(text), idx + len(kw) + 40)
            context = text[start:end].strip()
            if len(context) < len(title):
                title = context

    # 80자 제한
    if len(title) > max_len:
        title = title[: max_len - 3] + "..."

    return title


def is_relevant_message(text: str) -> bool:
    """
    3단계 스마트 필터링:
    1단계: 제외 패턴(EXCLUDE_PATTERNS) 검사 - 매치되면 즉시 False
    2단계: 키워드(KEYWORDS) 포함 검사
    3단계: 최소 길이 검사 (너무 짧은 메시지 제외)
    """
    if not text:
        return False

    text_stripped = text.strip()
    
    # 1단계: 제외 패턴 검사 (정규식)
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, text_stripped):
            return False

    # 2단계: 키워드 포함 검사
    text_lower = text_stripped.lower()
    found_kw = False
    for kw in KEYWORDS:
        if kw.lower() in text_lower:
            found_kw = True
            break
    
    if not found_kw:
        return False

    # 3단계: 최소 길이 검사 (10자 미만은 잡음으로 간주)
    if len(text_stripped) < 10:
        return False

    return True



async def collect_telegram_events() -> list:
    """
    Telethon 클라이언트로 타겟 채널에서 이벤트 메시지 수집

    Returns:
        [{"date": "YYYY-MM-DD", "title": "...", "type": "telegram"}, ...]
    """
    events = []
    session_file = os.path.join(BASE_DIR, "telegram_session")

    # Telethon 클라이언트 생성
    client = TelegramClient(session_file, API_ID, API_HASH)

    try:
        # 세션 파일이 없어도 로그인 시도 (자동 로그인)
        session_file_path = session_file + ".session"
        if not os.path.exists(session_file_path):
            logger.warning("[WARN] 텔레그램 세션 파일이 없습니다. 로그인을 시도합니다...")
            logger.warning("  (최초 로그인은 telegram_login.py를 먼저 실행해주세요)")
            # 세션 없이도 로그인 시도 (전화번호 인증 필요 시 실패)
            try:
                await client.start(phone=PHONE_NUMBER)
                logger.info("[OK] 텔레그램 로그인 성공!")
            except Exception as login_err:
                logger.warning(f"[WARN] 자동 로그인 실패: {login_err}")
                logger.warning("  -> python telegram_login.py 를 먼저 실행해주세요.")
                logger.warning("  -> 텔레그램 수집을 건너<skip>니다.")
                return []
        else:
            # 세션 파일이 있으면 정상 로그인
            if PHONE_NUMBER:
                await client.start(phone=PHONE_NUMBER)
            else:
                await client.start()
            logger.info("[OK] 텔레그램 로그인 성공!")

        # 현재 시간 기준 48시간 전 (주말 대비 확장)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)

        for channel_username in TARGET_CHANNELS:
            try:
                logger.info(f"[채널 접속 중] @{channel_username}")
                entity = await client.get_entity(channel_username)
                channel_title = getattr(entity, "title", channel_username)
                participants = getattr(entity, "participants_count", "?")
                logger.info(f"  -> '{channel_title}' (멤버: {participants})")

                # 최근 메시지 순회 (최대 500개)
                msg_count = 0
                async for message in client.iter_messages(
                    entity, limit=500
                ):
                    # 48시간 이전 메시지는 스킵
                    if message.date.replace(tzinfo=timezone.utc) < cutoff_time:
                        break

                    msg_text = message.text or message.message or ""
                    if not msg_text:
                        continue

                    # 키워드 필터
                    if not is_relevant_message(msg_text):
                        continue

                    # 날짜 추출 (메시지 본문 우선, 없으면 메시지 작성일)
                    event_date = extract_date_from_text(msg_text)
                    if not event_date:
                        # 메시지 작성일 기준 (UTC -> KST)
                        msg_dt = message.date.replace(tzinfo=timezone.utc).astimezone()
                        event_date = msg_dt.strftime("%Y-%m-%d")

                    # 제목 추출
                    title = extract_title(msg_text)

                    events.append({
                        "date": event_date,
                        "title": title,
                        "type": "telegram",
                    })
                    msg_count += 1

                logger.info(f"  -> @{channel_username} ({channel_title}): {msg_count}건 수집")

            except ChannelPrivateError:
                logger.warning(f"  [SKIP] @{channel_username}: 비공개 채널이거나 접근 권한이 없습니다.")
                continue
            except UsernameNotOccupiedError:
                logger.warning(f"  [SKIP] @{channel_username}: 존재하지 않는 채널입니다.")
                continue
            except PeerIdInvalidError:
                logger.warning(f"  [SKIP] @{channel_username}: 유효하지 않은 채널 ID입니다.")
                continue
            except FloodWaitError as e:
                wait_seconds = e.seconds
                logger.warning(f"  [FLOOD] @{channel_username}: FloodWait {wait_seconds}초")
                if wait_seconds <= 60:
                    logger.info(f"     {wait_seconds}초 대기 후 다음 채널로 이동...")
                    await asyncio.sleep(wait_seconds)
                    continue
                else:
                    logger.warning(f"     대기 시간이 너무 김({wait_seconds}초). 채널 스킵.")
                    continue
            except Exception as e:
                logger.warning(f"  [ERROR] @{channel_username} 처리 중 오류: {e}")
                continue

    except FloodWaitError as e:
        wait_seconds = e.seconds
        logger.warning(f"[FLOOD] 텔레그램 FloodWait: {wait_seconds}초 대기 필요")
        if wait_seconds <= 60:
            logger.info(f"  {wait_seconds}초 대기 후 재시도...")
            await asyncio.sleep(wait_seconds)
            return await collect_telegram_events()
        else:
            logger.warning(f"  대기 시간 너무 김({wait_seconds}초). 건너<skip>니다.")
            return []

    except Exception as e:
        logger.error(f"[ERROR] 텔레그램 클라이언트 오류: {e}")
        logger.warning("  -> 텔레그램 수집을 건너<skip>니다.")
        return []

    finally:
        await client.disconnect()
        logger.info("[연결 종료]")

    return events


def save_events(events: list):
    """수집된 이벤트를 JSON 파일로 저장"""
    # 날짜순 정렬
    events.sort(key=lambda x: x["date"])

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    logger.info(f"[OK] {OUTPUT_JSON} 저장 완료 (총 {len(events)}건)")


def main():
    """메인 실행 함수"""
    print()
    print("=" * 55)
    print("  텔레그램 주식 일정 수집기 (스마트 필터링)")
    print("=" * 55)
    print(f"  대상 채널: {', '.join(TARGET_CHANNELS)}")
    print(f"  필터 키워드: {len(KEYWORDS)}개 (국내 지수/테마/섹터 중심)")
    print(f"  제외 패턴: {len(EXCLUDE_PATTERNS)}개 (잡음/광고/개별종목 제거)")
    print(f"  수집 범위: 최근 48시간")
    print("=" * 55)
    print()


    # 비동기 수집 실행
    events = asyncio.run(collect_telegram_events())

    # 저장
    if events:
        save_events(events)
    else:
        logger.warning("[WARN] 수집된 일정이 없습니다.")
        # 빈 배열이라도 저장 (파일 없음 방지)
        save_events([])

    # 결과 출력 (로깅으로만 처리, cp949 인코딩 문제 회피)
    logger.info(f"총 {len(events)}건의 일정이 수집되었습니다.")
    for ev in events:
        logger.info(f"  [{ev['date']}] {ev['title']}")


if __name__ == "__main__":
    main()
