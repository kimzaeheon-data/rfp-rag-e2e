"""
route_c.py
라우트 C 노드 — 선택된 문서(selected_doc_id)에서 의무 요구사항을 추출해 체크리스트 생성.
'검색'이 아니라 '문서 전체 추출'이라는 점이 라우트 A와 다르다(질문이 아니라 doc_id로 동작).

2단계 동작:
- 문서 미선택(자연어 진입): 질문으로 검색해 후보 문서 리스트(candidate_docs)만 반환한다.
  무거운 추출을 미루고, UI에서 사용자가 문서를 고르게 한다.
- 문서 선택됨(selected_doc_id): 그 문서로 체크리스트를 만든다.
  추출 캐시가 있으면 캐시에서 로드하고(비용 0·즉시), 없으면 generate_checklist로 실추출한다.

주의: generate_checklist는 gpt-5-mini를 호출해 문서당 수 분·비용이 드는 무거운 작업이다.
"""
import io
import json
import os
from typing import Optional

from data_processing.example_generate_checklist import generate_checklist
from backend.pipeline import retrieve   # 자연어 진입 시 질문→문서 검색(route_a와 동일 함수 재사용)

# 후보 문서 최대 개수(1단계에서 사용자에게 보여줄 문서 수). doc_id 중복 제거 후 상위 N개.
_CANDIDATE_TOP_N = 3

# 추출 캐시 경로(프로젝트 루트 기준 상대경로). 이 경로에 DOC_xxx_extracted.json이 있으면
# 실추출 대신 캐시를 읽는다(비용 0·즉시). 캐시가 없으면 라이브 추출로 폴백한다.
_CACHE_DIR = os.path.join("data", "eval_cache", "extractions")


def _load_from_cache(doc_id: str) -> Optional[dict]:
    """
    추출 캐시(DOC_xxx_extracted.json)를 서비스 스키마로 변환해 반환한다.
    캐시 파일이 없으면 None을 반환한다(→ 라이브 추출로 폴백).

    캐시는 평가용 경량 스키마라 서비스 스키마와 필드명이 다르다:
      item→text, primary_category→category, match_status→status.
      flags는 캐시에 없어 기본값(전부 false)으로 채운다.

    Args:
        doc_id: 대상 문서 ID
    Returns:
        {items, status} 또는 None(캐시 없음)
    """
    fp = os.path.join(_CACHE_DIR, f"{doc_id}_extracted.json")
    if not os.path.exists(fp):
        return None

    with io.open(fp, encoding="utf-8") as f:   # 한글 → 반드시 utf-8
        raw = json.load(f)

    items = []
    for it in raw["items"]:
        items.append({
            "text": it["item"],
            "category": it["primary_category"],
            "evidence": [
                {"chunk_id": ev["chunk_id"], "quote": ev["quote"], "status": ev["match_status"]}
                for ev in it["evidence"]
            ],
            "flags": {"condition": False, "numeric": False, "deadline": False},  # 캐시엔 flags 없음
        })
    return {"items": items, "status": raw["manifest"]["status"]}


def route_c_node(state) -> dict:
    """
    라우트 C: 문서 선택 여부로 두 가지로 동작한다(2단계).

    - selected_doc_id 없음: 질문으로 검색해 후보 문서 리스트만 반환(candidate_docs).
      추출기를 부르지 않고 route_status="awaiting_doc_selection"으로 단락한다.
    - selected_doc_id 있음: 그 문서로 체크리스트 생성. 캐시 우선(없으면 라이브 추출).
      추출 status(complete_verified / complete_with_review / partial / failed /
      doc_not_found)를 route_status에 실어 answer_generation이 분기하게 한다.

    Returns:
        dict: checklist_items 또는 candidate_docs, route_status
    """
    doc_id = state.get("selected_doc_id")

    # (1단계) 문서 미선택: 질문으로 검색해 후보 문서만 반환한다(무거운 추출은 미룸).
    if not doc_id:
        query = state.get("rewritten_question") or state["question"]
        config = state.get("config", {})
        docs = retrieve(query, config)          # route_a와 동일한 검색 경로

        # doc_id 중복 제거하며 상위 N개 후보 구성(같은 문서의 여러 청크가 겹치지 않게)
        candidates = []
        seen = set()
        for d in docs:
            did = d.metadata.get("doc_id")
            if did and did not in seen:
                seen.add(did)
                candidates.append({
                    "doc_id": did,
                    "file_name": d.metadata.get("file_name"),
                    "project_name": d.metadata.get("project_name"),
                    "agency": d.metadata.get("agency"),
                })
            if len(candidates) >= _CANDIDATE_TOP_N:
                break

        return {"candidate_docs": candidates, "route_status": "awaiting_doc_selection"}

    # (2단계) 문서 선택됨: 캐시 우선 → 없으면 라이브 추출(무거운 LLM 호출)
    cached = _load_from_cache(doc_id)
    result = cached if cached is not None else generate_checklist(doc_id)
    return {
        "checklist_items": result.get("items", []),
        "route_status": result.get("status", "failed"),
    }