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
    # 1. 국내 주요 인사 동향
    # ============================================================
    {
        "date": None, "month": 2, "day": None,
        "title": "삼성전자 이재용 회장 사업보고/재판 일정",
        "type": "qualitative",
        "category": "인사/거취",
        "description": "이재용 삼성전자 회장 관련 사법 일정 및 주요 경영 행보",
        "impact_reason": "삼성전자 총수 리스크 발생 시 삼성전자 및 계열사 주가 변동",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 3, "day": None,
        "title": "삼성전자 정기 주주총회 (이재용 회장 복귀/경영 구상)",
        "type": "qualitative",
        "category": "인사/거취",
        "description": "삼성전자 정기 주총. 주요 안건, 배당, 이사 선임, 자사주 정책 발표.",
        "impact_reason": "삼성전자 배당 정책, 자사주 매입/소각 발표 시 주가 영향. M&A 언급 시 관련주 급등",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 1, "day": None,
        "title": "국내 주요 그룹 신년사/경영전략 발표 (삼성/SK/현대차/LG)",
        "type": "qualitative",
        "category": "인사/거취",
        "description": "주요 대기업 총수의 신년사 및 그룹 경영전략 발표",
        "impact_reason": "대규모 투자 계획 발표 시 해당 업종 및 협력사 주가 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 5, "day": None,
        "title": "젠슨 황 대만 컴퓨텍스(Computex) 기조연설 (국내 HBM/반도체 영향)",
        "type": "qualitative",
        "category": "인사/거취",
        "description": "컴퓨텍스 타이베이에서 젠슨 황 CEO 기조연설. AI/데이터센터 관련 발표.",
        "impact_reason": "AI 반도체 수요 전망 발표 시 국내 HBM/반도체주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 3, "day": None,
        "title": "젠슨 황 GTC 키노트 (엔비디아 GTC 컨퍼런스)",
        "type": "qualitative",
        "category": "인사/거취",
        "description": "엔비디아 GTC에서 젠슨 황 CEO 기조연설. 신제품/로드맵 발표.",
        "impact_reason": "차세대 GPU/반도체 발표 시 국내 반도체/AI 관련주 동반 상승",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 6, "day": None,
        "title": "한국은행 총재 기자간담회/경제전망 발표",
        "type": "qualitative",
        "category": "인사/거취",
        "description": "한은 총재의 경제전망 및 통화정책 관련 기자간담회",
        "impact_reason": "한은 총재 발언에 따라 금리 인하/인상 기대감으로 금융주 변동",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 8, "day": None,
        "title": "잭슨홀 미팅 (Jackson Hole Symposium) - 파월 의장 기조연설",
        "type": "qualitative",
        "category": "통화정책",
        "description": "캔자스시티 연은 주최 잭슨홀 경제 심포지엄. 파월 의장 기조연설.",
        "impact_reason": "2022년 잭슨홀에서 파월 매파 발언 후 코스피 3% 폭락. 매년 시장 방향성 결정",
        "source": "qualitative_knowledge_base",
    },

    # ============================================================
    # 2. 정부 정책 발표 / 투자 일정
    # ============================================================
    {
        "date": None, "month": 7, "day": None,
        "title": "하반기 경제정책방향 발표 (기획재정부)",
        "type": "qualitative",
        "category": "정부정책",
        "description": "기재부 하반기 경제정책방향. 성장률 전망, 세제 개편, 규제 완화 등.",
        "impact_reason": "법인세 감면, 규제 완화 발표 시 관련 업종 주가 급등. 부동산 정책 시 건설주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 3, "day": None,
        "title": "K-반도체 전략/지원책 발표 (정부/산업부)",
        "type": "qualitative",
        "category": "정부정책",
        "description": "반도체 클러스터 투자, 세제 지원, R&D 예산 등 반도체 산업 육성 정책",
        "impact_reason": "반도체 지원책 발표 시 삼성전자/하이닉스/소부장주 급등",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 4, "day": None,
        "title": "2차전지/배터리 산업 육성 전략 발표 (산업부)",
        "type": "qualitative",
        "category": "정부정책",
        "description": "배터리 R&D 지원, 광물 확보, IRA 대응 전략 등",
        "impact_reason": "배터리 지원 정책 발표 시 LG엔솔/SK온/삼성SDI 및 소재주 동반 상승",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 6, "day": None,
        "title": "바이오헬스 신산업 규제혁신 방안 발표",
        "type": "qualitative",
        "category": "정부정책",
        "description": "바이오/제약 규제 완화, 임상 지원, 인허가 패스트트랙 등",
        "impact_reason": "바이오 규제 완화 시 바이오/제약주 전반 상승. CMO/CDMO 기업 수혜",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 9, "day": None,
        "title": "정부 예산안 국회 제출 (R&D/국방/SOC 예산 증감)",
        "type": "qualitative",
        "category": "정부투자",
        "description": "차년도 정부 예산안 국회 제출. 부처별 R&D 예산, SOC 예산, 방산 예산 증감.",
        "impact_reason": "방산/SOC 예산 증액 시 방산주, 건설주 상승. R&D 삭감 시 과학기술주 하락",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 12, "day": None,
        "title": "국회 예산안 심사/확정 (예산결산특별위원회)",
        "type": "qualitative",
        "category": "정부투자",
        "description": "국회 예결위 심사 및 본회의 예산안 확정",
        "impact_reason": "최종 예산 확정 시 수혜 업종 주가 변동",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },

    # ============================================================
    # 3. 국제 관계 / 통상
    # ============================================================
    {
        "date": None, "month": 4, "day": None,
        "title": "한미 정상회담/경제협력 회의 (방산/원전/반도체)",
        "type": "qualitative",
        "category": "국제관계",
        "description": "한미 정상회담 및 경제장관회의. 방산/원전 수출, 반도체 협력 논의.",
        "impact_reason": "방산 수출 계약 체결 시 방산주 급등. 원전 수주 시 원전주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 5, "day": None,
        "title": "한일중 정상회의/경제협력 회의",
        "type": "qualitative",
        "category": "국제관계",
        "description": "한일중 3국 정상회의. 경제통상 협력, 수출규제 완화 논의.",
        "impact_reason": "일본 수출규제 완화 시 반도체 소재주, 중국 관광 재개 시 화장품/면세점주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 10, "day": None,
        "title": "미국 대선 관련 정책 공약 발표 (관세/IRA/반도체법)",
        "type": "qualitative",
        "category": "정치",
        "description": "미국 대선 후보의 경제 공약 발표. 관세, IRA, 반도체법(CHIPS Act) 수정 가능성.",
        "impact_reason": "관세 인상 공약 시 국내 수출주 전반 하방 압력. IRA 축소 시 배터리/전기차주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 11, "day": None,
        "title": "APEC 정상회의 (한미일 경제협력 강화)",
        "type": "qualitative",
        "category": "국제관계",
        "description": "APEC 정상회의. 역내 경제협력, 공급망 재편 논의.",
        "impact_reason": "공급망 협력 발표 시 관련 산업(반도체, 배터리, 광물) 주가 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },

    # ============================================================
    # 4. 국내 회의/미팅/일정
    # ============================================================
    {
        "date": None, "month": 4, "day": None,
        "title": "국회 기획재정위원회/산업통상자원위원회 전체회의",
        "type": "qualitative",
        "category": "회의/미팅",
        "description": "국회 상임위 전체회의. 경제/산업 주요 현안 질의.",
        "impact_reason": "주요 현안 질의 및 정책 방향 제시 시 관련 업종 주가 변동",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 2, "day": None,
        "title": "반도체/배터리/디스플레이 업계 CEO 간담회 (산업부 주관)",
        "type": "qualitative",
        "category": "회의/미팅",
        "description": "산업통상자원부 주관 주요 산업별 CEO 간담회. 애로사항 및 지원책 논의.",
        "impact_reason": "업계 지원책 발표 시 해당 섹터 주가 동반 상승",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 7, "day": None,
        "title": "금융위원회/금융감독원 정례 업무보고 및 정책 발표",
        "type": "qualitative",
        "category": "회의/미팅",
        "description": "금융위/금감원의 금융정책 방향, 공매도 규제, 기업 지배구조 정책 발표",
        "impact_reason": "공매도 규제 완화/강화에 따른 증시 변동성. 기업 지배구조 개선 정책 시 지주사주 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 3, "day": None,
        "title": "공정거래위원회 대기업집단 지정/일감몰아주기 규제 발표",
        "type": "qualitative",
        "category": "회의/미팅",
        "description": "공정위 대기업집단(재벌) 지정 및 내부거래 규제 발표",
        "impact_reason": "신규 지정/규제 강화 시 해당 그룹 계열사 주가 하락 가능성",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },

    # ============================================================
    # 5. 글로벌 컨퍼런스 (국내 산업 직접 영향)
    # ============================================================
    {
        "date": None, "month": 1, "day": None,
        "title": "CES (라스베가스) - 삼성/LG/SK 하이닉스 참가",
        "type": "qualitative",
        "category": "컨퍼런스",
        "description": "CES에서 삼성/LG/SK 등 국내 기업 신제품/신기술 발표",
        "impact_reason": "CES 기간 중 국내 전자/반도체/IT주 변동성 확대",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },
    {
        "date": None, "month": 9, "day": None,
        "title": "애플 신제품 발표 (9월 이벤트) - 국내 부품주 영향",
        "type": "qualitative",
        "category": "컨퍼런스",
        "description": "애플 아이폰 신제품 발표. 국내 카메라/배터리/디스플레이 부품주 영향.",
        "impact_reason": "아이폰 출시 사이클에 따라 국내 부품주 실적/주가 영향",
        "source": "qualitative_knowledge_base",
        "flexible_date": True,
    },

    # ============================================================
    # 6. 고정 일정 (날짜 확정 - 국내 중심)
    # ============================================================
    {
        "date": "2026-07-01",
        "title": "한국 6월 수출입 동향 발표 (산업통상자원부)",
        "type": "qualitative",
        "category": "경제지표",
        "description": "6월 수출입 실적. 반도체/자동차/선박 수출 핵심 지표.",
        "impact_reason": "수출 데이터에 따라 코스피 방향성 결정. 반도체 수출 증감률 특히 중요",
        "source": "qualitative_knowledge_base",
    },
    {
        "date": "2026-07-15",
        "title": "한국은행 금융통화위원회 (기준금리 결정)",
        "type": "qualitative",
        "category": "통화정책",
        "description": "한은 금통위 7월 회의. 기준금리 결정 및 경제 전망.",
        "impact_reason": "금리 결정 및 한은 총재 발언에 따라 코스피/코스닥 방향 결정",
        "source": "qualitative_knowledge_base",
    },
]

# ============================================================
# 카테고리별 색상 매핑
# ============================================================
CATEGORY_COLORS = {
    "인사/방문": "#e67e22",      # 주황
    "인사/거취": "#e67e22",      # 주황 (통합)
    "통화정책": "#c0392b",       # 진빨강
    "정부정책": "#8e44ad",       # 보라
    "정부투자": "#8e44ad",       # 보라 (통합)
    "국제관계": "#2c3e50",       # 진남색
    "정치": "#7f8c8d",           # 회색
    "컨퍼런스": "#16a085",       # 청록
    "경제지표": "#2980b9",       # 파랑
    "회의/미팅": "#d35400",      # 진주황
    "파생상품": "#2c3e50",       # 진남색
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
