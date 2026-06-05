# Stock Calendar - 고도화 작업 진행 상황

## [Step 1] 해외 일정 중요도 필터링 강화 (global_crawler.py 개선)
- [x] 완료
  - CORE_INDICATORS: 중요도 3(🔴) 핵심 지표 목록 정의
  - SECONDARY_INDICATORS: 중요도 2(🟡) 선별 목록 정의
  - LOW_IMPACT_KEYWORDS: 중요도 2 중에서도 제외할 저영향 지표 목록 정의
  - fetch_investing_calendar()에 3단계 필터링 로직 적용
    - 중요도 3: CORE_INDICATORS 매칭 시만 포함
    - 중요도 2: SECONDARY_INDICATORS 매칭 + LOW_IMPACT_KEYWORDS 제외
    - 중요도 1: 모두 제외

## [Step 2] IPO 상장일 자동 추출 (naver_crawler.py 개선)
- [x] 완료
  - fetch_ipo_schedule()에 3단계 파싱 로직 추가
    - [방법 1] 정규식 "상장/청약" 키워드 기반 날짜 추출
    - [방법 2] HTML 구조 기반 (td 내부 span/a 태그 분석)
    - [방법 3] 전체 텍스트 컨텍스트 매핑 (날짜 앞뒤 단어 분석)
  - 상장일 + 청약일 모두 추출하여 korea_events.json에 저장

## [Step 3] 정성 분석 기반 주요 일정 모듈 (qualitative_events.py 신규)
- [x] 완료
  - QUALITATIVE_EVENTS_DB 지식 베이스 구축 (25개 이벤트)
    - 주요 인사 발언/방문 (젠슨 황 GTC, CES, 한국 방문 등)
    - 정부 정책 발표 (반도체 특별법, 비상경제회의)
    - 국제 관계/정치 (한미 정상회담, 미국 선거)
    - 글로벌 컨퍼런스 (WWDC, 잭슨홀 미팅)
    - 고정 일정 (FOMC, CPI, PCE, 한은 금통위 등)
  - 카테고리별 색상 매핑 (인사/방문=주황, 통화정책=빨강, 정부정책=보라 등)
  - 유동적 날짜 처리 (flexible_date=True → 해당월 1일 + "(예상)" 표시)
  - run_pipeline.py에 Step 3로 통합
  - update_calendar.py에서 qualitative_events.json 로드 및 병합
  - HTML에 qualitative 타입 색상(.fc-event-qualitative) 추가
