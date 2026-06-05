# Stock Calendar Pipeline - 자동화 시스템

## 개요

국내/해외 주식 일정을 자동으로 수집하여 FullCalendar 기반 HTML 캘린더를 생성합니다.

## 파일 구성

| 파일 | 설명 |
|------|------|
| `naver_crawler.py` | 네이버 금융 국내 주식 일정 크롤링 → `korea_events.json` |
| `global_crawler.py` | Investing.com 해외 경제 일정 크롤링 → `global_events.json` |
| `telegram_events.py` | 텔레그램 채널 주식 일정 수집 → `telegram_events.json` |
| `update_calendar.py` | 3개 JSON 통합 + 중복 제거 + HTML 생성 → `stock_calendar.html` |
| **`run_pipeline.py`** | **마스터 실행 파일** - 위 4개를 순차 실행 |
| `run_pipeline.bat` | 작업 스케줄러용 배치 파일 (콘솔 없이 백그라운드 실행) |

## 사용법

### 1) 수동 실행 (최신 데이터로 업데이트 + 브라우저 열기)

```bash
python C:\stock_calendar\run_pipeline.py
```

실행할 때마다 **항상 최신 데이터**를 크롤링하여 HTML을 업데이트하고, 완료 후 브라우저가 자동으로 열립니다.

### 2) 작업 스케줄러용 실행 (브라우저 열지 않음)

```bash
python C:\stock_calendar\run_pipeline.py --no-open
```

또는 배치 파일 실행:

```bash
C:\stock_calendar\run_pipeline.bat
```

---

## Windows 작업 스케줄러 등록 가이드

### 목표: 매일 오전 7:30에 자동 실행

### 방법 1: `schtasks` 명령어로 한 번에 등록 (권장)

관리자 권한으로 **명령 프롬프트(CMD)** 를 열고 아래 명령어를 실행하세요.

```batch
schtasks /create ^
  /tn "StockCalendarPipeline" ^
  /tr "C:\stock_calendar\run_pipeline.bat" ^
  /sc daily ^
  /st 07:30 ^
  /f
```

**옵션 설명:**
- `/tn "StockCalendarPipeline"` — 작업 이름
- `/tr "..."` — 실행할 배치 파일 경로
- `/sc daily` — 매일 실행
- `/st 07:30` — 오전 7시 30분
- `/f` — 기존 작업이 있으면 덮어쓰기

### 방법 2: GUI로 등록

1. **작업 스케줄러** 실행 (Windows 키 → "Task Scheduler" 검색)
2. 오른쪽 **"작업 만들기..."** 클릭
3. **일반 탭:**
   - 이름: `StockCalendarPipeline`
   - 설명: `주식 캘린더 자동 업데이트 (매일 07:30)`
   - **"사용자가 로그온할 때만 실행"** 체크 해제
   - **"가장 높은 권한으로 실행"** 체크 해제
4. **트리거 탭:**
   - **"새로 만들기..."** 클릭
   - 작업 시작: **"예약 시간에"**
   - 설정: **매일**
   - 시작: `07:30:00`
   - 확인
5. **동작 탭:**
   - **"새로 만들기..."** 클릭
   - 동작: **"프로그램 시작"**
   - 프로그램/스크립트: `C:\stock_calendar\run_pipeline.bat`
   - 확인
6. **확인** 클릭하여 작업 저장

### 등록 확인

```bash
schtasks /query /tn "StockCalendarPipeline"
```

### 작업 삭제 (필요시)

```bash
schtasks /delete /tn "StockCalendarPipeline" /f
```

---

## 로그 확인

파이프라인 실행 로그는 `C:\stock_calendar\pipeline_log.txt`에 저장됩니다.

```bash
type C:\stock_calendar\pipeline_log.txt
```

---

## 전체 파일 목록

```
C:\stock_calendar\
├── naver_crawler.py        # 국내 크롤러
├── global_crawler.py       # 해외 크롤러
├── telegram_events.py      # 텔레그램 수집기
├── update_calendar.py      # HTML 통합 생성기
├── run_pipeline.py         # ★ 마스터 실행 파일
├── run_pipeline.bat        # ★ 작업 스케줄러용 배치 파일
├── requirements.txt        # 의존성 패키지 목록
├── README.md               # 이 파일
├── stock_calendar.html     # 생성된 캘린더 (최종 결과물)
├── korea_events.json       # 국내 일정 데이터
├── global_events.json      # 해외 일정 데이터
├── telegram_events.json    # 텔레그램 일정 데이터
└── pipeline_log.txt        # 실행 로그
```
