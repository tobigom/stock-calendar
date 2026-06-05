"""
=============================================================================
 [Stock Calendar Pipeline] - Master Executor + GitHub Auto Push
=============================================================================
 실행할 때마다 항상 최신 데이터로 크롤링 + HTML 생성 + GitHub 자동 업로드

 실행 순서:
   1. naver_crawler.py      (국내 주식 일정 크롤링)
   2. global_crawler.py     (해외 경제 일정 크롤링)
   3. qualitative_events.py (정성 분석 주요 일정 생성)
   4. telegram_events.py    (텔레그램 주식 일정 수집)
   5. update_calendar.py    (JSON 통합 + HTML 생성)
   6. git_push_to_github()  (index.html → GitHub 자동 Push)

 사용법:
   python run_pipeline.py           # 전체 실행 + 브라우저 오픈 + GitHub Push
   python run_pipeline.py --no-open # 브라우저 열지 않음 (작업 스케줄러용)
   python run_pipeline.py --no-push # GitHub Push 생략

=============================================================================
"""

import os
import sys
import subprocess
import time
import urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# [설정] GitHub 저장소 정보
# ============================================================
# ※ Personal Access Token은 절대 외부에 노출되지 않도록 주의하세요!
#    - GitHub에 직접 코드를 올릴 때는 토큰을 제거하거나 환경변수로 처리하세요.
#    - 아래 GITHUB_TOKEN에 직접 값을 넣어도 되지만,
#      보안을 위해 시스템 환경변수(예: STOCK_CALENDAR_TOKEN)를 사용하는 것을 권장합니다.
# ============================================================

# (1) GitHub 저장소 URL (자신의 저장소 주소로 변경)
GITHUB_REPO_URL = "https://github.com/tobigom/stock-calendar"

# (2) Personal Access Token (직접 입력 또는 환경변수에서 불러오기)
#     방법 A: 아래 변수에 직접 토큰 입력
#     방법 B: os.environ.get("STOCK_CALENDAR_TOKEN") 사용 (권장)
GITHUB_TOKEN = os.environ.get("STOCK_CALENDAR_TOKEN", "")
# GITHUB_TOKEN = "github_pat_여기에_토큰_입력"  # 직접 입력 시 주석 해제

# (3) Git 사용자 정보 (commit 시 표시될 이름/이메일)
GIT_USER_NAME = "tobigom"
GIT_USER_EMAIL = "tobigom@example.com"

# ============================================================
# 파이프라인 정의
# ============================================================
PIPELINE = [
    ("[1/6] 국내 주식 일정 크롤링 (Naver)",         "naver_crawler.py",     False),
    ("[2/6] 해외 경제 일정 크롤링 (Investing.com)",  "global_crawler.py",    False),
    ("[3/6] 정성 분석 주요 일정 생성",              "qualitative_events.py", False),
    ("[4/6] 텔레그램 주식 일정 수집",              "telegram_events.py",   False),
    ("[5/6] JSON 통합 + HTML 캘린더 생성",         "update_calendar.py",   False),
    ("[6/6] GitHub 자동 Push",                    None,                   False),  # 특수 단계
]


def print_banner():
    """파이프라인 시작 배너 출력"""
    print()
    print("=" * 65)
    print("     Stock Calendar Pipeline - Master Executor")
    print(f"     실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print()


def print_step_header(step_name: str, index: int, total: int):
    """각 단계 시작 헤더 출력"""
    print()
    print("-" * 65)
    print(f"  {step_name}  ({index}/{total})")
    print("-" * 65)


def print_result(step_name: str, success: bool, elapsed: float, output: str = ""):
    """단계 실행 결과 출력"""
    status = "[OK]" if success else "[FAIL]"
    print(f"  {status} {step_name}  ({elapsed:.1f}초)")
    if output:
        lines = [l for l in output.strip().split("\n") if l.strip()]
        for line in lines[-3:]:
            print(f"    > {line.strip()}")
    print()


def run_step(step_name: str, script_name: str, required: bool = False) -> bool:
    """
    단일 스크립트를 subprocess로 실행.
    성공 여부를 반환하며, required=True이면 실패 시 sys.exit(1).
    """
    script_path = os.path.join(BASE_DIR, script_name)

    if not os.path.exists(script_path):
        print(f"  [SKIP] {script_name} 파일이 존재하지 않습니다.")
        if required:
            sys.exit(1)
        return False

    start_time = time.time()

    # 텔레그램 단계는 30초 타임아웃 (로그인 문제 시 빠르게 스킵)
    timeout_sec = 30 if "telegram" in script_name else 120

    try:
        # 텔레그램 단계: 타임아웃 시 프로세스 강제 종료를 위해 Popen 사용
        if "telegram" in script_name:
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=BASE_DIR,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout_sec)
                result = subprocess.CompletedProcess(
                    args=[sys.executable, script_path],
                    returncode=proc.returncode,
                    stdout=stdout or "",
                    stderr=stderr or "",
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                elapsed = time.time() - start_time
                print(f"  [TIMEOUT] {step_name} - {timeout_sec}초 초과, 프로세스 강제 종료됨 ({elapsed:.1f}초)")
                if required:
                    sys.exit(1)
                return False
        else:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=timeout_sec,
            )
        elapsed = time.time() - start_time
        success = result.returncode == 0

        output = (result.stdout or "") + (result.stderr or "")
        print_result(step_name, success, elapsed, output)

        if not success and required:
            print(f"  [CRITICAL] 필수 단계 실패로 파이프라인을 중단합니다.")
            sys.exit(1)

        return success

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"  [TIMEOUT] {step_name} - {timeout_sec}초 초과 ({elapsed:.1f}초)")
        if required:
            sys.exit(1)
        return False

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  [ERROR] {step_name} 실행 중 예외 발생: {e}")
        if required:
            sys.exit(1)
        return False


def open_html_in_browser():
    """생성된 HTML 파일을 기본 브라우저로 열기"""
    html_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(html_path):
        try:
            if sys.platform == "win32":
                os.startfile(html_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", html_path])
            else:
                subprocess.run(["xdg-open", html_path])
            print(f"  [BROWSER] index.html -> 브라우저 열기 완료")
            return True
        except Exception as e:
            print(f"  [WARN] 브라우저 열기 실패: {e}")
            return False
    else:
        print(f"  [WARN] index.html 파일이 없습니다.")
        return False


# ============================================================
# [GitHub 자동 Push 함수]
# ============================================================
def git_push_to_github() -> bool:
    """
    index.html을 GitHub 저장소에 자동으로 add → commit → push 합니다.
    
    인증 방식:
      - GITHUB_TOKEN이 설정되어 있으면 토큰 기반 URL 사용
      - 토큰이 없으면 기존 원격 저장소 인증(ssh/id)에 의존
    """
    html_path = os.path.join(BASE_DIR, "index.html")

    if not os.path.exists(html_path):
        print(f"  [SKIP] index.html 파일이 없어 GitHub Push를 건너<skip>니다.")
        return False

    # --no-push 옵션 체크
    if "--no-push" in sys.argv:
        print(f"  [SKIP] --no-push 옵션으로 GitHub Push를 건너<skip>니다.")
        return False

    print(f"  [GIT] GitHub 저장소에 index.html 업로드를 시작합니다...")
    start_time = time.time()

    # GIT_DIR 환경변수 대신 --git-dir / --work-tree 옵션 사용
    GIT_OPTS = ["--git-dir=" + os.path.join(BASE_DIR, ".git").replace("\\", "/"),
                "--work-tree=" + BASE_DIR.replace("\\", "/")]

    def _run_git(cmd_list, timeout=10):
        """git 명령어 실행 헬퍼 (text=True 대신 encoding='utf-8' 사용)"""
        return subprocess.run(
            ["git"] + GIT_OPTS + cmd_list,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )

    try:
        # 1) Git 사용자 정보 설정 (최초 1회) - --global로 설정
        subprocess.run(
            ["git", "config", "--global", "user.name", GIT_USER_NAME],
            capture_output=True, encoding='utf-8', errors='replace', timeout=10
        )
        subprocess.run(
            ["git", "config", "--global", "user.email", GIT_USER_EMAIL],
            capture_output=True, encoding='utf-8', errors='replace', timeout=10
        )

        # 2) git init (항상 C:\stock_calendar에 .git 생성)
        git_dir_path = os.path.join(BASE_DIR, ".git")
        if not os.path.exists(git_dir_path):
            print(f"  [GIT] Git 저장소 초기화 중...")
            _run_git(["init", "-b", "main"], timeout=10)

        # 3) 원격 저장소 설정
        if GITHUB_TOKEN:
            # 토큰에 특수문자(@, _, . 등)가 포함될 수 있으므로 URL 인코딩
            encoded_token = urllib.parse.quote(GITHUB_TOKEN, safe='')
            token_url = GITHUB_REPO_URL.replace("https://", f"https://{encoded_token}@")
            _run_git(["remote", "remove", "origin"], timeout=10)
            _run_git(["remote", "add", "origin", token_url], timeout=10)
        else:
            remote_check = _run_git(["remote", "get-url", "origin"], timeout=10)
            if remote_check.returncode != 0:
                _run_git(["remote", "add", "origin", GITHUB_REPO_URL], timeout=10)

        # 4) 모든 변경 파일 add (index.html + 기타 파일들)
        _run_git(["add", "-A"], timeout=10)

        # 5) 변경사항 확인
        status_result = _run_git(["status", "--porcelain"], timeout=10)
        if not status_result.stdout.strip():
            rev_parse = _run_git(["rev-parse", "--verify", "HEAD"], timeout=10)
            if rev_parse.returncode != 0:
                print(f"  [GIT] 첫 commit을 생성합니다...")
                _run_git(["commit", "--allow-empty", "-m", "Initial commit"], timeout=10)
            else:
                print(f"  [GIT] 변경사항이 없어 commit을 건너<skip>니다.")
                return True

        # 6) commit
        today_str = datetime.now().strftime("%Y-%m-%d")
        commit_msg = f"[Auto] 주식 캘린더 자동 갱신: {today_str}"
        commit_result = _run_git(["commit", "-m", commit_msg], timeout=10)
        if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stderr:
            print(f"  [GIT] commit 실패: {commit_result.stderr.strip()[:200]}")

        # 7) push (--force: 원격 저장소에 기존 파일이 있어도 강제 업데이트)
        push_result = _run_git(["push", "-u", "origin", "main", "--force"], timeout=30)

        elapsed = time.time() - start_time

        if push_result.returncode == 0:
            print(f"  [GIT] [OK] GitHub Push 성공! ({elapsed:.1f}초)")
            print(f"  [GIT]    -> {GITHUB_REPO_URL}")
            return True
        else:
            push_result2 = _run_git(["push", "-u", "origin", "master"], timeout=30)
            if push_result2.returncode == 0:
                print(f"  [GIT] [OK] GitHub Push 성공! (master 브랜치, {elapsed:.1f}초)")
                print(f"  [GIT]    -> {GITHUB_REPO_URL}")
                return True
            else:
                error_msg = push_result.stderr.strip() or push_result2.stderr.strip()
                print(f"  [GIT] [FAIL] GitHub Push 실패: {error_msg[:200]}")
                return False

    except subprocess.TimeoutExpired:
        print(f"  [GIT] [TIMEOUT] GitHub Push 시간 초과")
        return False
    except Exception as e:
        import traceback
        print(f"  [GIT] [FAIL] GitHub Push 중 오류 발생: {e}")
        print(f"  [GIT] [DEBUG] Traceback: {traceback.format_exc()[:500]}")
        return False


# ============================================================
# [배치 파일 생성 함수]
# ============================================================
def create_desktop_bat():
    """
    바탕화면용 '주식캘린더_즉시갱신.bat' 파일을 생성합니다.
    사용자가 더블클릭만으로 전체 파이프라인을 실행할 수 있습니다.
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    bat_path = os.path.join(desktop, "주식캘린더_즉시갱신.bat")

    bat_content = f"""@echo off
chcp 65001 >nul
title 📈 주식 캘린더 즉시 갱신
echo ============================================
echo   주식 캘린더 파이프라인 실행 중...
echo   (잠시만 기다려주세요)
echo ============================================
echo.

cd /d "{BASE_DIR}"

python run_pipeline.py

echo.
if %errorlevel%==0 (
    echo ============================================
    echo   ✅ 모든 작업이 완료되었습니다!
    echo   index.html이 GitHub에 업로드되었습니다.
    echo ============================================
) else (
    echo ============================================
    echo   ⚠️ 일부 단계에서 오류가 발생했습니다.
    echo   위 로그를 확인해주세요.
    echo ============================================
)

echo.
pause
"""
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        print(f"  [BAT] [OK] 바탕화면 배치 파일 생성 완료!")
        print(f"  [BAT]    -> {bat_path}")
        return True
    except Exception as e:
        print(f"  [BAT] [FAIL] 배치 파일 생성 실패: {e}")
        return False


# ============================================================
# [작업 스케줄러 등록 가이드 출력]
# ============================================================
def print_scheduler_guide():
    """Windows 작업 스케줄러 등록 방법을 출력합니다."""
    guide = f"""
{'=' * 65}
  [Windows 작업 스케줄러 등록 가이드]
  매일 오전 7:30에 자동 실행 설정
{'=' * 65}

  [방법]
  1. '작업 스케줄러(Task Scheduler)' 실행 (Windows 키 → "Task Scheduler" 검색)
  2. 오른쪽 메뉴에서 '작업 만들기(Create Task...)' 클릭

  [일반(General) 탭]
  - 이름: "주식캘린더_자동갱신"
  - 설명: "매일 오전 7:30 주식 캘린더를 갱신하고 GitHub에 업로드"
  - 보안 옵션:
    · '사용자가 로그온할 때만 실행(Run only when user is logged on)' 선택
    · '최고 권한으로 실행(Run with highest privileges)' 체크 해제

  [트리거(Triggers) 탭]
  - 새로 만들기(New...)
  - 작업 시작: "예약 일정(On a schedule)"
  - 설정: "매일(Daily)"
  - 시작: 오전 7:30:00
  - 사용(Enabled) 체크
  - 확인

  [동작(Actions) 탭]
  - 새로 만들기(New...)
  - 동작: "프로그램 시작(Start a program)"
  - 프로그램/스크립트:
    python
  - 인수 추가(옵션):
    run_pipeline.py --no-open
  - 시작 위치(옵션):
    {BASE_DIR}
  - 확인

  [조건(Conditions) 탭]
  - '컴퓨터가 AC 전원에 연결되어 있을 때만 시작' 체크 해제 (선택사항)

  [설정(Settings) 탭]
  - '가장 오래 실행된 작업 중지' → 30분으로 설정 (선택사항)

  [참고]
  - 컴퓨터가 꺼져 있으면 작업이 실행되지 않습니다.
  - 매일 아침 7:30에 컴퓨터가 켜져 있어야 자동 갱신됩니다.
  - 작업 스케줄러는 백그라운드에서 실행되므로 브라우저는 열리지 않습니다.
  - 생성된 index.html은 자동으로 GitHub에 Push됩니다.

{'=' * 65}
"""
    print(guide)


# ============================================================
# 메인 함수
# ============================================================
def main():
    # 명령줄 인자 처리
    no_open = "--no-open" in sys.argv
    skip_telegram = "--skip-telegram" in sys.argv

    print_banner()

    total_steps = len(PIPELINE)
    success_count = 0
    fail_count = 0

    for i, (step_name, script_name, required) in enumerate(PIPELINE, 1):
        # 텔레그램 스킵 옵션
        if skip_telegram and script_name and "telegram" in script_name:
            print(f"  [SKIP] --skip-telegram 옵션으로 텔레그램 단계를 건너<skip>니다.")
            continue

        print_step_header(step_name, i, total_steps)

        # 6단계(GitHub Push)는 특수 처리
        if script_name is None:
            ok = git_push_to_github()
        else:
            ok = run_step(step_name, script_name, required)

        if ok:
            success_count += 1
        else:
            fail_count += 1

    # 최종 결과 요약
    print()
    print("=" * 65)
    print("  [파이프라인 실행 완료]")
    print(f"  전체 단계: {total_steps}개")
    print(f"  성공: {success_count}개 / 실패: {fail_count}개")
    print(f"  완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # HTML 파일 브라우저 열기 (--no-open 옵션이 없을 때만)
    if not no_open:
        print()
        print("  [INFO] 생성된 캘린더를 브라우저에서 엽니다...")
        open_html_in_browser()

    # 최종 HTML 파일 크기 출력
    html_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(html_path):
        size_kb = os.path.getsize(html_path) / 1024
        print(f"  [INFO] index.html ({size_kb:.1f} KB)")
    print()

    # 배치 파일 생성 (최초 1회)
    bat_path = os.path.join(os.path.expanduser("~"), "Desktop", "주식캘린더_즉시갱신.bat")
    if not os.path.exists(bat_path):
        print("  [INFO] 바탕화면 배치 파일을 생성합니다...")
        create_desktop_bat()
        print()

    # 작업 스케줄러 가이드 출력 (최초 1회)
    guide_flag = os.path.join(BASE_DIR, ".scheduler_guide_done")
    if not os.path.exists(guide_flag):
        print_scheduler_guide()
        # 가이드를 한 번만 출력하도록 플래그 파일 생성
        try:
            with open(guide_flag, "w", encoding="utf-8") as f:
                f.write(f"Guide shown at: {datetime.now()}\n")
        except Exception:
            pass

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
