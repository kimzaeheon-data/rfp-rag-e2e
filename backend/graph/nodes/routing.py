"""
routing.py
1단 라우팅 노드 — 재구성 질문의 의도를 룰 기반으로 분류해 route_a / route_c 결정.
- 체크리스트/요구사항 전수/제출서류 목록 의도 → route_c
- 그 외 단순 조회 → route_a

이 노드는 route 문자열만 기록한다. 실제 분기는 build.py의 조건부 엣지가 수행한다.
"""

# 라우트 C(체크리스트 생성) 강신호 — 이것만 있으면 조회 어미가 있어도 무조건 route_c.
_ROUTE_C_STRONG = ["체크리스트"]

# 라우트 C 리스트형 의도 키워드 — 조회 의문형으로 끝나지 않을 때만 route_c로 본다.
# ("제출 서류는 무엇인가요?" 같은 조회 질문이 route_c로 새는 것을 방지)
_ROUTE_C_LIST = [
    "요구사항 전부", "요구사항 목록", "제출서류 목록", "제출 서류 목록",
    "필수 항목", "준비물", "빠짐없이", "전체 목록", "제출 서류", "준수 사항",
]

# 조회 의문형 어미 — 리스트형 키워드가 걸려도 이 어미로 끝나면 조회로 보고 route_a.
_LOOKUP_ENDINGS = [
    "무엇인가요", "무엇입니까", "어디인가요", "얼마인가요",
    "언제인가요", "어떻게 되나요", "무엇이 있나요",
]


def routing_node(state) -> dict:
    """
    재구성 질문의 의도를 룰 기반으로 분류해 라우트를 결정한다.

    - 강신호(체크리스트)면 무조건 route_c.
    - 리스트형 의도 키워드가 있고 조회 의문형 어미가 아니면 route_c.
    - 그 외(단순 조회)는 route_a.

    Returns:
        dict: route 필드("route_a" 또는 "route_c")
    """
    # 문서가 이미 선택된 경우(2단계 진입): 의도 분류 없이 바로 route_c로 보낸다.
    # (UI에서 후보 문서를 클릭 → selected_doc_id가 실려 재요청된 경우)
    if state.get("selected_doc_id"):
        return {"route": "route_c"}

    # 재구성 질문 우선, 없으면 원문 사용
    q = state.get("rewritten_question") or state["question"]

    # 강신호: 조회 어미와 무관하게 route_c
    if any(kw in q for kw in _ROUTE_C_STRONG):
        return {"route": "route_c"}

    # 리스트형 의도 + 조회 의문형 어미가 아님 → route_c
    if any(kw in q for kw in _ROUTE_C_LIST) and not any(e in q for e in _LOOKUP_ENDINGS):
        return {"route": "route_c"}

    return {"route": "route_a"}