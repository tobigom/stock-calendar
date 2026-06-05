"""
텔레그램 주식 채널에서 일정 메시지 수집기 (Telethon 기반)

- 타겟 public 채널에서 최근 24시간 메시지 수집
- [일정], [스케줄], [공모주], [CPI], [실적] 등 키워드 필터링
- 메시지에서 날짜(YYYY-MM-DD) 추출 또는 메시지 작성일 기준
- 결과를 telegram_events.json으로 저장

사용 방법:
    1. pip install telethon
    2. 아래 API_ID, API_HASH 확인 (이미 입력됨)
    3. TARGET_CHANNELS에 수집할 채널 유저네임 추가
    4. python telegram_events.py 실행
"""
import re
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import FloodWaitError

# ============================================================
# [설정] 텔레그램 API 인증 정보
# ============================================================
API_ID = 26220720
API_HASH = "778b9252849089d2b872061e9044e9ed"

# ============================================================
# [설정] 텔레그램 로그인 전화번호 (최초 1회 입력 후 세션 저장)
# - 예: PHONE_NUMBER = "821012345678"  (국가코드 82 + 01012345678)
# - 최초 실행 후 세션 파일(telegram_session)이 생성되면 자동 로그인
# - 세션 파일 삭제 시 다시 전화번호 입력 필요
# ============================================================
PHONE_NUMBER = "821087555301"  # 여기에 전화번호를 입력하세요 (예: "821012345678")


# ============================================================
# [설정] 수집 대상 텔레그램 채널 (public username)
# ============================================================
TARGET_CHANNELS = [
    "value_investing_lab",
    "giant_mkt",
    # 필요시 추가: "another_channel",
]

# ============================================================
# [설정] 필터 키워드 (메시지에 이 단어가 포함되면 수집)
# ============================================================
KEYWORDS = ["일정", "스케줄", "공모주", "CPI", "실적", "배당", "IPO", "청약"]

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

    지원 패턴:
    - 2026-06-08
    - 2026.06.08
    - 2026/06/08
    - 06월 08일 (같은 해 기준)
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

    return None


def extract_title(text: str, max_len: int = 80) -> str:
    """
    메시지 본문에서 일정 관련 제목을 추출합니다.
    - 첫 줄 또는 키워드 앞뒤 문맥을 우선 사용
    - 너무 길면 max_len으로 자름
    """
    # 첫 줄 추출
    first_line = text.split("\n")[0].strip()
    if len(first_line) > 5:
        title = first_line
    else:
        title = text.strip()

    # 키워드 기준으로 앞뒤 문맥 추출 (더 짧고 의미있는 제목)
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
        # 세션 파일이 없으면 스킵 (최초 로그인 필요)
        session_file_path = session_file + ".session"
        if not os.path.exists(session_file_path):
            logger.warning("⚠️ 텔레그램 세션 파일이 없습니다. 로그인을 먼저 해주세요.")
            logger.warning("   → python telegram_login.py  (또는 직접 텔레그램 로그인)")
            logger.warning("   → 세션 없이 텔레그램 수집을 건너뜁니다.")
            return []

        # 전화번호가 설정되어 있으면 자동 로그인 시도
        if PHONE_NUMBER:
            await client.start(phone=PHONE_NUMBER)
        else:
            await client.start()
        logger.info("✅ 텔레그램 로그인 성공!")


        # 현재 시간 기준 24시간 전
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

        for channel_username in TARGET_CHANNELS:
            try:
                logger.info(f"📡 채널 접속 중: @{channel_username}")
                entity = await client.get_entity(channel_username)
                channel_title = getattr(entity, "title", channel_username)

                # 최근 메시지 순회 (최대 200개)
                msg_count = 0
                async for message in client.iter_messages(
                    entity, limit=200, offset_date=datetime.now(timezone.utc)
                ):
                    # 24시간 이전 메시지는 스킵
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

                logger.info(f"  → @{channel_username} ({channel_title}): {msg_count}건 수집")

            except Exception as e:
                logger.error(f"  ⚠️ @{channel_username} 처리 중 오류: {e}")
                continue

    except FloodWaitError as e:
        wait_seconds = e.seconds
        logger.warning(f"⏳ 텔레그램 FloodWait: {wait_seconds}초 대기 필요 (건너뜁니다)")
        return []

    except Exception as e:
        logger.error(f"❌ 텔레그램 클라이언트 오류: {e}")
        logger.warning("   → 텔레그램 수집을 건너뜁니다.")
        return []

    finally:
        await client.disconnect()
        logger.info("🔌 텔레그램 연결 종료")

    return events


def save_events(events: list):
    """수집된 이벤트를 JSON 파일로 저장"""
    # 날짜순 정렬
    events.sort(key=lambda x: x["date"])

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ {OUTPUT_JSON} 저장 완료 (총 {len(events)}건)")


def main():
    """메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("텔레그램 주식 일정 수집기 시작")
    logger.info("=" * 50)
    logger.info(f"  대상 채널: {', '.join(TARGET_CHANNELS)}")
    logger.info(f"  필터 키워드: {', '.join(KEYWORDS)}")
    logger.info(f"  수집 범위: 최근 24시간")
    logger.info("=" * 50)

    # 비동기 수집 실행
    events = asyncio.run(collect_telegram_events())

    # 저장
    if events:
        save_events(events)
    else:
        logger.warning("⚠️ 수집된 일정이 없습니다.")
        # 빈 배열이라도 저장 (파일 없음 방지)
        save_events([])

    # 결과 출력
    logger.info("-" * 50)
    logger.info(f"총 {len(events)}건의 일정이 수집되었습니다.")
    for ev in events:
        logger.info(f"  [{ev['date']}] {ev['title']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
