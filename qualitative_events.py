"""
정성 분석(Qualitative Analysis) 기반 주요 주식 일정 모듈

과거 시장에 큰 영향을 미친 이벤트 유형을 지식 베이스로 관리하여,
정량적 중요도(CPI, GDP 등)로는 포착하기 어렵지만 시장에 큰 영향을 주는
일정을 캘린더에 추가합니다.

포함 대상:
- 주요 인사 발언/방문 (젠슨 황, 파월 의장 등)
- 정부 정책 발표 (비상경제회의, 반도체 특별법 등)
- 국제 관계 이벤트 (정상회담, 수출 규제 등)
- 주요국 선거/정치 일정
- 글로벌 컨퍼런스 (GTC, CES 등)
"""

from __future__ import annotations
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# 정성 분석 지식 베이스
# ============================================================
# 각 이벤트는 다음 필드를 가집니다:
#   date: "YYYY-MM-DD" (고정 날짜) 또는 None (매년/매월 반복)
#   month: int (매년 반복되는 경우 월)
#   day: int (매년 반복되는 경우 일)
#   title: 캘린더에 표시될 제목
#   type: 이벤트 유형 ("qualitative")
#   category: 카테고리 (아래 참조)
#   description: 이벤트 설명
#   impact_reason: 과거 시장 영향 근거
#   source: 정보 출처

QUALITATIVE_EVENTS_DB = [
    # ============================================================
    # 1. 주요 인사 발언/방문
    # ============================================================
    {
        "date": None, "month": 3, "day": None,  # 3월 중 (GTC)
        "title": "젠슨 황 GTC 키노트 (엔비디아 GTC 컨퍼런스)",
        "type": "qualitative",
        "category": "인사/방문",
        "description": "엔비디아 GTC(GPU Technology Conference)에서 젠슨 황 CEO 기조연설. 신제품 발표, 로드맵 공개.",
        "impact_reason": "과거 GTC에서 차세대 GPU/반도체 발표 시 엔비디아 주가 5~15% 급등, 국내 반도체/AI 관련주 동반 상승",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,  # 정확한 날짜는 매년 다름
    },
    {
        "date": None, "month": 5, "day": None,  # 5월 중
        "title": "젠슨 황 대만 컴퓨텍스(Computex) 기조연설",
        "type": "qualitative",
        "category": "인사/방문",
        "description": "컴퓨텍스 타이베이에서 젠슨 황 CEO 기조연설. AI/데이터센터 관련 발표.",
        "impact_reason": "AI 반도체 수요 전망 발표 시 국내 HBM/반도체주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 1, "day": None,  # 1월 초 (CES)
        "title": "CES 2026 개최 (라스베가스, 젠슨 황 기조연설)",
        "type": "qualitative",
        "category": "컨퍼런스",
        "description": "CES 2026에서 엔비디아/삼성/LG 등 주요 기업 신제품 발표",
        "impact_reason": "CES 기간 중 국내 전자/반도체/IT주 변동성 확대",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 2, "day": None,
        "title": "젠슨 황 한국 방문 (예상)",
        "type": "qualitative",
        "category": "인사/방문",
        "description": "젠슨 황 CEO의 한국 방문 시 삼성전자/하이닉스 HBM 협력 논의",
        "impact_reason": "2024년 방한 시 HBM 관련주 급등, 삼성전자/하이닉스 주가 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 6, "day": None,
        "title": "연준 파월 의장 반기 통화정책 보고 (의회 증언)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "파월 연준 의장의 상/하원 통화정책 반기 보고. 금리 전망 시사.",
        "impact_reason": "매년 2월/6월 의회 증언에서 금리 방향성 시사 시 전 세계 증시 출렁",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 2, "day": None,
        "title": "연준 파월 의장 반기 통화정책 보고 (의회 증언)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "파월 연준 의장의 상/하원 통화정책 반기 보고",
        "impact_reason": "매년 2월/6월 의회 증언에서 금리 방향성 시사 시 전 세계 증시 출렁",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    # ============================================================
    # 2. 정부 정책 발표
    # ============================================================
    {
        "date": None, "month": 7, "day": None,
        "title": "한국 반도체 특별법/지원책 발표 (예상)",
        "type": "qualitative",
        "category": "정부정책",
        "description": "K-반도체 클러스터, 세제 지원, R&D 투자 등 반도체 산업 육성 정책",
        "impact_reason": "2023년 반도체 지원책 발표 시 삼성전자/하이닉스 등 반도체주 급등",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 9, "day": None,
        "title": "한국 정부 비상경제회의/경제정책 방향 발표",
        "type": "qualitative",
        "category": "정부정책",
        "description": "기획재정부 주관 경제정책 방향, 수출/내수 활성화 대책",
        "impact_reason": "정책 발표 시 관련 업종(반도체, 배터리, 자동차) 주가 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    # ============================================================
    # 3. 국제 관계/정치
    # ============================================================
    {
        "date": None, "month": 4, "day": None,
        "title": "한미 정상회담 (예상)",
        "type": "qualitative",
        "category": "국제관계",
        "description": "한미 정상회담 시 방산/원전/반도체 협력 관련주 영향",
        "impact_reason": "2023년 한미 정상회담 시 방산주/원전주 급등",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 11, "day": None,
        "title": "미국 중간선거/대선 관련 일정",
        "type": "qualitative",
        "category": "정치",
        "description": "미국 선거 관련 정책 불확실성, 주요 공약 발표",
        "impact_reason": "선거 시즌 정책 불확실성으로 변동성 확대, 특정 업종(신재생, 방산) 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    # ============================================================
    # 4. 글로벌 컨퍼런스/이벤트
    # ============================================================
    {
        "date": None, "month": 9, "day": None,
        "title": "애플 신제품 발표 (9월 이벤트)",
        "type": "qualitative",
        "category": "컨퍼런스",
        "description": "애플 아이폰 신제품 발표. 국내 부품주(카메라, 배터리, 디스플레이) 영향.",
        "impact_reason": "아이폰 출시 사이클에 따라 국내 부품주 실적/주가 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 6, "day": None,
        "title": "WWDC (애플 세계 개발자 컨퍼런스)",
        "type": "qualitative",
        "category": "컨퍼런스",
        "description": "애플 WWDC에서 신규 OS, AI 전략 발표",
        "impact_reason": "AI 전략 발표 시 국내 애플 부품주/IT주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    # ============================================================
    # 5. 고정 일정 (날짜 확정)
    # ============================================================
    {
        "date": "2026-06-10",
        "title": "미국 5월 CPI 발표",
        "type": "qualitative",
        "category": "경제지표",
        "description": "5월 소비자물가지수(CPI) 발표. 연준 금리 결정에 직접적 영향.",
        "impact_reason": "CPI 발표일마다 코스피/코스닥 변동성 2~3배 확대",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-06-11",
        "title": "ECB 통화정책회의 (금리 결정)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "유럽중앙은행(ECB) 금리 결정 및 통화정책 방향",
        "impact_reason": "ECB 금리 결정 시 유로/달러 환율 변동 → 국내 증시 영향",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-06-17",
        "title": "미국 5월 소매판매(Retail Sales) 발표",
        "type": "qualitative",
        "category": "경제지표",
        "description": "5월 소매판매 데이터. 소비 경기 판단 핵심 지표.",
        "impact_reason": "소비 둔화 신호 시 코스피 하방 압력",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-06-18",
        "title": "미국 FOMC 금리 결정 (6월)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "연준 FOMC 6월 회의. 금리 결정 및 점도표, 경제 전망 업데이트.",
        "impact_reason": "FOMC 발표일마다 코스피 1~3% 변동. 점도표에 따른 금리 전망이 시장 방향 결정",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-06-25",
        "title": "미국 5월 PCE 물가지수 발표",
        "type": "qualitative",
        "category": "경제지표",
        "description": "연준이 선호하는 물가 지표. 근원 PCE 핵심.",
        "impact_reason": "PCE 발표일마다 증시 변동성 확대",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-07-01",
        "title": "한국 6월 수출입 동향 발표",
        "type": "qualitative",
        "category": "경제지표",
        "description": "산업통상자원부 6월 수출입 실적. 반도체/자동차 수출 핵심.",
        "impact_reason": "수출 데이터에 따라 코스피 방향성 결정. 반도체 수출 증감률 중요",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-07-15",
        "title": "한국은행 금융통화위원회 (기준금리 결정)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "한은 금통위 금리 결정. 한국 경제 전망 업데이트.",
        "impact_reason": "금리 결정 및 한은 총재 발언에 따라 코스피/코스닥 영향",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-07-29",
        "title": "미국 FOMC 금리 결정 (7월)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "연준 FOMC 7월 회의. 금리 결정 및 성명서.",
        "impact_reason": "FOMC 발표일마다 코스피 1~3% 변동",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-08-27",
        "title": "잭슨홀 미팅 (Jackson Hole Symposium)",
        "type": "qualitative",
        "category": "컨퍼런스",
        "description": "캔자스시티 연은 주최 잭슨홀 경제 심포지엄. 파월 의장 기조연설.",
        "impact_reason": "2022년 잭슨홀에서 파월 매파 발언 후 코스피 3% 폭락. 매년 시장 방향성 결정",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-09-17",
        "title": "미국 FOMC 금리 결정 (9월)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "연준 FOMC 9월 회의. 금리 결정 및 점도표 업데이트.",
        "impact_reason": "FOMC 발표일마다 코스피 1~3% 변동",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-11-05",
        "title": "미국 FOMC 금리 결정 (11월)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "연준 FOMC 11월 회의. 금리 결정.",
        "impact_reason": "FOMC 발표일마다 코스피 1~3% 변동",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-12-17",
        "title": "미국 FOMC 금리 결정 (12월)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "연준 FOMC 12월 회의. 금리 결정 및 점도표, 경제 전망 업데이트.",
        "impact_reason": "연말 FOMC는 다음해 금리 전망 제시로 시장 큰 영향",
        "source": "qualitative_knowledge_base",
    },
]

# ============================================================
# 카테고리별 색상 매핑
# ============================================================
CATEGORY_COLORS = {
    "인사/방문": "#e67e22",      # 주황
    "통화정책": "#c0392b",       # 진빨강
    "정부정책": "#8e44ad",       # 보라
    "국제관계": "#2c3e50",       # 진남색
    "정치": "#7f8c8d",           # 회색
    "컨퍼런스": "#16a085",       # 청록
    "경제지표": "#2980b9",       # 파랑
}

# ============================================================
# 선물옵션 만기일 계산
# ============================================================

def get_futures_options_expiry_dates(year: int = None) -> list[dict]:
    """
    한국 선물옵션 동시만기일 계산
    
    한국 파생상품 시장의 선물옵션 동시만기일은
    매년 3월, 6월, 9월, 12월의 두 번째 목요일입니다.
    
    이 날은 만기일이 다가올수록 변동성이 커지며,
    만기일 당일 장 막판에 괴리율 축소를 위한
    프로그램 매매(차익거래)가 대량으로 발생하여
    주식시장이 요동치는 특징이 있습니다.
    
    Args:
        year: 기준년도 (None이면 현재년도)
    
    Returns:
        [{"date": "YYYY-MM-DD", "title": "...", "type": "futures_options", ...}, ...]
    """
    if year is None:
        year = datetime.now().year
    
    result = []
    # 선물옵션 만기월: 3월, 6월, 9월, 12월
    expiry_months = [3, 6, 9, 12]
    
    for month in expiry_months:
        # 해당월 1일의 요일 확인
        first_day = datetime(year, month, 1)
        # 1일이 무슨 요일인지 (0=월, 1=화, 2=수, 3=목, 4=금, 5=토, 6=일)
        weekday = first_day.weekday()
        
        # 두 번째 목요일 계산
        # 목요일(weekday=3)까지의 일수
        if weekday <= 3:
            # 첫 번째 목요일: (3 - weekday)일 후
            first_thursday = 3 - weekday + 1  # 1일 기준
            second_thursday = first_thursday + 7
        else:
            # 다음주 목요일: (7 - weekday + 3)일 후
            first_thursday = 7 - weekday + 3 + 1  # 1일 기준
            second_thursday = first_thursday
        
        expiry_date = datetime(year, month, second_thursday)
        date_str = expiry_date.strftime("%Y-%m-%d")
        
        # 만기월 이름
        month_names = {3: "3월", 6: "6월", 9: "9월", 12: "12월"}
        month_name = month_names[month]
        
        result.append({
            "date": date_str,
            "title": f"📊 선물옵션 동시만기일 ({month_name})",
            "type": "futures_options",
            "category": "파생상품",
            "color": "#2c3e50",
            "description": f"{year}년 {month_name} 선물옵션 동시만기일. 만기일 괴리율 축소를 위한 프로그램 매매로 증시 변동성 확대.",
            "impact_reason": "만기일마다 코스피/코스닥 장 막판 1~3% 변동. 프로그램 매매(차익거래) 대량 발생.",
            "source": "qualitative_knowledge_base",
        })
    
    return result


# ============================================================
# 주요 함수
# ============================================================

def get_qualitative_events(
    start_date: str = None,
    end_date: str = None,
    days_back: int = 7,
    days_forward: int = 90,
) -> list[dict]:
    """
    정성 분석 기반 주요 일정을 반환합니다.
    
    Args:
        start_date: 시작일 (YYYY-MM-DD). None이면 days_back 기준.
        end_date: 종료일 (YYYY-MM-DD). None이면 days_forward 기준.
        days_back: 과거 몇 일까지 포함할지
        days_forward: 미래 몇 일까지 포함할지
    
    Returns:
        [{"date": "YYYY-MM-DD", "title": "...", "type": "qualitative", ...}, ...]
    """
    today = datetime.now()
    
    if start_date is None:
        start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = (today + timedelta(days=days_forward)).strftime("%Y-%m-%d")
    
    result = []
    
    # 선물옵션 만기일 추가
    expiry_dates = get_futures_options_expiry_dates(today.year)
    for exp in expiry_dates:
        if start_date <= exp["date"] <= end_date:
            result.append(exp)
    
    for event in QUALITATIVE_EVENTS_DB:
        event_date = None
        
        if event.get("date"):
            # 고정 날짜
            event_date = event["date"]
        elif event.get("month") and event.get("day"):
            # 매년 반복되는 날짜
            year = today.year
            event_date = f"{year}-{event['month']:02d}-{event['day']:02d}"
        elif event.get("month") and event.get("flexible_date"):
            # 유동적 날짜: 해당 월의 특정 요일이나 미정
            # 여기서는 해당월 1일로 표시 (실제 날짜는 수동 업데이트 필요)
            year = today.year
            event_date = f"{year}-{event['month']:02d}-01"
            # 제목에 "(예상)" 표시
            if "(예상)" not in event["title"]:
                event["title"] = event["title"] + " (예상)"
        else:
            continue
        
        # 날짜 범위 필터
        if event_date < start_date or event_date > end_date:
            continue
        
        # 카테고리별 색상 정보 추가
        category = event.get("category", "기타")
        color = CATEGORY_COLORS.get(category, "#95a5a6")
        
        result.append({
            "date": event_date,
            "title": event["title"],
            "type": "qualitative",
            "category": category,
            "color": color,
            "description": event.get("description", ""),
            "impact_reason": event.get("impact_reason", ""),
            "source": "qualitative_knowledge_base",
        })
    
    # 날짜순 정렬
    result.sort(key=lambda x: x["date"])
    
    logger.info(f"[Qualitative] 정성 분석 일정 {len(result)}건 반환 (범위: {start_date} ~ {end_date})")
    return result


def save_qualitative_events_to_json(
    events: list[dict],
    filepath: str = None,
) -> str:
    """정성 분석 일정을 JSON 파일로 저장합니다."""
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), "qualitative_events.json")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    
    logger.info(f"[Qualitative] {len(events)}건 저장 완료 → {filepath}")
    return filepath


def load_qualitative_events_from_json(
    filepath: str = None,
) -> list[dict]:
    """JSON 파일에서 정성 분석 일정을 로드합니다."""
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), "qualitative_events.json")
    
    if not os.path.exists(filepath):
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 메인 실행
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    print("=" * 60)
    print("[Qualitative Events Generator]")
    print("=" * 60)
    
    events = get_qualitative_events(days_back=7, days_forward=90)
    
    if events:
        save_qualitative_events_to_json(events)
        
        print(f"\n[Result] 총 {len(events)}건의 정성 분석 일정")
        print("-" * 60)
        
        # 카테고리별 통계
        from collections import Counter
        cat_counts = Counter(ev["category"] for ev in events)
        print("\n[Category] 카테고리별:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            print(f"   {cat}: {count}건")
        
        # 전체 목록
        print("\n[Events] 전체 일정:")
        for ev in events:
            # 이모지 제거 (cp949 호환)
            safe_title = ev['title'].encode('ascii', errors='replace').decode('ascii')
            print(f"   [{ev['date']}] [{ev['category']}] {safe_title}")
    else:
        print("\n[Info] 해당 기간 내 정성 분석 일정이 없습니다.")
