"""메타데이터 보강 (Stage 2) — chunks_v1.json + doc_metadata.json → enriched.

doc_id로 조인해 각 청크 metadata에 검색·필터·표시용 필드를 추가한다.
- 추가: project_name, agency, agency_normalized, agency_aliases,
        announcement_date, bid_start, bid_end, announcement_no, announcement_round
- 덮어쓰기: budget_amount ← 정규화값(0원·결측 → null)  [팀 합의]
- 제외: summary (청크마다 박으면 파일 폭증 + 이미 meta_summary에 있음)
- 보존: 도혁님 기존 키(section, content_type, chunk_index, page, token_count,
        has_image_budget, pii_masked) 그대로.

실행(레포 루트에서): PYTHONIOENCODING=utf-8 python data_processing/enrich_chunks.py
출력: data/processed/chunks_v1_0622_enriched.json
"""
import json, sys, collections

sys.stdout.reconfigure(encoding="utf-8")

CHUNKS = "data/processed/chunks_v1_0622_PASS.json"   # 0622 검증 게이트 PASS본(중복0·PUA0·과세분화 해결)
META = "data/processed/doc_metadata.json"
OUT = "data/processed/chunks_v1_0622_enriched.json"  # 골든빌더·scan/manifest 입력 파일명과 정합

# 청크 metadata에 추가할 필드 (doc_metadata 키 → 청크 키). summary 제외.
ADD = ["project_name", "agency_normalized", "agency_aliases",
       "announcement_date", "bid_start", "bid_end",
       "announcement_no", "announcement_round"]


def main():
    chunks = json.load(open(CHUNKS, encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8"))

    missing = set()
    enriched = []
    for c in chunks:
        m = dict(c["metadata"])
        doc_id = m["doc_id"]
        dm = meta.get(doc_id)
        if dm is None:
            missing.add(doc_id)
            enriched.append(c)
            continue
        m["agency"] = dm["agency_raw"]            # 원본 기관명
        for k in ADD:
            m[k] = dm[k]
        m["budget_amount"] = dm["budget_krw"]     # 정규화값으로 덮어쓰기(0→null)
        enriched.append({"page_content": c["page_content"], "metadata": m})

    json.dump(enriched, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── 검증 리포트 ──
    print("=" * 60)
    print(f"보강 완료 {len(enriched)}청크 → {OUT}")
    if missing:
        print(f"⚠ 메타 매칭 실패 doc_id: {sorted(missing)}")
    else:
        print("✓ 전 청크 메타 조인 성공 (매칭 실패 0)")
    print("=" * 60)

    # 새 필드가 빠짐없이 들어갔는지
    sample = enriched[0]["metadata"]
    print("\n[보강 후 metadata 키]")
    print(" ", list(sample.keys()))

    # budget null 청크 비율 (정규화 반영 확인)
    null_budget_docs = {c["metadata"]["doc_id"] for c in enriched
                        if c["metadata"].get("budget_amount") is None}
    print(f"\n예산 null doc: {len(null_budget_docs)}건 {sorted(null_budget_docs)}")

    print("\n[meta_summary 청크 샘플 — 보강된 필터 필드]")
    for c in enriched:
        if c["metadata"]["content_type"] == "meta_summary":
            m = c["metadata"]
            print(f"  {m['doc_id']} | {m['agency']} → {m['agency_normalized']} | "
                  f"예산={m['budget_amount']} | 공개일={m['announcement_date']} | "
                  f"공고={m['announcement_no']} | aliases={m['agency_aliases']}")
            break


if __name__ == "__main__":
    main()
