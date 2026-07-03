# -*- coding: utf-8 -*-
# V5 정식 채점 — 문서 단위 전수 (카테고리 필터 없음)
# 사용:
#   python evaluation/run_v5_scoring.py                    # 전체 8문서
#   python evaluation/run_v5_scoring.py --doc=DOC_061      # 1문서만 (스모크)
#   python evaluation/run_v5_scoring.py --snapshot         # 결과 스냅샷 저장
import sys, json, io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import eval_route_c as base
base.GOLD_VERSION = "v5.0"   # Decision Pair Cache 키 버전 — V5로 교체 (기록 정직성)

from route_c_evaluate import evaluate_question, summarize, save_snapshot
from embed_cache import EmbedCache
from openai import OpenAI
from dotenv import load_dotenv

V5_QUESTIONS = ROOT / "evaluation" / "v5_gold_questions.json"


def main():
    args = sys.argv[1:]
    k = 8
    for a in args:
        if a.startswith("--k="):
            k = int(a.split("=")[1])
    only = [a.split("=")[1] for a in args if a.startswith("--doc=")]
    do_snapshot = "--snapshot" in args

    load_dotenv()
    client = OpenAI()
    embed = EmbedCache(client=client)
    dcache = base.DecisionPairCache()

    data = json.load(io.open(V5_QUESTIONS, encoding="utf-8"))
    qs = data["questions"]
    if only:
        qs = [q for q in qs if q["answer_doc_id"] in only]
    if not qs:
        print("해당 문서 없음:", only)
        return

    print(f"V5 정식 채점: {len(qs)}문서, k={k}, gold=v5.0, filter=none(문서 전수)")
    scores = []
    for q in qs:
        ext = base.get_extraction(q["answer_doc_id"])
        s = evaluate_question(q, ext, embed, dcache, base.call_matcher, client,
                              k=k, filter_mode="none")
        scores.append(s)
        print(f"  {s.qid} cov={s.item_coverage:.3f} prec={s.item_precision:.3f} "
              f"expected={len(q['expected_items'])} denom={s.n_extracted}/{s.n_extracted_raw} "
              f"calls={s.matcher_calls} hits={s.matcher_cache_hits} "
              f"review={s.n_review_expected} unresolved={s.n_unresolved_expected}")

    print(f"\n요약: {summarize(scores)}")
    print(f"임베딩 API 호출 텍스트 수: {embed.api_calls}")
    if do_snapshot:
        save_snapshot(scores, k=k)
        print("스냅샷 저장 완료 (evaluation/reports/)")


if __name__ == "__main__":
    main()
