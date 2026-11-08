"""Evaluate live /chat catalog answers against an independent metadata oracle.

Run from the repository root with --chunks and --index pointing to local data.
Questions, expected IDs and raw API responses stay in gitignored data/eval_results.
--prepare-only validates the corpus and freezes expected answers without API calls.
"""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from unittest.mock import patch


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_corpus(path):
    chunks = json.loads(path.read_text(encoding="utf-8-sig"))
    records = {}
    for chunk in chunks:
        meta = chunk["metadata"]
        if not meta.get("doc_id"):
            raise ValueError("Source chunk has no doc_id")
        if meta.get("content_type") == "meta_summary":
            if meta["doc_id"] in records:
                raise ValueError("Duplicate business summary")
            records[meta["doc_id"]] = meta
    if set(records) != {c["metadata"]["doc_id"] for c in chunks}:
        raise ValueError("Every business must have exactly one summary")
    fields = ("agency_normalized", "budget_amount", "announcement_date", "bid_start", "bid_end")
    conflicts = sum(
        any(c["metadata"].get(k) != records[c["metadata"]["doc_id"]].get(k) for k in fields)
        for c in chunks
    )
    if conflicts:
        raise ValueError(f"Metadata differs across chunks of the same business: {conflicts}")
    return chunks, records


def make_cases(records):
    agency = Counter(r["agency_normalized"] for r in records.values()).most_common(1)[0][0]
    cases = [
        ("all_list", "등록된 모든 사업을 알려줘.", {}),
        ("all_count", "등록된 사업은 총 몇 건이야?", {}, "count"),
        ("budget_100m", "예산이 1억 원 이상인 사업을 모두 알려주세요.", {"budget_min": 100_000_000}),
        ("budget_500m", "예산이 5억 원 이상인 사업을 모두 알려주세요.", {"budget_min": 500_000_000}),
        ("budget_1b", "예산이 10억 원 이상인 사업을 모두 알려주세요.", {"budget_min": 1_000_000_000}),
        ("budget_count", "예산 5억 원 이상인 사업은 총 몇 건이야?", {"budget_min": 500_000_000}, "count"),
        ("budget_range", "예산 1억 원 이상 5억 원 이하인 사업을 모두 알려줘.", {"budget_min": 100_000_000, "budget_max": 500_000_000}),
        ("budget_strict_min", "예산이 5억 원을 초과하는 사업을 모두 알려줘.", {"budget_min": 500_000_001}),
        ("budget_strict_max", "예산이 5억 원 미만인 사업을 모두 알려줘.", {"budget_max": 499_999_999}),
        ("agency_list", f"{agency}에서 발주한 사업을 모두 알려줘.", {"agency": agency}),
        ("agency_count", f"{agency}에서 발주한 사업은 총 몇 건이야?", {"agency": agency}, "count"),
        ("combined", f"{agency} 발주 사업 중 예산 1억 원 이상인 사업을 모두 알려줘.", {"agency": agency, "budget_min": 100_000_000}),
        ("date_range", "공개일이 2024년 5월 1일부터 2024년 6월 30일까지인 사업을 모두 알려줘.", {"date_field": "announcement_date", "date_min": "2024-05-01", "date_max": "2024-06-30"}),
        ("deadline_count", "입찰 마감일이 2024년 6월 1일부터 2024년 6월 30일까지인 사업은 몇 건이야?", {"date_field": "bid_end", "date_min": "2024-06-01", "date_max": "2024-06-30"}, "count"),
        ("start_date", "입찰 시작일이 2024년 1월 1일부터 2024년 12월 31일까지인 사업을 모두 알려줘.", {"date_field": "bid_start", "date_min": "2024-01-01", "date_max": "2024-12-31"}),
        ("sort_budget_desc", "예산 5억 원 이상인 사업을 예산이 큰 순서대로 모두 알려줘.", {"budget_min": 500_000_000, "sort_by": "budget_amount", "sort_order": "desc"}),
        ("sort_budget_asc", "예산 5억 원 이상인 사업을 예산 오름차순으로 모두 알려줘.", {"budget_min": 500_000_000, "sort_by": "budget_amount", "sort_order": "asc"}),
        ("sort_date", "전체 사업을 공개일이 빠른 순서대로 모두 알려줘.", {"sort_by": "announcement_date", "sort_order": "asc"}),
        ("empty", "예산 1조 원 이상인 사업을 모두 알려줘.", {"budget_min": 1_000_000_000_000}),
        ("unsupported_type", "대학교가 발주한 사업은 모두 몇 건인가요?", {}, "count", "catalog_unsupported"),
        ("unsupported_or", "예산 5억 원 이상이거나 1억 원 이하인 사업을 모두 알려줘.", {}, "list", "catalog_unsupported"),
        ("unsupported_relative", "최근 한 달에 공개된 사업을 모두 알려줘.", {}, "list", "catalog_unsupported"),
        ("paraphrase_list", "예산이 5억 원 이상인 모든 사업을 빠짐없이 보여줘.", {"budget_min": 500_000_000}),
        ("paraphrase_count", "예산 5억 원 이상인 사업이 몇 건인지 알려줘.", {"budget_min": 500_000_000}, "count"),
    ]
    return [
        {"id": row[0], "question": row[1], "filters": row[2],
         "operation": row[3] if len(row) > 3 else "list",
         "status": row[4] if len(row) > 4 else "catalog_ok"}
        for row in cases
    ]


def expected_answer(case, records):
    """Compute expected business IDs without using catalog or query-parser code."""
    if case["status"] != "catalog_ok":
        return {"doc_ids": [], "unknown": 0}
    spec = case["filters"]
    selected = []
    unknown = 0
    for doc_id, row in sorted(records.items()):
        checks = []
        if "agency" in spec:
            checks.append(row.get("agency_normalized") == spec["agency"])
        for field, low, high in (
            ("budget_amount", "budget_min", "budget_max"),
            (spec.get("date_field"), "date_min", "date_max"),
        ):
            if low not in spec and high not in spec:
                continue
            value = row.get(field)
            if value is None or value == "":
                checks.append(None)
                continue
            value = int(str(value).replace(",", "")) if field == "budget_amount" else date.fromisoformat(str(value)[:10]).isoformat()
            checks.append((low not in spec or value >= spec[low]) and (high not in spec or value <= spec[high]))
        if False in checks:
            continue
        if None in checks:
            unknown += 1
        else:
            selected.append(doc_id)
    return {"doc_ids": selected, "unknown": unknown}


def score(case, result, records, parsed=None, parser_error=None):
    expected = case["expected"]
    ids = [s.get("doc_id") for s in result.get("sources", [])]
    expected_ids, actual_ids = set(expected["doc_ids"]), set(ids)
    answer = result.get("answer", "")
    status_ok = result.get("route_status") == case["status"]
    filter_keys = {"agency", "budget_min", "budget_max", "date_min", "date_max"}
    expected_scope = "filtered" if filter_keys.intersection(case["filters"]) else "all"
    if case["status"] != "catalog_ok":
        expected_scope = "unsupported"
    parser_ok = not parser_error and (parsed or {}).get("catalog_scope") == expected_scope
    if case["status"] != "catalog_ok":
        response_pass = status_ok and not ids and bool(answer)
        return {"pass": response_pass and parser_ok, "response_pass": response_pass,
                "status_ok": status_ok, "parser_ok": parser_ok}
    match = re.search(r"조건에 맞는 사업은\s*(\d+)건", answer)
    unknown = re.search(r"조건을 확인할 수 없는\s*(\d+)건", answer)
    count_ok = bool(match) and int(match[1]) == len(expected_ids)
    unknown_ok = (int(unknown[1]) if unknown else 0) == expected["unknown"]
    numbered = re.findall(r"^\d+\. (.+)$", answer, re.MULTILINE)
    content_ok = not numbered if case["operation"] == "count" else (
        len(numbered) == len(ids) and all(
            text.startswith(str(records.get(doc_id, {}).get("project_name") or records.get(doc_id, {}).get("file_name") or doc_id))
            and re.findall(r"예산\s*([\d,]+)원", text) == (
                [f"{records[doc_id]['budget_amount']:,}"]
                if doc_id in records and records[doc_id].get("budget_amount") is not None else []
            )
            and str(records.get(doc_id, {}).get("agency") or records.get(doc_id, {}).get("agency_normalized") or "") in text
            for doc_id, text in zip(ids, numbered)
        )
    )
    sort_ok = True
    field = case["filters"].get("sort_by")
    if field:
        values = [records.get(doc_id, {}).get(field) for doc_id in ids]
        present = [v for v in values if v is not None]
        ordered = sorted(present, reverse=case["filters"]["sort_order"] == "desc")
        sort_ok = values == ordered + [None] * (len(values) - len(present))
    tp = len(expected_ids & actual_ids)
    ids_ok = expected_ids == actual_ids and len(ids) == len(actual_ids)
    checks = {"status_ok": status_ok, "ids_ok": ids_ok, "count_ok": count_ok,
              "unknown_ok": unknown_ok, "content_ok": content_ok, "sort_ok": sort_ok,
              "self_check_ok": not result.get("check_flags")}
    response_pass = all(checks.values())
    return {"pass": response_pass and parser_ok, "response_pass": response_pass,
            "parser_ok": parser_ok, **checks,
            "precision": tp / len(actual_ids) if actual_ids else (1.0 if not expected_ids else 0.0),
            "recall": tp / len(expected_ids) if expected_ids else (1.0 if not actual_ids else 0.0),
            "missing_ids": sorted(expected_ids - actual_ids),
            "extra_ids": sorted(actual_ids - expected_ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--golden", type=Path, help="Cross-check the existing Q021–Q023 answer IDs")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--tag", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("--tag must contain only letters, numbers, underscores or hyphens")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    chunks, records = load_corpus(args.chunks)
    cases = make_cases(records)
    for case in cases:
        case["expected"] = expected_answer(case, records)
    if args.golden:
        golden = {r["id"]: r for r in json.loads(args.golden.read_text(encoding="utf-8-sig"))}
        for case_id, golden_id in (("budget_100m", "Q021"), ("budget_500m", "Q022"), ("budget_1b", "Q023")):
            case = next(c for c in cases if c["id"] == case_id)
            if set(case["expected"]["doc_ids"]) != set(golden[golden_id]["answer_doc_id"]):
                raise ValueError(f"Independent oracle disagrees with {golden_id}")
    if args.limit:
        cases = cases[:args.limit]
    output = Path("data/eval_results") / f"catalog_e2e_{args.tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    payload = {"protocol": {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluator_sha256": fingerprint(Path(__file__)),
        "parser_sha256": fingerprint(
            Path(__file__).resolve().parents[1] / "retrieval" / "query_parser.py"
        ),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_chunks": len(chunks), "businesses": len(records),
        "source_sha256": fingerprint(args.chunks),
        "index_path": str(args.index.resolve()),
        "index_sha256": fingerprint(args.index / "index.faiss"),
        "docstore_sha256": fingerprint(args.index / "index.pkl"),
        "golden_sha256": fingerprint(args.golden) if args.golden else None,
        "metadata_conflict_chunks": 0, "parser_model": "gpt-5-nano",
        "parser_timeout_seconds": 10, "retriever_type": "agentic_rag",
        "entrypoint": "POST /chat via FastAPI TestClient",
        "live_llm": not args.prepare_only,
    }, "cases": cases, "rows": []}

    def save():
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    print(f"Prepared {len(cases)} questions against {len(records)} businesses", flush=True)
    if args.prepare_only:
        print(output, flush=True)
        return
    os.environ["FAISS_INDEX_PATH"] = str(args.index.resolve())
    from dotenv import load_dotenv
    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing")
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.pipeline import get_vectorstore
    from backend.graph.nodes import route_a
    from backend.graph.nodes.routing import routing_node
    from backend.retrieval.catalog import catalog_operation
    for case in cases:
        if catalog_operation(case["question"]) != case["operation"]:
            raise ValueError("Question does not use the catalog path")
        if routing_node({"question": case["question"]})["route"] != "route_a":
            raise ValueError("Question does not route to the catalog node")
    vectorstore = get_vectorstore()
    docs = [vectorstore.docstore.search(s) for s in vectorstore.index_to_docstore_id.values()]
    indexed_ids = {d.metadata.get("doc_id") for d in docs}
    if indexed_ids != set(records):
        raise ValueError("Index business IDs differ from the oracle corpus")
    for doc in docs:
        for field in ("agency_normalized", "budget_amount", "announcement_date", "bid_start", "bid_end"):
            if doc.metadata.get(field) != records[doc.metadata["doc_id"]].get(field):
                raise ValueError(f"Index metadata differs from source: {field}")
    payload["protocol"]["index_chunks"] = len(docs)
    payload["protocol"]["index_dimension"] = vectorstore.index.d
    actual_extract = route_a.extract_metadata
    with TestClient(app) as client:
        for i, case in enumerate(cases, 1):
            observed = {}

            def observe(*a, **kw):
                try:
                    parsed = actual_extract(*a, **kw)
                    observed["parsed"] = parsed
                    return parsed
                except Exception as exc:
                    observed["parser_error"] = type(exc).__name__
                    raise

            start = time.perf_counter()
            row = {"id": case["id"]}
            try:
                # Delegate to the real parser, preserving its model, timeout and output.
                with patch.object(route_a, "extract_metadata", observe):
                    response = client.post("/chat", json={"query": case["question"], "history": [], "retriever_type": "agentic_rag"})
                row["http_status"] = response.status_code
                result = response.json()
                row["response"] = result
                row["score"] = score(case, result, records, observed.get("parsed"), observed.get("parser_error"))
                row["score"]["pass"] &= response.status_code == 200
            except Exception as exc:
                row["error_type"] = type(exc).__name__
                row["score"] = {"pass": False}
            row["elapsed_sec"] = round(time.perf_counter() - start, 3)
            row.update(observed)
            payload["rows"].append(row)
            save()
            print(f"[{i}/{len(cases)}] {case['id']} {'PASS' if row['score']['pass'] else 'FAIL'} {row['elapsed_sec']}s", flush=True)
    rows = payload["rows"]
    supported_ids = {c["id"] for c in cases if c["status"] == "catalog_ok"}
    supported = [r for r in rows if r["id"] in supported_ids]
    unsupported = [r for r in rows if r["id"] not in supported_ids]
    payload["summary"] = {
        "passed": sum(r["score"]["pass"] for r in rows), "total": len(rows),
        "response_passed": sum(r["score"].get("response_pass", False) for r in rows),
        "supported_passed": sum(r["score"]["pass"] for r in supported),
        "supported_total": len(supported),
        "unsupported_passed": sum(r["score"]["pass"] for r in unsupported),
        "unsupported_total": len(unsupported),
        "mean_latency_sec": round(sum(r["elapsed_sec"] for r in rows) / len(rows), 3),
        "api_timeouts": sum(r.get("parser_error") == "APITimeoutError" for r in rows),
        "failures": [r["id"] for r in rows if not r["score"]["pass"]],
    }
    save()
    print(json.dumps(payload["summary"], ensure_ascii=False), flush=True)
    print(output, flush=True)


if __name__ == "__main__":
    main()
