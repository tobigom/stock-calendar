"""
텔레그램 주식/경제 채널 검색 스크립트

- 텔레그램 API로 public 채널 검색
- 검색 결과에서 구독자 수, 설명 등을 확인
- 신뢰할 수 있는 채널 목록 생성

사용법:
    python telegram_search_channels.py
"""
import os
import sys
import asyncio
import logging
import json

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import InputPeerEmpty

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "telegram_session")

API_ID = 26220720
API_HASH = "778b9252849089d2b872061e9044e9ed"
PHONE_NUMBER = "821087555301"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 검색할 키워드
SEARCH_QUERIES = [
    "korean stock",
    "korea stock",
    "stock news",
    "investment",
    "investing",
    "주식",
    "증권",
    "투자",
    "경제",
    "IPO",
    "stock market",
    "trading",
    "value investing",
    "미국주식",
    "해외주식",
]

# 검증할 특정 채널들 (알려진 인기 채널)
VERIFY_CHANNELS = [
    "value_investing_lab",    # 기존
    "giant_mkt",              # 기존
    "stock_ipo_korea",        # IPO 정보
    "korea_economy_news",     # 경제 뉴스
    "us_stock_info",          # 미국 주식 정보
    "dividend_korea",         # 배당주 정보
    "investing_tips_kr",      # 투자 팁
    "stock_analysis_kr",      # 주식 분석
    "daily_stock_news",       # 데일리 주식 뉴스
    "kospi_stock",            # 코스피 정보
    "kosdaq_stock",           # 코스닥 정보
    "global_macro_economy",   # 글로벌 매크로 경제
    "korea_finance_news",     # 한국 금융 뉴스
    "stock_calendar_kr",      # 주식 캘린더
    "earnings_korea",         # 실적 정보
    "ipo_schedule_kr",        # 공모주 일정
]


async def search_channels():
    """채널 검색 및 검증"""
    session_path = SESSION_FILE + ".session"
    if not os.path.exists(session_path):
        logger.warning("[WARN] 세션 파일이 없습니다. 먼저 telegram_login.py를 실행해주세요.")
        return []

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    try:
        await client.start(phone=PHONE_NUMBER)
        me = await client.get_me()
        logger.info(f"[OK] 로그인 성공: {me.first_name}")

        found_channels = []

        # 1) 특정 채널 검증
        logger.info(f"\n[1/2] 알려진 채널 {len(VERIFY_CHANNELS)}개 검증 중...")
        for username in VERIFY_CHANNELS:
            try:
                entity = await client.get_entity(username)
                title = getattr(entity, 'title', username)
                participants = getattr(entity, 'participants_count', '?')
                about = getattr(entity, 'about', '')
                logger.info(f"  [OK] @{username} -> '{title}' (멤버: {participants})")
                found_channels.append({
                    "username": username,
                    "title": title,
                    "participants": participants,
                    "about": about[:100] if about else '',
                })
            except FloodWaitError as e:
                logger.warning(f"  [FLOOD] FloodWait {e.seconds}초 - 5초 대기 후 계속")
                await asyncio.sleep(5)
                continue
            except Exception as e:
                logger.warning(f"  [FAIL] @{username}: {e}")

        # 2) 키워드 검색
        logger.info(f"\n[2/2] 키워드 검색 중...")
        for query in SEARCH_QUERIES:
            try:
                logger.info(f"  검색어: '{query}'")
                result = await client(SearchRequest(
                    q=query,
                    limit=10,
                ))
                for chat in result.chats:
                    username = getattr(chat, 'username', None)
                    if not username:
                        continue
                    title = getattr(chat, 'title', '?')
                    participants = getattr(chat, 'participants_count', 0)
                    about = getattr(chat, 'about', '')
                    # 이미 찾은 채널은 스킵
                    if any(c['username'] == username for c in found_channels):
                        continue
                    # 멤버 1000명 이상만
                    if isinstance(participants, int) and participants < 1000:
                        continue
                    found_channels.append({
                        "username": username,
                        "title": title,
                        "participants": participants,
                        "about": about[:100] if about else '',
                    })
                    logger.info(f"  [NEW] @{username} -> '{title}' (멤버: {participants})")
                await asyncio.sleep(2)  # FloodWait 방지
            except FloodWaitError as e:
                logger.warning(f"  [FLOOD] {e.seconds}초 대기")
                await asyncio.sleep(min(e.seconds, 10))
                continue
            except Exception as e:
                logger.warning(f"  [FAIL] 검색어 '{query}': {e}")
                continue

        # 중복 제거 및 정렬
        seen = set()
        unique_channels = []
        for ch in found_channels:
            if ch['username'] not in seen:
                seen.add(ch['username'])
                unique_channels.append(ch)

        # 멤버 수 기준 정렬
        def sort_key(ch):
            p = ch.get('participants', 0)
            return -p if isinstance(p, int) else 0
        unique_channels.sort(key=sort_key)

        return unique_channels

    except FloodWaitError as e:
        logger.error(f"[FLOOD] FloodWait {e.seconds}초 - 너무 김, 중단")
        return []
    except Exception as e:
        logger.error(f"[FAIL] 검색 중 오류: {e}")
        return []
    finally:
        await client.disconnect()
        logger.info("[연결 종료]")


def main():
    print()
    print("=" * 60)
    print("  [텔레그램 주식 채널 검색기]")
    print("=" * 60)
    print()

    channels = asyncio.run(search_channels())

    print()
    print("=" * 60)
    print(f"  검색 결과: 총 {len(channels)}개 채널 발견")
    print("=" * 60)
    print()

    if channels:
        for i, ch in enumerate(channels, 1):
            participants = ch.get('participants', '?')
            about = ch.get('about', '')[:80]
            print(f"  {i:2d}. @{ch['username']}")
            print(f"      제목: {ch['title']}")
            print(f"      멤버: {participants}")
            if about:
                print(f"      설명: {about}")
            print()

        # JSON 저장
        output_path = os.path.join(BASE_DIR, "telegram_channels_found.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] 채널 목록 저장 완료: {output_path}")

        # 추천 채널 목록 생성 (멤버 5000명 이상)
        recommended = [ch for ch in channels
                       if isinstance(ch.get('participants'), int) and ch['participants'] >= 5000]
        if recommended:
            print("  [추천 채널 목록 (멤버 5000명 이상)]")
            print()
            for ch in recommended:
                print(f'    "{ch["username"]}",  # {ch["title"]} (멤버: {ch["participants"]})')
            print()
    else:
        print("  검색 결과가 없습니다.")
        print("  먼저 telegram_login.py를 실행하여 로그인해주세요.")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
