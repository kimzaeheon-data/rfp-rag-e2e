"""
re_retrieve.py
재검색 노드 — grade가 insufficient로 판정했을 때 호출되는 '다시 검색' 동작.
agentic 재검색 루프의 '재시도' 부분(루프 배선은 build.py의 조건부 엣지가 수행).

질문에서 추출한 조건이 있으면 후보 범위를 넓히되 조건은 유지한다.
조건이 없는 질문은 설정의 precision/recall 전략으로 재검색한다.
"""
from collections import Counter
from langchain_core.documents import Document
from backend.pipeline import get_vectorstore   # 캐싱된 FAISS 벡터스토어(1회 로드)
from retriever import MMR_FETCH_K, MMR_LAMBDA, get_retriever, re_retrieve_fn, re_retrieve_recall_fn


# ── 재검색 슬롯(입출력 계약) ──────────────────────────────────────────────
# 슬롯 계약: (query, prev_docs, attempt, config) -> list[Document]
# config["re_retrieve_strategy"] 값으로 재검색 전략을 고른다.
#   "precision" : 1차 결과의 다수 기관/사업으로 좁혀 재검색(re_retrieve_fn)
#   "recall"    : 필터 해제 + 다양성 강화로 넓게 재검색(re_retrieve_recall_fn)
# 기본값 "recall": 부실한 1차를 안고 좁히면 더 빗나갈 수 있어 넓히기를 기본으로 둔다.
# 재검색 함수(retriever.py)는 원본 그대로 사용하고, 입출력 형식은 이 어댑터가 흡수한다.
def _adapt_re_retrieve(query: str, prev_docs: list, attempt: int, config: dict) -> list[Document]:
    """재검색 함수(precision/recall)를 슬롯 계약에 맞게 감싼다."""
    strategy = config.get("re_retrieve_strategy", "recall")
    vectorstore = get_vectorstore()

    if strategy == "precision":
        # 1차 결과 문서 메타에서 가장 빈번한 agency/project_name을 추출해 필터로 사용
        agency_counter = Counter(
            d.metadata["agency_normalized"]
            for d in prev_docs
            if d.metadata.get("agency_normalized")
        )
        project_counter = Counter(
            d.metadata["project_name"]
            for d in prev_docs
            if d.metadata.get("project_name")
        )
        agency = agency_counter.most_common(1)[0][0] if agency_counter else None
        project_name = project_counter.most_common(1)[0][0] if project_counter else None
        # precision 함수는 (docs, agency_skipped) 튜플 반환 → docs만 취한다
        docs, _ = re_retrieve_fn(
            query=query,
            vectorstore=vectorstore,
            agency=agency,
            project_name=project_name,
        )
        return docs

    # 기본: recall 확대(필터 해제 + 다양성 강화)
    return re_retrieve_recall_fn(query=query, vectorstore=vectorstore)


def re_retrieve_node(state) -> dict:
    """
    grade가 insufficient로 판정한 경우, 질문을 다시 검색해 docs를 교체한다.

    Returns:
        dict: docs(재검색 결과로 교체), route_status
    """
    query = state.get("rewritten_question") or state["question"]
    prev_docs = state.get("docs", [])
    attempt = state.get("retry_count", 1)   # grade에서 증가시킨 시도 횟수
    config = state.get("config", {})

    metadata = state.get("search_metadata")
    if metadata:
        # 명시 조건은 유지하고, 검색 후보를 넓혀 첫 검색에서 놓친 근거를 찾는다.
        new_docs = get_retriever(
            query,
            get_vectorstore(),
            k=config.get("top_k", 5),
            fetch_k=MMR_FETCH_K * 2,
            lambda_mult=MMR_LAMBDA if config.get("re_retrieve_strategy") == "precision" else 0.7,
            strict_agency=True,
            **metadata,
        )
        if not new_docs:
            new_docs = prev_docs
    else:
        new_docs = _adapt_re_retrieve(query, prev_docs, attempt, config)
    
    status = "ok" if new_docs else "empty"
    return {"docs": new_docs, "route_status": status}
