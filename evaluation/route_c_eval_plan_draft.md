# 라우트 C 평가 계획서 (V4 진단 + V5 정식 채점)

> 상태: V5 정식 채점 완료 반영 (2026-07-03) / 작성: DE 도혁
> 대상: 통합 보고서(#133) 데이터팀 라우트 C 섹션 근거 문서
> 주의: 원문·골든셋·캐시 등 NDA 데이터는 리포에 포함하지 않는다(드라이브 별도 수령).

---

## 1. 목적

라우트 C(RFP 의무항목 추출)의 성능을 재현 가능하게 측정한다. 두 단계로 나눈다.
- V4 진단: 카테고리별 경향을 빠르게 파악하는 표본 진단(카테고리 필터, 문항 단위).
- V5 정식 채점: 전수 라벨(blind gold) 기반 문서 단위 전수 채점. 발표에 쓰는 정식 수치.

V4에서 Coverage만 유효 지표로 보고, Precision은 V5 전수 라벨에서 정식 측정한다. 이 분리가 V4/V5 설계의 핵심이다.

---

## 2. 데이터셋

- 문서: 공공조달 RFP 100건 중 골든셋 대상 문서.
- V5 골든셋: 문서 단위 전수 라벨(blind gold v5.0). 라벨은 아인님이 1차 작성, 경계 항목은 도혁이 독립 더블 라벨 후 규칙으로 합의(6장).
- 무결성 게이트: verify_golden_v5.py 하드 12/12 PASS (PR #126).

---

## 3. 지표 정의

- Item Coverage = 매칭된 expected 항목 수 / 전체 expected 항목 수. "놓치지 않기"를 우선하는 지표.
  - 한계: 추출 항목이 많을수록 매칭 기회가 늘어 낙관될 수 있으나, V5는 문서 전수라 이 왜곡이 작다. 분모(expected)가 고정이라 문서 간 비교가 안정적이다.
- Item Precision = 매칭된 expected 항목 수 / 추출 항목 수. "덜 뱉기"를 보는 지표.
  - 한계: 분모가 추출 항목 수라 카테고리·문서 크기에 휘둘린다. V4에서는 비교 불가였고(핵심 발견 3), V5 전수에서 처음 신뢰 가능한 값이 나온다.
- Review Burden = 사람 검토가 필요한 항목 수 / 전체 expected. 자동 판정이 애매해 사람이 봐야 하는 비율. 낮을수록 운영 부담이 작다.
- match_status(근거 검증): strict_verified / relocated_verified / cross_chunk_verified(검증 성공) / unverified_evidence(미검증) / out_of_scope_source.

---

## 4. 채점 파이프라인

- 추출: ComplianceExtractorV2 → 문서 윈도우 단위 gpt-5-mini 추출(캐시).
- 매칭: expected 항목과 추출 항목을 matcher(gpt-5-mini)로 판정(match/miss/review). Decision Pair Cache로 중복 판정 0.
- 임베딩: top-k 후보 축소용(EmbedCache).
- 캐시 재사용: 추출 캐시(재호출 0) + Decision Pair Cache(중복 판정 0) + 임베딩 캐시. 재실행해도 캐시 히트면 API 0.
- 실행: python evaluation/run_v5_scoring.py --snapshot (8문서 전수, filter=none)

---

## 5. V4 진단 결과 (전부 hard 필터 / k=8)

| 문항 | 카테고리 | Coverage | Precision | denom(n_extr/raw) | matched/review/unresolved | expected |
|------|---------|----------|-----------|-------------------|---------------------------|----------|
| Q015 | requirement | 0.857 | 0.064 | 234/335 | 6 / 1 / 0 | 7 |
| Q018 | qualification | 0.667 | 0.500 | 10/335 | 6 / 1 / 2 | 9 |
| Q019 | qualification | 0.500 | 0.667 | 12/350 | 9 / 6 / 3 | 18 |
| Q020 | scoring | 0.500 | 0.088 | 34/493 | 2 / 2 / 0 | 4 |

> 핵심 발견 1 - Coverage는 카테고리 복잡도에 좌우. requirement(0.857)가 가장 높고, qualification(0.667/0.500)·scoring(0.500)이 낮다. 자격요건·배점·제출서류가 혼재되거나 복합항목일수록 1:1 매칭이 어려워진다.
>
> 핵심 발견 2 - qualification은 자격요건+제출서류 혼재. Q019의 review 6·unresolved 3의 대부분이 "별지N 서류" 항목. 추출기는 자격요건은 잘 잡으나 개별 서류명을 일반 문구와 매칭하기 어렵다. Q018도 동일 패턴(unresolved 2건이 제출서류)이라 두 문항에서 일관 확인.
>
> 핵심 발견 3 - Precision은 분모(카테고리 항목 수)에 휘둘려 V4에선 비교 불가. 같은 추출기인데 Q015 precision 0.064(분모 234)와 Q018 0.500(분모 10)이 8배 차이. 추출 성능 차이가 아니라 분모 크기 차이일 뿐이다. V4에서는 Coverage만 유효 지표로 보고, precision은 V5 전수 라벨에서 정식 측정한다.
>
> 주: Q018은 hard 필터 기준 0.667. soft 필터에서는 제출서류 카테고리가 회복돼 더 높아질 가능성이 있으나, 이번 측정에는 soft 결과가 없어 별도 검증 예정.
>
> Q016/Q017(category mode)은 별도 채점하지 않고 V5 전수 채점으로 대체했다. V5는 카테고리 필터 없이 문서 전수를 채점하므로 개별 카테고리 문항을 따로 돌릴 필요가 없다.

---

## 6. V5 정식 채점 결과 (2026-07-02, 8문서 전수 / filter=none / k=8)

### 6.1 종합

- macro Item Coverage 0.886 / macro Item Precision 0.286 / Review Burden 9.7%
- expected 총 937개(in_scope) / 사람 검토 필요 91건 / matcher calls 6,908 / cache hits 588
- V4의 Coverage 표본 진단과 달리, 전수 라벨로 처음 신뢰 가능한 Precision을 확보(V4는 분모 문제로 측정 불가였음).

### 6.2 문서별

| 문서 | expected | Coverage | Precision | matched/review/unresolved |
|------|----------|----------|-----------|---------------------------|
| DOC_061 | 72 | 0.889 | 0.249 | 64 / 8 / 0 |
| DOC_003 | 91 | 0.890 | 0.271 | 81 / 7 / 3 |
| DOC_008 | 181 | 0.895 | 0.248 | 162 / 15 / 4 |
| DOC_040 | 83 | 0.831 | 0.294 | 69 / 11 / 3 |
| DOC_041 | 147 | 0.884 | 0.345 | 130 / 14 / 3 |
| DOC_048 | 148 | 0.912 | 0.290 | 135 / 13 / 0 |
| DOC_070 | 90 | 0.922 | 0.310 | 83 / 7 / 0 |
| DOC_087 | 125 | 0.864 | 0.278 | 108 / 16 / 1 |

Coverage 0.831~0.922로 문서 무관 안정. 의무항목 약 89%를 자동 회수한다. Precision 0.286은 "놓치지 않기(coverage)" 우선 설계의 결과다.

### 6.3 criticality별 분해 (미실시)

criticality(gate/mandatory/scored)별 Coverage 분해는 이번 채점에서 산출하지 않았다. 채점 파이프라인은 item 텍스트 매칭만 수행하고 criticality를 다루지 않으며, Decision Pair Cache는 해시 키라 gold criticality와 직접 조인이 불가하다. 분해하려면 러너 재실행(캐시 미스분 약 6,900 matcher 호출, 약 2.6달러)이 필요한데, 현재 API 잔여(8.8%)로는 한도를 초과해 실시하지 않았다. 문서별 Coverage 0.831~0.922 안정 분포로 설명력은 충분하다고 본다.

---

## 7. 골든셋 라벨 품질 관리

### 7.1 더블 라벨 일치도(Cohen's kappa)

경계 62건을 도혁이 독립 라벨한 뒤 아인님 라벨과 축별로 대조했다.
- actor kappa 0.941 (거의 완전 일치)
- scope kappa 1.000 (완전 일치)
- criticality kappa 0.457 (보통) — 불일치 27건

### 7.2 criticality 판정 규칙(합의)

criticality kappa가 낮았던 27건을 세 규칙으로 합의해 확정했다.
- 규칙 B: 제출 산출물(제안서·서약서 등)은 submission
- 규칙 C: 자격 관문(사전 통과 조건)은 gate
- 규칙 D: 실행형 이행 항목은 delivery

### 7.3 커플링 버그 정정

확장 라벨 빌더에서 scope=submission이면 criticality도 submission으로 자동 부여되는 커플링 버그를 발견했다. 경계 외 일반 라벨 937건을 전수 스캔하여 실행형인데 submission으로 잡힌 16건을 확인, freeze 전에 delivery로 정정했다. 더블 라벨이 채점 수치 오염을 사전 차단한 사례다.

---

## 8. 비용(키) 관리

- 팀 OpenAI 한도 $20, 현재 91.2% 소진($18.24 / $20.00, 잔여 $1.76).
- Q019 한 문항 = $0.05 (matcher 144 calls, expected 18개 기준).
- V5 8문서 전수 실측: matcher 6,908 calls, 채점 관련 소진 약 $2.5 (78.5% -> 91.0% 구간). 계획 단계 산술 추정($2.6)과 근사.
- 캐시 재사용으로 절약: 추출 캐시(재호출 0) + Decision Pair Cache(중복 판정 0) + 임베딩 캐시.
- 재추출(--force) 금지 — 8문서 전체 재추출 1회 약 13%p(약 $2.6), 문서당 약 $0.3(윈도우 수에 비례, $0.2~0.4).
- 잔여 예산이 적어(8.8%) 추가 대규모 채점·재추출은 발표 시연용 여유 확보를 위해 자제한다. criticality 분해(6.3)를 미실시한 것도 이 때문이다.

---

## 9. 체크리스트

- [x] V4 진단 4문항(Q015/Q018/Q019/Q020) 카테고리 경향 확인
- [x] V5 골든셋 무결성 게이트 통과(verify_golden_v5.py 12/12, PR #126)
- [x] 더블 라벨 kappa 측정 + criticality 규칙 3조 합의
- [x] 커플링 버그 16건 정정 후 freeze
- [x] V5 정식 채점 완료(cov 0.886, 스냅샷 저장)
- [x] Q016/Q017은 V5 전수로 대체(별도 category mode 채점 불요)
- [x] 비용 현황 갱신(91.2% 소진)
- [ ] criticality별 분해 — API 예산상 미실시(6.3)
