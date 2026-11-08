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

_CATALOG_RULES = """\
이번 질문은 사업 목록 또는 사업 건수 조회입니다. 기존 필드 외에 catalog_scope를 출력하세요.
- all: 사용자가 등록된 모든 사업을 아무 조건 없이 조회합니다.
- filtered: 조회 조건 전체를 한 기관명, 원 단위 예산 범위, 한 종류의 날짜 범위의 AND 조합으로 표현할 수 있습니다.
- unsupported: 조건이 불명확하거나 위 조합으로 표현할 수 없습니다.
사업 유형, 본문에 등장하는 키워드, 기관 유형(예: 대학교), 복수 기관,
제외 조건, OR 조건, 상위 N건 또는 목록/건수 이외의 작업은 unsupported입니다.
조건 일부라도 표현할 수 없으면 unsupported로 표시하세요. project_name은 null로 두세요.
예산 초과·미만은 원 단위로 각각 +1·-1을 적용해 포함 경계로 바꾸세요.
날짜의 이후·이전이 기준일을 포함하지 않는 경우 다음 날·전날을 경계로 사용하세요.
기준일이 확정되지 않은 상대 날짜는 unsupported입니다.
"""


def extract_metadata(question: str, *, timeout: float | None = None, for_catalog: bool = False) -> dict:
    """
    질문에서 필터/정렬 조건을 추출합니다.

    Args:
        question: 사용자 질문
        timeout: 서비스에서 사용할 API 타임아웃. 지정하면 SDK 재시도를 생략합니다.
        for_catalog: 사업 전수 조회에서 지원 가능한 조건인지 함께 판정합니다.

    Returns:
        {agency, project_name, budget_min, budget_max,
         date_field, date_min, date_max, sort_by, sort_order}
    """
    prompt = _SYSTEM_PROMPT + ("\n" + _CATALOG_RULES if for_catalog else "")
    user_content = f"{prompt}\n\n질문: {question}"

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
        if for_catalog:
            scope = result.get("catalog_scope")
            if scope not in ("all", "filtered", "unsupported"):
                raise ValueError("Invalid catalog_scope")
            metadata["catalog_scope"] = scope
        return metadata
    except ValueError:
        print("[query_parser] 검색 조건 응답을 해석하지 못해 기본 검색을 사용합니다.")
        return dict(_EMPTY_META)
