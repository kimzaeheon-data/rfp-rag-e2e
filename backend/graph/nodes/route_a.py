"""
route_a.py
라우트 A 노드 — 재구성 질문으로 검색해 청크(Document)를 회수한다(단순 RAG 경로).
생성은 공통 노드(answer_generation)에서 하므로, 여기서는 검색만 수행한다.

재구성 질문에서 검색 조건을 추출해 통합 파이프라인의 retrieve()에 전달한다.
"""
import logging

from openai import OpenAIError

from backend.pipeline import get_vectorstore, retrieve
from backend.retrieval.catalog import catalog_operation, catalog_response
from backend.retrieval.query_parser import extract_metadata

logger = logging.getLogger(__name__)


def route_a_node(state) -> dict:
    """
    재구성 질문으로 FAISS 검색을 수행해 Document를 회수한다.

    - 재구성 질문(rewritten_question)으로 검색해야 followup이 맞는 청크를 회수한다.
    - (결정2) Document를 통째로 state.docs에 싣고, str·dict 변환은 최종 get_ai_response에서.

    Returns:
        dict: docs(list[Document]), route_status, search_metadata
    """
    # 재구성 질문 우선, 없으면 원문
    query = state.get("rewritten_question") or state["question"]
    config = state.get("config", {})
    metadata = {}
    if config.get("use_query_metadata", True):
        operation = catalog_operation(query)
        parsed = {}
        try:
            parsed = extract_metadata(query, timeout=10.0, for_catalog=bool(operation))
        except OpenAIError as exc:
            logger.warning("검색 조건 추출 실패(%s)", type(exc).__name__)
        if operation:
            return catalog_response(operation, parsed, get_vectorstore)
        if parsed:
            # 사업명 부분 문자열 필터는 기존 실험에서 정답 청크를 과하게 제외했다.
            metadata = {key: value for key, value in parsed.items()
                        if key != "project_name" and value is not None}
            if not metadata.get("date_field"):
                metadata.pop("date_min", None)
                metadata.pop("date_max", None)
            if not (metadata.get("date_min") or metadata.get("date_max")):
                metadata.pop("date_field", None)
            if not (metadata.get("sort_by") and metadata.get("sort_order")):
                metadata.pop("sort_by", None)
                metadata.pop("sort_order", None)

    docs = retrieve(query, config, metadata=metadata)
    status = "ok" if docs else "empty"
    return {"docs": docs, "route_status": status, "search_metadata": metadata}
