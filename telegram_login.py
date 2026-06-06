"""
텔레그램 로그인 전용 스크립트 (telegram_login.py)

- 최초 1회 실행: 전화번호 인증 -> 세션 파일 생성
- 이후에는 세션 파일로 자동 로그인
- FloodWait 대비: 지수 백오프 적용

사용법:
    python telegram_login.py          # 정상 로그인
    python telegram_login.py --force  # 기존 세션 삭제 후 재로그인
"""
import os
import sys
import asyncio
import logging
import time

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PhoneCodeInvalidError, SessionPasswordNeededError

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


async def do_login():
    """로그인 수행"""
    # --force 옵션: 기존 세션 삭제
    if "--force" in sys.argv:
        session_path = SESSION_FILE + ".session"
        if os.path.exists(session_path):
            os.remove(session_path)
            logger.info("[OK] 기존 세션 파일 삭제 완료")

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    try:
        logger.info("[텔레그램 로그인을 시작합니다]")
        logger.info(f"   전화번호: {PHONE_NUMBER}")
        print()

        # code_callback을 직접 정의하여 input() 처리
        code_entered = None

        async def code_callback():
            nonlocal code_entered
            if code_entered is None:
                loop = asyncio.get_event_loop()
                code_entered = await loop.run_in_executor(
                    None, lambda: input("   텔레그램 앱에서 받은 인증코드를 입력하세요: ")
                )
            return code_entered

        await client.start(
            phone=PHONE_NUMBER,
            code_callback=code_callback,
        )

        me = await client.get_me()
        logger.info(f"[OK] 로그인 성공! 사용자: {me.first_name} (@{me.username or '없음'})")
        logger.info(f"   세션 파일: {SESSION_FILE}.session")
        return True

    except FloodWaitError as e:
        wait_seconds = e.seconds
        logger.warning(f"[TIMEOUT] FloodWait: {wait_seconds}초 대기 필요")
        if wait_seconds <= 60:
            logger.info(f"   {wait_seconds}초 동안 대기 후 재시도합니다...")
            await asyncio.sleep(wait_seconds)
            return await do_login()
        else:
            logger.error(f"   대기 시간이 너무 깁니다({wait_seconds}초). 나중에 다시 시도하세요.")
            return False

    except PhoneCodeInvalidError:
        logger.error("[FAIL] 인증코드가 올바르지 않습니다. 다시 실행해주세요.")
        return False

    except SessionPasswordNeededError:
        logger.warning("[2FA] 2단계 인증이 필요합니다.")
        loop = asyncio.get_event_loop()
        password = await loop.run_in_executor(
            None, lambda: input("   비밀번호(2FA)를 입력하세요: ")
        )
        await client.sign_in(password=password)
        me = await client.get_me()
        logger.info(f"[OK] 로그인 성공! 사용자: {me.first_name} (@{me.username or '없음'})")
        return True

    except Exception as e:
        logger.error(f"[FAIL] 로그인 중 오류 발생: {e}")
        return False

    finally:
        await client.disconnect()
        logger.info("[연결 종료]")


def main():
    print()
    print("=" * 55)
    print("  [텔레그램 로그인 도우미]")
    print("=" * 55)
    print()

    success = asyncio.run(do_login())

    print()
    if success:
        print("=" * 55)
        print("  [OK] 로그인 완료! 이제 telegram_events.py를 실행할 수 있습니다.")
        print("=" * 55)
    else:
        print("=" * 55)
        print("  [FAIL] 로그인 실패. 위 로그를 확인해주세요.")
        print("=" * 55)
    print()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
