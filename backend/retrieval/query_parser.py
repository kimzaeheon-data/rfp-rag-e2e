"""
query_parser.py
사용자 질문에서 메타데이터 필터/정렬 조건을 추출합니다.

추출 필드:
    agency        : 발주기관명
    project_name  : 사업명
    budget_min    : 예산 하한 (원 단위 정수)
    budget_max    : 예산 상한 (원 단위 정수)
    date_field    : 정렬/필터 기준 날짜 필드 (announcement_date | bid_end | bid_start)
    date_min      : 날짜 하한 (YYYY-MM-DD)
    date_max      : 날짜 상한 (YYYY-MM-DD)
    sort_by       : 정렬 기준 필드 (budget_amount | announcement_date | bid_end)
    sort_order    : 정렬 방향 (asc | desc)

사용법:
    from query_parser import extract_metadata

    extract_metadata("예산이 1억원 이상인 사업을 모두 알려주세요.")
    # → {"budget_min": 100000000, "sort_by": None, ...}

    extract_metadata("예산이 가장 큰 사업은?")
    # → {"sort_by": "budget_amount", "sort_order": "desc", ...}
"""

import json
from datetime import date
from openai import OpenAI

_SYSTEM_PROMPT = """\
당신은 공공 입찰 RFP 검색 시스템의 쿼리 분석기입니다.
사용자 질문을 분석해 아래 필드를 추출하고 JSON으로만 출력하세요.

추출 필드:
- agency       : 발주기관명. 없으면 null.
- project_name : 사업명. 없으면 null.
- budget_min   : 예산 하한 (원 단위 정수). 없으면 null. 예) "1억원 이상" → 100000000
- budget_max   : 예산 상한 (원 단위 정수). 없으면 null. 예) "5억원 이하" → 500000000
- date_field   : 날짜 필터 기준 필드. announcement_date | bid_end | bid_start | null
- date_min     : 날짜 하한 (YYYY-MM-DD). 없으면 null.
- date_max     : 날짜 상한 (YYYY-MM-DD). 없으면 null.
- sort_by      : 정렬 기준. budget_amount | announcement_date | bid_end | null
- sort_order   : 정렬 방향. asc | desc | null. "가장 큰/높은/늦은" → desc, "가장 작은/낮은/먼저" → asc

규칙:
- JSON만 출력하세요. 설명 없이.
- 값이 없으면 null.
- 기관명/사업명은 질문에 나온 표현 그대로.
- 금액 단위 변환: 1억=100000000, 5억=500000000, 10억=1000000000

예시:
질문: "예산이 1억원 이상인 사업을 모두 알려주세요."
출력: {"agency": null, "project_name": null, "budget_min": 100000000, "budget_max": null, "date_field": null, "date_min": null, "date_max": null, "sort_by": null, "sort_order": null}

질문: "예산이 가장 큰 사업은 무엇인가요?"
출력: {"agency": null, "project_name": null, "budget_min": null, "budget_max": null, "date_field": null, "date_min": null, "date_max": null, "sort_by": "budget_amount", "sort_order": "desc"}

질문: "가장 먼저 공개된 사업은 무엇인가요?"
출력: {"agency": null, "project_name": null, "budget_min": null, "budget_max": null, "date_field": "announcement_date", "date_min": null, "date_max": null, "sort_by": "announcement_date", "sort_order": "asc"}
"""

_EMPTY_META = {
    "agency": None,
    "project_name": None,
    "budget_min": None,
    "budget_max": None,
    "date_field": None,
    "date_min": None,
    "date_max": None,
    "sort_by": None,
    "sort_order": None,
}


def extract_metadata(question: str, *, timeout: float | None = None) -> dict:
    """
    질문에서 필터/정렬 조건을 추출합니다.

    Args:
        question: 사용자 질문
        timeout: 서비스에서 사용할 API 타임아웃. 지정하면 SDK 재시도를 생략합니다.

    Returns:
        {agency, project_name, budget_min, budget_max,
         date_field, date_min, date_max, sort_by, sort_order}
    """
    user_content = f"{_SYSTEM_PROMPT}\n\n질문: {question}"

    client = OpenAI() if timeout is None else OpenAI(timeout=timeout, max_retries=0)
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": user_content}],
        max_completion_tokens=4000,
    )

    raw = (response.choices[0].message.content or "").strip()

    # 마크다운 코드블록 제거
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        metadata = dict(_EMPTY_META)
        for key in metadata:
            value = result.get(key)
            if value is None:
                continue
            if key in ("budget_min", "budget_max"):
                if type(value) is not int or value < 0:
                    raise ValueError(f"Invalid {key}")
            else:
                if not isinstance(value, str):
                    raise ValueError(f"Invalid {key}")
                value = value.strip() or None
                if value and key in ("date_min", "date_max"):
                    value = date.fromisoformat(value).isoformat()
            metadata[key] = value

        if metadata["date_field"] not in (None, "announcement_date", "bid_end", "bid_start"):
            raise ValueError("Invalid date_field")
        if metadata["sort_by"] not in (None, "budget_amount", "announcement_date", "bid_end"):
            raise ValueError("Invalid sort_by")
        if metadata["sort_order"] not in (None, "asc", "desc"):
            raise ValueError("Invalid sort_order")
        return metadata
    except ValueError:
        print("[query_parser] 검색 조건 응답을 해석하지 못해 기본 검색을 사용합니다.")
        return dict(_EMPTY_META)
