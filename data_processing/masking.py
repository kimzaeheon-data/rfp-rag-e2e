"""재파싱 본문(parsed_documents.json)의 PII 마스킹.
NDA: 로컬 전용. 보고 출력 시 실제 PII는 부분 가림(redact)해서 표시.

설계 원칙:
- 가릴 것: 이메일 / 휴대폰 / 일반전화·팩스 / 주민등록번호 / 사업자등록번호
- 안 가릴 것: 공고번호(연속 11자리), 사업금액(콤마 숫자), 날짜(YYYY-MM-DD), 일반 수치
  → 정규식은 '0으로 시작 + 구분자(- 또는 ))' 같은 전화 고유 형태만 매칭해 오탐 회피.
- 적용 순서: email → 주민 → 사업자 → 휴대폰 → 일반전화
  (휴대폰을 일반전화보다 먼저: 010이 일반전화 패턴에도 걸리므로 선점 치환)
"""
import json, re, sys, io, collections

sys.stdout.reconfigure(encoding="utf-8")

SRC = "data/processed/parsed_documents_v2.json"
OUT = "data/processed/masked_documents_v2.json"   # v2(유선 포함 마스킹). 현 SSOT는 remask_v3의 v3

def _id67(m):
    """6-7자리 번호: 앞6자리가 유효 생년월일이면 주민번호, 아니면 법인등록번호."""
    s = m.group(0)
    mm, dd = int(s[2:4]), int(s[4:6])
    if 1 <= mm <= 12 and 1 <= dd <= 31:
        return "rrn", "[주민등록번호]"
    return "corp_reg", "[법인등록번호]"


def _biz(m):
    """사업자등록번호 — 000 더미(양식 템플릿)는 마스킹 제외."""
    if m.group(0).startswith("000"):
        return None, None            # 마스킹 안 함
    return "biz", "[사업자등록번호]"


# (이름, 토큰, 정규식, 판정함수)  — 위에서부터 순서대로 적용
# 판정함수 None이면 토큰 고정, 아니면 match→(name,token) 동적 결정((None,None)=skip)
PATTERNS = [
    # @ 양옆 공백 허용(\s?): 재파싱 시 'id @domain' / 'id@ domain'처럼 끼어든 공백 대응
    ("email", "[이메일]", re.compile(r"[A-Za-z0-9._%+\-]+\s?@\s?[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), None),
    ("id67",  None,       re.compile(r"\b\d{6}-\d{7}\b"), _id67),
    ("biz",   None,       re.compile(r"\b\d{3}-\d{2}-\d{5}\b"), _biz),
    # 휴대폰: 010/011/016~019 + (선택)구분자 + 3~4 + 4
    ("mobile", "[휴대폰]", re.compile(r"\b01[0166789][-.)\s]?\d{3,4}[-.\s]?\d{4}\b"), None),
    # 일반전화·팩스: 0+지역번호(1~2자리) + 구분자(- 또는 )) + 3~4 + - + 4
    ("phone", "[전화번호]", re.compile(r"\b0\d{1,2}[-)]\s?\d{3,4}-\d{4}\b"), None),
]


def redact(s):
    """보고용: 실제 PII를 앞 일부만 남기고 가림 (NDA)."""
    if "@" in s:  # email
        head = s.split("@")[0][:2]
        return head + "***@***"
    digits = re.sub(r"\D", "", s)
    return s[:3] + "*" * (len(s) - 3) if len(s) > 3 else "***"


def main():
    docs = json.load(open(SRC, encoding="utf-8"))
    total = collections.Counter()
    samples = collections.defaultdict(list)
    per_doc_hits = []

    masked_docs = []
    for d in docs:
        text = d["text"]
        hits = collections.Counter()
        for name, token, rx, judge in PATTERNS:
            def _sub(m, token=token, judge=judge):
                val = m.group(0)
                if judge is not None:
                    nm, tok = judge(m)
                    if nm is None:
                        return val            # 마스킹 제외 (원문 유지)
                else:
                    nm, tok = name, token
                hits[nm] += 1
                if len(samples[nm]) < 5:
                    samples[nm].append(redact(val))
                return tok
            text = rx.sub(_sub, text)
        total.update(hits)
        per_doc_hits.append((d["doc_id"], d["file_name"], dict(hits), sum(hits.values())))
        masked_docs.append({
            "doc_id": d["doc_id"],
            "file_name": d["file_name"],
            "text": text,                       # 마스킹 완료
            "char_count": len(text),
            "pii_masked": True,
            "masking_counts": dict(hits),
        })

    # ── 저장 ──
    json.dump(masked_docs, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 출력 유형(라벨) 고정 순서
    REPORT = [("email", "[이메일]"), ("mobile", "[휴대폰]"), ("phone", "[전화번호]"),
              ("rrn", "[주민등록번호]"), ("biz", "[사업자등록번호]"), ("corp_reg", "[법인등록번호]")]

    # ── 보고 ──
    print("=" * 60)
    print(f"문서 {len(docs)}건 마스킹 완료 → {OUT}")
    print("=" * 60)
    print("\n[유형별 마스킹 건수]")
    for name, token in REPORT:
        print(f"  {token:<12} {total[name]:>5}건   (검증샘플: {samples[name][:3]})")
    print(f"\n  총 마스킹: {sum(total.values())}건")

    print("\n[재검증 — 마스킹 후 PII 잔존(토큰 외 패턴)]")
    residual = collections.Counter()
    for md in masked_docs:
        for name, token, rx, judge in PATTERNS:
            for m in rx.finditer(md["text"]):
                if judge is not None and judge(m)[0] is None:
                    continue            # 의도적 미마스킹(더미)은 잔존으로 안 셈
                residual[name] += 1
    print(f"  잔존 합계: {sum(residual.values())}건 (0이어야 정상; 더미 000-제외)")

    print("\n[PII 포함 상위 문서 10건]")
    for did, fn, hits, n in sorted(per_doc_hits, key=lambda x: -x[3])[:10]:
        print(f"  {did} {n:>3}건 {hits}  | {fn[:30]}")

    masked_docs_with_pii = sum(1 for _, _, _, n in per_doc_hits if n > 0)
    print(f"\n  PII 발견 문서: {masked_docs_with_pii}/100건, PII 0건 문서: {100 - masked_docs_with_pii}건")


if __name__ == "__main__":
    main()
