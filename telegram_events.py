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
# ※ 채널에 가입되어 있지 않아도 public 채널 메시지는 읽을 수 있음
# ※ 단, private/초대 전용 채널은 접근 불가
# ============================================================
TARGET_CHANNELS = [
    "value_investing_lab",
    "giant_mkt",
    # 필요시 추가
]

# ============================================================
# [설정] 필터 키워드 (메시지에 이 단어가 포함되면 수집)
# ============================================================
KEYWORDS = [
    # 한글 키워드
    "일정", "스케줄", "공모주", "CPI", "실적", "배당", "IPO", "청약",
    "상장", "상장예정", "기업공개", "액면분할", "감자", "증자",
    "유상증자", "전환사채", "CB", "BW", "신주인수권", "워런트",
    "스플릿", "합병", "분할", "상폐", "관리종목", "지정예탁",
    "공시", "DART", "반기보고", "사업보고", "분기보고",
    "어닝", "어닝서프라이즈", "어닝쇼크", "가이던스",
    "목표주가", "투자의견", "매수", "매도", "트레이딩",
    "배당락", "배당기준일", "배당금", "중간배당",
    "주주총회", "주총", "임시주총",
    "스페이스X", "테슬라", "엔비디아", "애플", "마이크로소프트",
    "메타", "아마존", "구글", "알파벳", "TSMC",
    "FOMC", "금리", "기준금리", "인상", "인하", "동결",
    "고용", "실업률", "비농업", "고용보고서",
    "GDP", "소비자물가", "생산자물가", "PCE", "근원",
    "무역", "관세", "수출", "수입",
    # 영문 키워드
    "earnings", "dividend", "ex-dividend", "record date",
    "stock split", "reverse split", "merger", "acquisition",
    "buyback", "share repurchase", "tender offer",
    "rights offering", "convertible", "warrant",
    "delisting", "bankruptcy", "restructuring",
    "spacex", "ipo", "listing", "offering",
    "fomc", "fed", "interest rate", "cpi", "ppi", "pce",
    "nonfarm", "unemployment", "gdp", "trade deficit",
    "tariff", "sanction",
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
    """
    # YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # MM월 DD일 (같은 해)
    m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if m:
        now = datetime.now()
        month, day = int(m.group(1)), int(m.group(2))
        return f"{now.year:04d}-{month:02d}-{day:02d}"

    # MM/DD (같은 해, 미국식)
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            now = datetime.now()
            return f"{now.year:04d}-{month:02d}-{day:02d}"

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
    """메시지에 필터 키워드가 포함되어 있는지 확인"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


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
                    entity, limit=500, offset_date=datetime.now(timezone.utc)
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
    print("  텔레그램 주식 일정 수집기")
    print("=" * 55)
    print(f"  대상 채널: {', '.join(TARGET_CHANNELS)}")
    print(f"  필터 키워드: {len(KEYWORDS)}개")
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

    # 결과 출력
    print()
    print("-" * 55)
    print(f"  총 {len(events)}건의 일정이 수집되었습니다.")
    for ev in events:
        print(f"    [{ev['date']}] {ev['title']}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
