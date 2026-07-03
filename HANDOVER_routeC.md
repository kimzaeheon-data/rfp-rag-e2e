# 라우트 C 인수인계 (HANDOVER_routeC)

> 최종 갱신: 2026-07-03 / 작성: DE 도혁
> 대상: SD 수민님(서비스 연동·시연) 및 이후 라우트 C를 받는 모든 사람
> 이 문서는 GitHub 커밋용. 캐시·골든셋 실물(추출 원문·quote)은 NDA 대상이라 리포에 올리지 않고 드라이브에서 별도 수령.

---

## 0. 한눈에 보기

라우트 C = **선택된 RFP 문서(doc_id) 하나에서 입찰자가 지켜야 할 의무항목을 전부 추출해 체크리스트로 반환**하는 도구.

- 라우트 A(검색)와 다른 점: **질문 텍스트가 아니라 doc_id로 동작**한다. 문서 전체를 윈도우로 훑어 추출하기 때문에 질문만으로는 동작하지 않는다. "질문 → doc_id" 변환은 검색 단계가 담당한다.
- 무거운 작업이다: gpt-5-mini 실호출, **문서당 약 2분**.

### 현행 진입점 (이것만 쓰면 된다)

```
route_c_node(state)                         # backend/graph/nodes/route_c.py  ← LangGraph 노드
  └─ generate_checklist(doc_id)             # data_processing/example_generate_checklist.py  ← 추출기 진입점
       └─ ComplianceExtractorV2.run(...)    # data_processing/compliance_extractor_v2.py  ← 실제 추출 (현행 v2)
```

### 혼동 주의 (다른 팀이 가장 헷갈리는 지점)

`generate_checklist`라는 이름의 함수가 리포에 **3개** 있다. 이 중 현행은 하나뿐이다.

| 위치 | 상태 | 설명 |
|------|------|------|
| `data_processing/example_generate_checklist.py` : `generate_checklist(doc_id)` | [현행] | 실서비스·시연이 쓰는 진입점. `ComplianceExtractorV2`를 호출. |
| `data_processing/compliance_extractor.py` : `generate_checklist(query, doc_id)` (모듈함수, line 324) | [죽은 코드] | v1 진입점. 아무도 import하지 않음. 무시할 것. |
| `data_processing/compliance_extractor.py` : `ChecklistGenerator.generate_checklist()` (메서드, line 281) | [죽은 코드] | v1 클래스 메서드. 직접 진입점으로 쓰지 않음. |

`compliance_extractor.py`(v1) 파일 자체는 **완전히 죽은 건 아니다** — v2가 내부에서 `ChecklistGenerator`를 조립 헬퍼로 상속해 쓴다(`self._base = ChecklistGenerator()`, 청크 조립용). 하지만 **v1의 `generate_checklist` 진입점(line 281·324)은 죽은 코드**다. 진입점으로는 절대 이 둘을 쓰지 말 것. import 사슬로 확정된 사실이며, 현행은 오직 v2뿐이다.

---

## 1. 받는 사람이 할 일 (체크리스트)

**연동 (라이브):**
1. `state["selected_doc_id"]`에 대상 문서 ID를 넣고 `route_c_node(state)` 호출.
2. 반환된 `route_status`(status 5종)로 UI 분기 (→ 3-3 표).
3. 반환된 `checklist_items`를 화면에 표출 (→ 3-2 스키마).

**시연 백업 준비:**
1. 드라이브에서 캐시 zip 수령 → 로컬 `data/eval_cache/extractions/`에 압축 해제 (→ 2-1).
2. 라이브 실패/지연 시, 캐시 JSON을 직접 읽어 표출 (→ 2-4 매핑, 2-6 예시).

**시연 운영 (회의 확정):**
- 라이브 추출은 문서당 약 2분 → **발표 초반에 트리거**해두고, 진행 중/후반에 결과 표출.
- 즉시 응답 항목은 후반부.
- 라이브가 실패할 때를 대비해 백업 캐시(8문서)를 손에 쥐고 진행.

---

## 2. 시연 백업 경로 (캐시)

라이브 실호출이 타임아웃/에러/시간초과일 때를 대비한 안전망. V5 골든셋 8문서의 **실제 추출 결과**가 캐시로 준비돼 있다.

### 2-1. 캐시 수령 및 배치

- 파일: `route_c_v5_cache_8docs_0702.zip` (드라이브: Data Team > 평가결과 / 추출캐시 폴더)
- 배치 위치(로컬): `data/eval_cache/extractions/`
- 해제 시 `DOC_xxx_extracted.json` 8개가 플랫하게 풀린다.
- 이 폴더는 **gitignore 대상(NDA)**. 리포에 커밋하지 말 것.

### 2-2. 캐시 8문서

| doc_id | 추출 항목 수 | status | windows |
|--------|-------------|--------|---------|
| DOC_061 | 748 | complete_with_review | 22/22 |
| DOC_003 | 745 | complete_with_review | 28/28 |
| DOC_008 | 1706 | complete_with_review | 32/32 |
| DOC_040 | 480 | complete_with_review | 19/19 |
| DOC_041 | 849 | complete_with_review | 33/33 |
| DOC_048 | 1147 | complete_with_review | 30/30 |
| DOC_070 | 771 | complete_with_review | 28/28 |
| DOC_087 | 1108 | complete_with_review | 34/34 |

8문서 전부 windows 완료(failed 0), status 전부 `complete_with_review`.

### 2-3. 캐시 파일 구조

```json
{
  "doc_id": "DOC_xxx",
  "items": [
    {
      "item": "<의무항목 내용>",
      "primary_category": "requirement | qualification | submission | scoring",
      "evidence": [
        {"chunk_id": "DOC_xxx#n", "quote": "<근거 원문>", "match_status": "<...>"}
      ]
    }
  ],
  "manifest": { "doc_id": "...", "status": "...", "windows_total": 0, "windows_completed": 0 }
}
```

### 2-4. 캐시 → 서비스 스키마 매핑

캐시는 **평가용 경량 스키마**라 서비스 반환 스키마(→ 3-2)와 필드명이 다르다. 백업 표출 시 아래로 변환:

| 서비스 스키마 | 캐시 스키마 | 비고 |
|--------------|------------|------|
| `items[].text` | `items[].item` | 이름만 다름 |
| `items[].category` | `items[].primary_category` | 이름만 다름 |
| `evidence[].chunk_id` | `evidence[].chunk_id` | 동일 |
| `evidence[].quote` | `evidence[].quote` | 동일 |
| `evidence[].status` | `evidence[].match_status` | 이름만 다름 |
| `items[].flags` | **없음** | 아래 주의 |
| `status` | `manifest.status` | 전부 complete_with_review |
| `extracted_count` | `len(items)` | 계산 |

** 캐시에는 `flags` 필드가 없다.** 평가 파이프라인은 flags(검토 우선순위 힌트)를 쓰지 않아 저장하지 않았다. 백업 표출 시 UI가 flags를 참조하면 값이 없어 에러 날 수 있으니, **flags는 기본값(전부 false) 또는 미표시로 처리**할 것. 항목 내용/카테고리/근거는 완전하므로 체크리스트 표출 자체엔 지장 없다.

### 2-5. match_status 값 (참고)

캐시 evidence의 `match_status`는 근거 검증 결과다:
- `strict_verified` — 근거 quote가 청크에 정확히 존재 (대다수)
- `relocated_verified` — 인접 청크에서 재확인됨 (scope 유지)
- `cross_chunk_verified` — 여러 청크 걸침, 검증됨
- `unverified_evidence` — 자동 검증 실패 (표현 차이 등, 사람 검토 영역)
- `out_of_scope_source` — 범위 밖 근거

`unverified_evidence`가 섞여 있어 status가 `complete_with_review`로 잡힌 것(정상 동작).

### 2-6. 백업 캐시 읽기 예시 (복붙용)

```python
import json
from pathlib import Path

CACHE_DIR = Path("data/eval_cache/extractions")

def load_from_cache(doc_id: str) -> dict:
    """라이브 실패 시 백업. 캐시 JSON을 서비스 스키마로 변환해 반환."""
    fp = CACHE_DIR / f"{doc_id}_extracted.json"
    if not fp.exists():
        return {"items": [], "doc_id": doc_id, "status": "doc_not_found", "extracted_count": 0}

    with open(fp, encoding="utf-8") as f:      # 한글 → 반드시 utf-8
        raw = json.load(f)

    items = []
    for it in raw["items"]:
        items.append({
            "text": it["item"],
            "category": it["primary_category"],
            "evidence": [
                {"chunk_id": ev["chunk_id"], "quote": ev["quote"], "status": ev["match_status"]}
                for ev in it["evidence"]
            ],
            "flags": {"condition": False, "numeric": False, "deadline": False},  # 캐시엔 flags 없음
        })

    return {
        "items": items,
        "doc_id": raw["doc_id"],
        "status": raw["manifest"]["status"],
        "extracted_count": len(items),
    }
```

---

## 3. 라이브 경로 (서비스 연동)

### 3-1. 노드 호출 예시 (복붙용)

```python
# backend/graph/nodes/route_c.py 의 route_c_node 를 그래프에서 호출
# 입력: state["selected_doc_id"]
# 출력: {"checklist_items": [...], "route_status": "<status>"}

state = {"selected_doc_id": "DOC_061"}
result = route_c_node(state)

items  = result["checklist_items"]   # 3-2 스키마
status = result["route_status"]      # 3-3 표
```

`selected_doc_id`가 없으면 추출기를 부르지 않고 `route_status="no_doc_selected"`로 즉시 단락한다(무거운 LLM 호출을 미리 막는 설계).

### 3-2. checklist_items 스키마 (라이브)

```json
{
  "text": "<의무항목 내용>",
  "category": "requirement | qualification | submission | scoring",
  "evidence": [
    {"chunk_id": "DOC_xxx#n", "quote": "<근거 원문>", "status": "<match_status>"}
  ],
  "flags": {
    "condition": false,   // 조건부 표현 누락 위험
    "numeric":   false,   // 숫자/배점 불일치 위험
    "deadline":  false    // 기한 누락 위험
  }
}
```

라이브 경로는 flags가 채워진다(v2 sentinel이 계산). 백업 캐시 경로는 flags가 비어있다(→ 2-4).

### 3-3. status 5종 + UI 가이드

`route_status`로 전달되며 `answer_generation`이 분기한다.

| status | 의미 | 발생 조건 | UI 표출 가이드(제안) |
|--------|------|-----------|---------------------|
| `complete_verified` | 완전 검증 완료 | 전 윈도우 성공 + 검토 플래그 없음 | 체크리스트 정상 표출 |
| `complete_with_review` | 완료(검토 권장) | 성공했으나 미검증 근거 또는 조건/수치/기한 리스크 있음 | 표출 + "일부 항목 검토 권장" 안내 |
| `partial` | 부분 완료 | 일부 윈도우 실패 | 표출 + "일부 구간 추출 실패" 경고 |
| `failed` | 실패 | 전 윈도우 실패 | 체크리스트 없음, 재시도 안내 |
| `doc_not_found` | 문서 없음 | 해당 doc_id 청크 없음 | "문서를 찾을 수 없음" 안내 |

※ `no_doc_selected`는 추출기 status가 아니라 **노드 레벨**에서 나온다(doc_id 미선택 단락). UI 분기 시 이 값도 함께 처리 필요("공고를 먼저 선택하세요" 안내).

---

## 4. 코드 지도 (파일별 역할)

| 파일 | 역할 | 상태 |
|------|------|------|
| `backend/graph/nodes/route_c.py` | LangGraph 노드, 서비스 진입점 | [현행] |
| `data_processing/example_generate_checklist.py` | `generate_checklist(doc_id)` 추출기 진입점 | [현행] |
| `data_processing/compliance_extractor_v2.py` | `ComplianceExtractorV2` — 실제 추출 파이프라인 | [현행] |
| `data_processing/compliance_extractor.py` | `ChecklistGenerator`(청크 조립 헬퍼) | v2가 헬퍼로만 사용. 이 파일의 `generate_checklist`(line 281·324)는 [죽은 코드] |
| `data_processing/models.py` | Pydantic 데이터 계약(evidence 검증·sentinel·dedupe) | [현행] |
| `evaluation/eval_route_c.py` | 채점 파이프라인 (캐시 읽기 포함) | [평가 전용] |
| `evaluation/run_v5_scoring.py` | V5 정식 채점 러너 | [평가 전용] |

**핵심:** 캐시(`data/eval_cache/extractions/`)를 읽는 코드는 **평가 파이프라인에만** 있다. 서비스 진입점(`generate_checklist`)은 캐시를 읽지 않고 매번 실추출한다. 그래서 시연 백업으로 캐시를 쓰려면 2-6처럼 **직접 읽어** 표출해야 한다(서비스 진입점이 자동으로 캐시를 쓰지 않는다).

---

## 5. 기술 근거 (계승 — v2 설계 확정 사항)

### gpt-5-mini 실전 제약
- reasoning 모델이라 느림(윈도우당 30~90초) → 병렬 필수(max_workers).
- reasoning 토큰이 max를 먹어 출력 잘림(LengthError) → `max_completion_tokens=16000` + 방어 코드.
- `reasoning_effort="low"` (minimal은 과추출).
- 100문서 전체 추출은 비현실적(~18시간) → 골든셋 문서 샘플로 검증.

### 윈도우 / 검증 설계
- 윈도우 = 청크 8개 기준(토큰 16k는 타임아웃). overlap 1청크.
- 검증율 개선: PDF 추출 띄어쓰기 노이즈가 주범 → normalize 공백 제거로 75% → 97.5%(DOC_001 실측). NLI 불필요했음(기계적 fix 우선).
- relocated: 인접 허용 범위 전체에서 재확인(scope 유지).
- LLM 노이즈 측정: raw 출력 고정 후 A/B 비교(`data/raw_llm_cache`, gitignore).

### 캐시 동작
- 같은 doc_id 재추출은 캐시가 있으면 재호출 0(평가 파이프라인 기준). `input_manifest_hash`로 입력 변경 시 stale 무효화.
- manifest에 `prompt_version`/`schema_version`(v2) 기록 → 재현성 추적.

---

## 6. V5 평가 결과 (2026-07-02 정식 채점)

- **macro Coverage 0.886 / Precision 0.286 / Review burden 9.7%** (8문서 전수, filter_mode=none)
- 문서별 Coverage 0.831 ~ 0.922로 문서 무관 안정. 의무항목 약 89% 자동 회수.
- Precision 0.286은 "놓치지 않기(coverage)" 우선 설계의 결과. 전수 라벨로 처음 신뢰 가능한 값 확보(V4는 분모 문제로 측정 불가였음).
- 총 matcher calls 6,908 / 캐시 히트 588 → 캐시가 재호출을 실제로 0으로 만든 근거.
- 스냅샷: `evaluation/reports/route_c_eval_8q_k8.json` (드라이브: Data Team > 평가결과)

---

## 7. 절대 금지 / NDA

- 청킹·FAISS 인덱스 변경 금지.
- **NDA:** 원문·골든셋·`raw_llm_cache`·추출 캐시 실물을 git 커밋 금지. 데이터 실물은 드라이브, 문서는 GitHub로 분리.
- 개인 OpenAI 키 사용 금지. 팀 키(.env, BOM 없이 utf-8, gitignore)만. 팀 $20 한도 / `!usage`로 관리.
- 한글 파일 수정은 반드시 python `io.open(..., encoding="utf-8")`. PowerShell Get-Content/Set-Content/-replace는 CP949로 한글을 깨뜨림.

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 체크리스트가 mock 항목("(mock) ...")만 나옴 | `use_mock=True`로 호출됨 | 현행 진입점 `generate_checklist(doc_id)`는 실호출(`use_mock=False`) 고정. 직접 v2를 부를 때 인자 확인 |
| `route_status="no_doc_selected"` | `selected_doc_id`가 비어있음 | 검색 단계에서 doc_id를 넘겼는지 확인 |
| `status="doc_not_found"` | 해당 doc_id 청크가 인덱스에 없음 | 문서 ID·청크 인덱스 확인 (chunks_v1) |
| 라이브가 2분 넘게 안 끝남 | 대형 문서 실추출 정상 소요 | 시연은 초반 트리거 권장. 급하면 백업 캐시(2-6)로 표출 |
| 백업 캐시 표출 시 flags 참조 에러 | 캐시엔 flags 없음 | flags 기본값(false) 처리 (2-4, 2-6) |
| 한글이 깨져 저장됨 | PowerShell로 파일 수정 | python utf-8로 재작성 |

---

## 문의

라우트 C 연동에서 막히는 부분은 DE 도혁에게. 시연 문서가 확정되면 해당 doc_id 캐시를 미리 데워둘 수 있음.
