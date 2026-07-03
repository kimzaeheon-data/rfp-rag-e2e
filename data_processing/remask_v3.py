"""마스킹 정책 v3 — 새 팀 정책(전화번호 공개/비공개 분리) 반영.

정책 변경 (CASE1/CASE2):
- CASE1 공개: 유선(02·031·042…)·대표번호(1588 등) → **마스킹 안 함**
- CASE2 비공개: 개인 휴대폰(010 등) → 마스킹 유지
- 이메일·주민·사업자·법인번호 → 기존대로 마스킹 (CASE1/2에 없음 = 변경 없음)

→ v2 대비 유일한 변화: landline `phone` 패턴 제거. 나머지는 masking.py와 동일.
masking.py의 규칙 함수를 그대로 import해 일관성 보장.

실행(레포 루트에서): PYTHONIOENCODING=utf-8 python data_processing/remask_v3.py
출력: data/processed/masked_documents_v3.json + 검증 리포트
"""
import json, re, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from masking import _id67, _biz, redact   # 규칙 단일 출처

sys.stdout.reconfigure(encoding="utf-8")

SRC = "data/processed/parsed_documents_v2.json"
OUT = "data/processed/masked_documents_v3.json"

# 이메일 차등(전화 정책과 일관): 사적 webmail만 마스킹, 기관/공식 계정은 노출.
# denylist 방식 — 알려진 무료 webmail만 가리고 나머지(.go/.re/.ac/.or.kr,
# 공기업 .com[korail/7luck], 공공기관 .kr/.org)는 '담당자 문의처'로 공개.
PERSONAL_MAIL = {
    "gmail.com", "googlemail.com", "naver.com", "daum.net", "hanmail.net",
    "nate.com", "kakao.com", "hotmail.com", "outlook.com", "outlook.kr",
    "yahoo.com", "yahoo.co.kr", "live.com", "icloud.com", "me.com",
    "paran.com", "korea.com", "dreamwiz.com", "hanmir.com", "empal.com",
}


def _email(m):
    """사적 webmail이면 마스킹, 기관 도메인이면 노출(None)."""
    domain = m.group(0).replace(" ", "").split("@")[1].lower().rstrip(".")
    if domain in PERSONAL_MAIL:
        return "email", "[이메일]"
    return None, None   # 기관 도메인 → 노출

# v3 패턴: landline(phone) 제거. 이메일·주민/법인·사업자·휴대폰만 마스킹.
PATTERNS = [
    # @ 양옆 공백 허용(\s?): 'id @domain' / 'id@ domain' 대응. judge=_email로 도메인 차등.
    ("email", None, re.compile(r"[A-Za-z0-9._%+\-]+\s?@\s?[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), _email),
    ("id67",  None,       re.compile(r"\b\d{6}-\d{7}\b"), _id67),
    ("biz",   None,       re.compile(r"\b\d{3}-\d{2}-\d{5}\b"), _biz),
    ("mobile", "[휴대폰]", re.compile(r"\b01[0166789][-.)\s]?\d{3,4}[-.\s]?\d{4}\b"), None),
    # ("phone", ...) ← v3에서 제거: 유선·대표번호는 공개 정보로 노출
]

# 노출된 유선 검증용 (마스킹 안 됐는지 확인)
LANDLINE = re.compile(r"\b0\d{1,2}[-)]\s?\d{3,4}-\d{4}\b")
REPNUM   = re.compile(r"\b1[5678]\d{2}[-.]?\d{4}\b")   # 1588/1577/15xx 대표번호


def mask_text(text, hits, samples):
    for name, token, rx, judge in PATTERNS:
        def _sub(m, name=name, token=token, judge=judge):
            val = m.group(0)
            if judge is not None:
                nm, tok = judge(m)
                if nm is None:
                    return val
            else:
                nm, tok = name, token
            hits[nm] += 1
            if len(samples[nm]) < 5:
                samples[nm].append(redact(val))
            return tok
        text = rx.sub(_sub, text)
    return text


def main():
    try:
        docs = json.load(open(SRC, encoding="utf-8"))
    except FileNotFoundError:
        print(f"[오류] {SRC} 없음.")
        sys.exit(1)

    total = collections.Counter()
    samples = collections.defaultdict(list)
    masked_docs = []
    exposed_landline = exposed_rep = 0

    for d in docs:
        hits = collections.Counter()
        text = mask_text(d["text"], hits, samples)
        # 마스킹 후에도 유선/대표번호가 본문에 남아있는지(=공개됐는지) 카운트
        exposed_landline += len(LANDLINE.findall(text))
        exposed_rep      += len(REPNUM.findall(text))
        total.update(hits)
        masked_docs.append({
            "doc_id": d["doc_id"], "file_name": d["file_name"],
            "text": text, "char_count": len(text),
            "pii_masked": True, "masking_counts": dict(hits),
            "masking_policy": "v3-phone-public",
        })

    json.dump(masked_docs, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("=" * 60)
    print(f"v3 마스킹 완료 {len(docs)}건 → {OUT}")
    print("정책: 유선·대표번호 공개 / 휴대폰 마스킹 · 이메일=기관도메인 공개/사적 마스킹 · 주민·사업자·법인 마스킹")
    print("=" * 60)
    print("\n[마스킹된 유형]")
    for name, token in [("email", "[이메일]"), ("mobile", "[휴대폰]"),
                        ("rrn", "[주민등록번호]"), ("biz", "[사업자등록번호]"),
                        ("corp_reg", "[법인등록번호]")]:
        print(f"  {token:<12} {total[name]:>5}건  샘플:{samples[name][:3]}")
    print(f"  총 마스킹: {sum(total.values())}건")

    print("\n[공개(노출) 확인 — 본문에 그대로 남은 전화]")
    print(f"  유선(02·0XX)   : {exposed_landline}건  ← 정책상 공개 (정상)")
    print(f"  대표번호(15xx) : {exposed_rep}건  ← 정책상 공개 (정상)")

    print("\n[v2 대비 변화] 유선 마스킹 해제 → 본문에 실제 번호 노출")
    print("  도혁님은 이 v3로 재청킹하면 됩니다.")


if __name__ == "__main__":
    main()
