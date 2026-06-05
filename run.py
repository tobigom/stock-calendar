"""
주식 캘린더 전체 파이프라인 실행기

1. 네이버 금융에서 국내 주식 일정 크롤링 (korea_events.json)
2. Investing.com에서 글로벌 경제 일정 크롤링 (global_events.json)
3. 텔레그램 채널에서 주식 일정 수집 (telegram_events.json)
4. 세 데이터를 병합하여 FullCalendar HTML 생성 (stock_calendar.html)
"""
import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(step_name: str, script_name: str):
    """스크립트를 실행하고 결과를 출력합니다."""
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"[SKIP] {script_name} 파일이 없습니다.")
        return False
    
    print(f"\n{'='*60}")
    print(f"[Step] {step_name}")
    print(f"[Run]  python {script_name}")
    print(f"{'='*60}")
    
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=False,
        cwd=BASE_DIR,
    )
    
    if result.returncode != 0:
        print(f"[ERROR] {step_name} 실패 (exit code: {result.returncode})")
        return False
    
    print(f"[DONE] {step_name} 완료")
    return True


def main():
    print("=" * 60)
    print("  주식 캘린더 전체 파이프라인")
    print("=" * 60)
    
    # Step 1: 국내 주식 일정 크롤링
    run_step("국내 주식 일정 크롤링 (네이버 금융)", "naver_crawler.py")
    
    # Step 2: 글로벌 경제 일정 크롤링
    run_step("글로벌 경제 일정 크롤링 (Investing.com)", "global_crawler.py")
    
    # Step 3: 텔레그램 주식 일정 수집
    run_step("텔레그램 주식 일정 수집", "telegram_events.py")
    
    # Step 4: HTML 캘린더 생성
    run_step("FullCalendar HTML 생성", "stock_calendar.py")
    
    # 결과 확인
    html_path = os.path.join(BASE_DIR, "stock_calendar.html")
    if os.path.exists(html_path):
        print(f"\n{'='*60}")
        print(f"[SUCCESS] 캘린더 생성 완료!")
        print(f"  HTML 파일: {html_path}")
        print(f"  브라우저에서 열려면 파일을 더블클릭하세요.")
        print(f"{'='*60}")
    else:
        print(f"\n[WARN] HTML 파일이 생성되지 않았습니다.")


if __name__ == "__main__":
    main()
