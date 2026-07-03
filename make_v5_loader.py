import json, io
gold = json.load(io.open("data/processed/v5_gold_labels.json", encoding="utf-8"))
questions = []
for did, dv in gold["docs"].items():
    expected = [lab["item"] for lab in dv.get("labels", []) if lab.get("expected_scope") == "in_scope"]
    questions.append({"id": f"V5_{did}", "answer_doc_id": did, "expected_items": expected, "q_subtype": "", "item_match_mode": "item"})
io.open("evaluation/v5_gold_questions.json", "w", encoding="utf-8", newline="").write(json.dumps({"questions": questions}, ensure_ascii=False, indent=2))
total = sum(len(q["expected_items"]) for q in questions)
print(f"문서 {len(questions)} / 총 expected(in_scope): {total}")
for q in questions: print(f"  {q['answer_doc_id']}: {len(q['expected_items'])}")
