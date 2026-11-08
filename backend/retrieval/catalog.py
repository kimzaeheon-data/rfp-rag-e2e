"""Exact list and count queries over the documents in the loaded RFP index."""

import re
import unicodedata
from datetime import date

from langchain_core.documents import Document

_BUSINESS_LIST = re.compile(
    r"(?:모든|전체)\s*(?:사업|공고)|"
    r"(?:사업|공고)(?:을|를|은|는|이|가|의)?\s*"
    r"(?:(?:예산|사업\s*금액|공개일|입찰\s*(?:마감일|시작일))(?:이|가|을|를)?\s*"
    r"(?:(?:큰|작은|높은|낮은|빠른|이른|늦은)\s*순(?:서)?(?:대로|으로)?|"
    r"(?:오름차순|내림차순)(?:으로)?)\s*)?"
    r"(?:모두|전부|전체|목록|리스트|총\s*몇|몇\s*(?:건|개)|건수|개수)"
)
_COUNT = re.compile(r"몇\s*(?:건|개)|건수|개수")
_DATE_LABELS = {"announcement_date": "공개일", "bid_start": "입찰 시작일", "bid_end": "입찰 마감일"}


def catalog_operation(question: str) -> str | None:
    """Identify explicit whole-catalog business list and count requests."""
    if not _BUSINESS_LIST.search(question):
        return None
    return "count" if _COUNT.search(question) else "list"


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _field(doc: Document, key: str) -> int | str | None:
    value = doc.metadata.get(key)
    if value is None or isinstance(value, bool):
        return None
    if key == "budget_amount":
        try:
            return int(str(value).replace(",", ""))
        except ValueError:
            return None
    if key in _DATE_LABELS:
        try:
            return date.fromisoformat(str(value)[:10]).isoformat()
        except ValueError:
            return None
    if isinstance(value, str):
        return _normalized(value) or None
    return None


def _summary(doc: Document, date_field: str | None) -> str:
    meta = doc.metadata
    name = meta.get("project_name") or meta.get("file_name") or meta["doc_id"]
    parts = [name]
    agency = meta.get("agency") or meta.get("agency_normalized")
    if agency:
        parts.append(str(agency))
    budget = _field(doc, "budget_amount")
    if budget is not None:
        parts.append(f"예산 {budget:,}원")
    if date_field in _DATE_LABELS and (value := _field(doc, date_field)):
        parts.append(f"{_DATE_LABELS[date_field]} {value}")
    return " · ".join(parts)


def catalog_response(operation: str, parsed: dict, load_vectorstore) -> dict:
    """Evaluate structured conditions on one record per doc_id and render every match."""
    filters = {k: parsed[k] for k in ("agency", "budget_min", "budget_max", "date_min", "date_max")
               if parsed.get(k) is not None}
    scope = parsed.get("catalog_scope")
    date_field = parsed.get("date_field")
    sort_by, sort_order = parsed.get("sort_by"), parsed.get("sort_order")
    if (
        scope not in ("all", "filtered")
        or (scope == "filtered") != bool(filters)
        or parsed.get("project_name")
        or (({"date_min", "date_max"} & filters.keys()) and date_field not in _DATE_LABELS)
        or bool(sort_by) != bool(sort_order)
    ):
        return {
            "answer": "전수 조회 조건을 확정하지 못했습니다. 발주기관, 예산 범위 또는 날짜 범위를 명시해 주세요.",
            "route_status": "catalog_unsupported",
        }

    vectorstore = load_vectorstore()
    by_id = {}
    for storage_id in vectorstore.index_to_docstore_id.values():
        doc = vectorstore.docstore.search(storage_id)
        if not isinstance(doc, Document) or not (doc_id := _field(doc, "doc_id")):
            return {
                "answer": "인덱스에 사업 식별 정보가 누락되어 전수 조회 결과를 확정할 수 없습니다.",
                "route_status": "catalog_unavailable",
            }
        if doc_id not in by_id or doc.metadata.get("content_type") == "meta_summary":
            by_id[doc_id] = doc
    if not by_id:
        return {"answer": "조회할 사업이 인덱스에 등록되어 있지 않습니다.", "route_status": "catalog_unavailable"}

    agency = filters.get("agency")
    if agency:
        agency = _normalized(agency)
        exact = {_field(doc, "agency_normalized") for doc in by_id.values()}
        if agency not in exact:
            candidates = set()
            for doc in by_id.values():
                aliases = doc.metadata.get("agency_aliases") or ()
                if isinstance(aliases, str):
                    aliases = (aliases,)
                labels = (*aliases, doc.metadata.get("agency"))
                normalized = _field(doc, "agency_normalized")
                if normalized and any(isinstance(label, str) and _normalized(label) == agency for label in labels):
                    candidates.add(normalized)
            if len(candidates) != 1:
                return {
                    "answer": "요청하신 발주기관을 하나로 확인할 수 없습니다. 정식 기관명으로 다시 조회해 주세요.",
                    "route_status": "catalog_unknown_agency",
                }
            agency = candidates.pop()

    conditions = []
    if agency:
        conditions.append(("agency_normalized", agency, agency))
    if "budget_min" in filters or "budget_max" in filters:
        conditions.append(("budget_amount", filters.get("budget_min"), filters.get("budget_max")))
    if "date_min" in filters or "date_max" in filters:
        conditions.append((date_field, filters.get("date_min"), filters.get("date_max")))

    matches = []
    unknown = 0
    for doc_id in sorted(by_id):
        doc = by_id[doc_id]
        missing = False
        for key, lower, upper in conditions:
            value = _field(doc, key)
            if value is None:
                missing = True
            elif (lower is not None and value < lower) or (upper is not None and value > upper):
                break
        else:
            if missing:
                unknown += 1
            else:
                matches.append(doc)

    if sort_by:
        present, missing_order = [], []
        for doc in matches:
            value = _field(doc, sort_by)
            if value is None:
                missing_order.append(doc)
            else:
                present.append((value, doc))
        present.sort(key=lambda row: row[0], reverse=sort_order == "desc")
        matches = [doc for _, doc in present] + missing_order

    display_date = date_field or (sort_by if sort_by in _DATE_LABELS else None)
    summaries = [_summary(doc, display_date) for doc in matches]
    lines = [f"인덱스에 등록된 사업 {len(by_id)}건 중 조건에 맞는 사업은 {len(matches)}건입니다."]
    if unknown:
        lines.append(f"필수 메타데이터가 없어 조건을 확인할 수 없는 {unknown}건은 집계에서 제외했습니다.")
    if operation == "list" and summaries:
        lines.append("")
        lines.extend(f"{i}. {summary}" for i, summary in enumerate(summaries, 1))

    sources = [Document(page_content=summary, metadata={**doc.metadata, "section": "사업 메타데이터"})
               for doc, summary in zip(matches, summaries)]
    return {"answer": "\n".join(lines), "docs": sources, "route_status": "catalog_ok"}
