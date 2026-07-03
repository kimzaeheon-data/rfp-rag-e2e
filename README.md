---
# 2026-Agentic-RAG-Project: RFP 문서 요약 & 질문/답변 챗봇

AI 엔지니어 10기 중급 팀 프로젝트 — 가상 B2G 입찰지원 스타트업 **'입찰메이트(RFPilot)'** 의 사내 RAG 시스템입니다. 공공조달 RFP 문서(HWP 96 / PDF 4, 총 100건)에 대해 컨설턴트가 자연어로 질의하면, 검색·생성·의무항목 추출을 결합해 답변과 준수 체크리스트를 제공합니다.

> **기간**: 2026-06-17 ~ 07-08 (3주)
> **결과물**: 프로젝트 완료 보고서 + GitHub repo 제출

---

## 프로젝트 개요 (수치)

### 데이터 규모
- RFP 문서: 100건 (HWP 96 / PDF 4)
- 청크: 14,606개 (chunks_v1)
- 골든셋(V5): 954 라벨 / 937 in_scope 채점 대상 (DE 아인 담당)

### 성능 지표
| 파트 | 지표 | 값 |
|------|------|-----|
| 라우트 C (의무항목 추출) | Item Coverage (V5, 8문서 전수) | 0.886 |
| 라우트 C | Item Precision | 0.286 |
| 라우트 C | Review Burden | 9.7% |
| 검색 (RAG) | RAGAS 등 | 담당자 작성 예정 |
| 생성 | 응답 품질 | 담당자 작성 예정 |

라우트 C는 문서 단위 전수 채점(filter=none) 기준이며, 문서별 Coverage는 0.831~0.922로 안정적입니다.

---

## 팀 구성

| 이름 | 역할 | 담당 |
| --- | --- | --- |
| 민재 | PM (Project Manager) | 일정 관리, 이슈 조율, PR 리뷰 |
| 도혁 | DE (Data Engineer) | 문서 청킹 전략 설계 및 검증, 라우트 C 기능 구현 |
| 아인 | DE (Data Engineer) | 문서별 메타데이터 처리, 골든 데이터셋 구축 |
| 재헌 | RE (Retrieval Engineer) | 임베딩 생성, vector DB 구축, retrieval 기법 고도화 |
| 수민 | SD (Service Developer) | 모델 응답 고도화(정확도, 포맷, 길이, 톤 등), 챗봇 서비스 개발|

---

## 팀 보고서

> **보고서 제출 예정**
<a href="https://github.com/Codeit-Part3-5Team/codeit-part3-5team-project">바로 가기</a>

---

## 협업일지 및 팀 일간 보고서

<a href="https://github.com/orgs/Codeit-Part3-5Team/discussions">바로 가기</a>

---

## 프로젝트 파이프라인

```
              [사용자 질문]
                   |
      [Agentic 파이프라인 (바깥 껍데기)]
                   |
             Node: 질문 분석
                   |
        +---------------------+
        |                     |
        v                     v
   Node: RAG 검색         Node: 라우트 C
   *하이브리드 구조*       Compliance Validator 도구
   "Naive RAG"           - 필수/반드시 키워드 검색(도구 특화)
   + "Agentic RAG"       - LLM 체크리스트 생성
        |                     |
        +---------------------+
                   |
             Node: 답변 생성
                   |
               [최종 답변]
```

> 위 다이어그램은 개념 흐름 기준입니다. 실제 LangGraph 노드 구조와의 상세 정합성은 각 노드 담당자 확인이 필요합니다(라우트 C 노드는 확인 완료).

---

## 프로젝트 구조

```
codeit-part3-5team-project/
├── data/                 # 데이터 (.gitignore, NDA)
│   ├── raw/              # 원본 HWP, PDF
│   ├── metadata/         # data_list.csv
│   └── processed/        # 가공 데이터 (청크 JSON 등)
|
├── backend/    # FastAPI (웹/앱 공통)
|   |
│   ├── evaluation/   # 생성/검색 평가
|   |
│   ├── generation/   # 생성
│   │   └── prompts/  # 시스템 프롬프트
|   |
|   ├── graph/        # LangGraph
|   |   └── nodes/    # 노드
|   |
│   └── retrieval/    # 검색
|
├── data_processing/  # 데이터 전처리
|
├── evaluation/  # 데이터 평가
|
├── frontend/    # React 웹 프론트엔드
|
├── utils/       # 공통 유틸리티
|
├── notebooks/   # Jupyter Notebooks (baseline, experiments ...)
|
├── reports/     # 보고서·발표자료 PDF
└── .github/     # PR 템플릿, Issue 템플릿
```

---

## 환경 설정

### 사전 요구사항

- Python 3.12+

### 설치

```bash
git clone https://github.com/Codeit-Part3-5Team/codeit-part3-5team-project.git
cd codeit-part3-5team-project

# 가상환경 생성 (conda 권장)
conda create -n codeit-part3-5team-project python=3.12 -y
conda activate codeit-part3-5team-project

pip install -r requirements.txt
pip install -e .
```

`pip install -e .`는 개발 중인 현재 프로젝트를 Python 환경에 등록합니다.
노트북 또는 다른 작업 디렉터리에서 실행해도 `from backend...` import를 안정적으로 사용할 수 있습니다.

---

## 재현 방법

> 주의: 원본 RFP·골든셋·캐시 등 NDA 데이터는 리포에 포함되지 않습니다(.gitignore). 드라이브(Data Team)에서 별도 수령해 `data/` 하위에 배치한 뒤 실행하세요.

### 통합 실행

```bash
# 추후 작성 예정

# 데이터

# 검색

# 생성

# 챗봇

```

### 데이터 단독 실행

```bash
# 1) 원본 재파싱 (HWP/PDF 100건 → canonical 본문)
python data_processing/build_parsed_v2.py

# 2) PII 마스킹 적용 (parsed → masked_documents_v3.json)
#    v3 정책: 유선·대표번호 공개 / 개인 휴대폰·이메일·주민·사업자·법인 마스킹
PYTHONIOENCODING=utf-8 python data_processing/remask_v3.py

# 3) 청킹 (표 추출 v2 + tiktoken 기반, 입력=마스킹본)
python data_processing/build_chunks.py

# 4) 청크 품질 게이트 (중복/과세분화/PUA/토큰)
python evaluation/check_chunks.py

# 5) enriched 청크 생성 (청크 + doc_metadata → chunks_v1_0622_enriched.json)
#    이후 단계(마스킹 검증/매니페스트/골든셋)의 입력
python data_processing/enrich_chunks.py

# 6) PII 마스킹 검증 (3단계 누출 검사, PASS/FAIL 판정) — enriched 청크 필요
python evaluation/scan_3stage.py

# 7) 마스킹 매니페스트 생성 (검증 결과 증명) — enriched 청크 필요
python evaluation/build_manifest.py

# 8) 골든셋 빌드 (검색·생성 평가용) — enriched 청크 필요
python evaluation/build_golden_dataset_v3.py

# 9) V5 골든셋 무결성 검사 (하드 12축, 재청킹 시 깨짐 자동 감지)
python evaluation/verify_golden_v5.py

# 10) 라우트 C 의무항목 추출 채점 (V5 blind gold, 8문서 전수)
#    gold 관계: v5_gold_labels.json(SSOT) → make_v5_loader.py → v5_gold_questions.json
#    주의: gold는 NDA — 드라이브에서 수령하거나 로더로 생성 후 실행
#    V5 정식 채점 결과: macro Coverage 0.886 / Precision 0.286 / Review burden 9.7% (8문서 전수)
python make_v5_loader.py
python evaluation/run_v5_scoring.py --snapshot
#    스모크(단일 문서): python evaluation/run_v5_scoring.py --doc=DOC_061

# (참고) 데이터/추출기 단위 테스트
python -m pytest evaluation/test_masking.py -q          # 마스킹 회귀 14건
python evaluation/test_verify_evidence.py                # 근거 검증
python evaluation/test_dedupe.py                         # 중복 제거
python evaluation/test_sentinels.py                      # 센티넬
python evaluation/test_completeness_gate.py              # 완전성 게이트
python evaluation/test_compliance_extractor.py           # 추출기 통합
```

### 검색 단독 실행

```bash
# 추후 작성 예정

```

### 생성 단독 실행

```bash
# 추후 작성 예정

```

### 챗봇 단독 실행

```bash
# 추후 작성 예정

```
---

---

## 데이터 배치 (드라이브 → 로컬)

NDA 데이터는 리포에 포함되지 않습니다(.gitignore). 드라이브(Data Team)에서 받아 아래 경로에 배치한 뒤 재현 명령어를 실행하세요.

| 드라이브 폴더 | 로컬 경로 | 용도 |
|--------------|-----------|------|
| 원본 데이터 | `data/raw/` | HWP/PDF 원본 100건 |
| 파싱본문 | `data/processed/` | canonical 본문 (parsed_documents_v2.json) |
| 마스킹본 | `data/processed/` | PII 마스킹 적용본 (masked_documents_v3.json) |
| 청크 | `data/processed/` | 청크 JSON (chunks_v1_0622_PASS.json) |
| doc_metadata | `data/processed/` | 문서 메타데이터 (enrich_chunks 입력) |
| enriched 청크 | `data/processed/` | 청크 + doc_metadata 조인 (chunks_v1_0622_enriched.json, 마스킹 검증·골든셋 입력) |(chunks_v1_0622_enriched.json, 마스킹 검증·골든셋 입력) |
| 골든셋 | `data/processed/` | 라벨 (v5_gold_labels.json 등) |
| 추출캐시 | `data/eval_cache/extractions/` | 문서별 추출 결과 |
| 평가결과 | `evaluation/reports/` | 채점 스냅샷 |
| faiss_index | `data/faiss_index/` | 검색 인덱스 (검색팀) |

가공 산출물(파싱본/마스킹본/청크/골든셋)은 드라이브에 있으므로, 처음부터 재생성하지 않고 받아서 배치하면 바로 다음 단계를 실행할 수 있습니다.

---

## 실행 순서 (의존성)

```
파싱(build_parsed_v2)
   → 마스킹본(masked_documents_v3, 드라이브 수령)
      → 청킹(build_chunks) → 청크 게이트(check_chunks)
         → enriched 청크(드라이브 수령. 청크 + doc_metadata 조인)
            → 마스킹 검증(scan_3stage) / 매니페스트(build_manifest)  ← enriched 필요
            → 골든셋(build_golden_dataset_v3)  ← enriched 필요
               → 골든 무결성 게이트(verify_golden_v5)
                  → 라우트 C 채점(run_v5_scoring)  ← gold 필요
```

- 청킹(build_chunks)은 마스킹본(masked_documents_v3.json)을 입력으로 읽습니다. 드라이브에서 받아 `data/processed/`에 두면 됩니다.
- 마스킹 검증(scan_3stage)·매니페스트(build_manifest)는 3단계 검증의 마지막 스테이지로 enriched 청크를 입력으로 읽으므로, 청킹·enrich 이후에 실행해야 합니다.
- 골든셋 빌드도 enriched 청크를 입력으로 사용합니다.
- 라우트 C 채점은 청크 + gold가 필요합니다. gold 관계: v5_gold_labels.json(SSOT) → `make_v5_loader.py` → v5_gold_questions.json.

---

## API 키 / 비용 주의

- 일부 스크립트는 OpenAI API를 사용합니다: `run_v5_scoring.py`(matcher), `build_golden_dataset_v3.py`(평가), 추출기.
- 실행 전 `.env`에 `OPENAI_API_KEY`가 필요합니다(BOM 없이 UTF-8, gitignore 대상).
- 팀 공용 한도($20)를 공유합니다. 대규모 채점·재추출은 잔여 예산을 확인하고 실행하세요.
- 캐시가 있으면 재호출이 0입니다. 불필요한 `--force` 재추출은 피하세요(8문서 전체 재추출 약 $2.6).

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 한글 파일이 깨진 채 저장됨 | PowerShell Get-Content/Set-Content가 CP949로 처리 | Python io.open(encoding="utf-8")로 읽고 쓰기 |
| 콘솔에서 한글·기호가 깨져 보임 | 콘솔 출력 인코딩이 CP949 | PYTHONIOENCODING=utf-8 설정 후 실행 |
| build_chunks 실행 시 입력 파일 없음 | 마스킹본이 data/processed/에 없음 | 드라이브에서 masked_documents_v3.json 수령 후 배치 |
| scan_3stage/build_manifest/골든셋 빌드 에러 | enriched 청크가 data/processed/에 없음 | 드라이브에서 enriched 청크 수령 후 배치 (청킹 이후 단계) |
| run_v5_scoring.py 실행 시 파일 없음 에러 | gold(v5_gold_questions.json)가 없음 | make_v5_loader.py로 생성하거나 드라이브 수령 |
| 채점이 예상보다 느리고 비용이 큼 | 캐시 미스로 matcher 신규 호출 | 캐시 배치 확인. 캐시 히트 시 재호출 0 |

## 데이터 처리 정책

### 담당자 인명 처리 (미마스킹)

RFP 문서 내 담당자 인명은 **마스킹하지 않고 공개 유지**합니다.

**법적 근거 — 공공기관의 정보공개에 관한 법률 제9조 제1항 제6호 단서:**
비공개 대상이 되는 개인정보라도 다음은 공개 가능합니다.
- (라목) 직무를 수행한 공무원의 성명·직위
- (마목) 공개하는 것이 공익을 위하여 필요한 경우로서, 법령에 따라 국가·지자체가 업무의 일부를 위탁·위촉한 개인의 성명·직업

**적용 논리:**
RFP 문서 내 담당자 정보는 공공 조달 절차의 공식 문의처(Point of Contact)로서, 기관이 업무 연락 목적으로 공고에 공표한 정보입니다. PIPA상 개인정보에 해당하나, 본인의 직무 수행과 관련하여 공표된 정보로 한정해 활용하므로 마스킹하지 않습니다.

### 마스킹 대상 (개인 사적 정보)

기관 업무용 정보는 공개하되, 개인 사적 정보는 마스킹합니다.

| 구분 | 처리 | 예시 |
|------|------|------|
| 사업자등록번호 / 법인등록번호 | 마스킹 | `[사업자등록번호]` |
| 개인 휴대폰 (010) | 마스킹 | `[전화번호]` |
| 사적 이메일 (gmail, naver 등) | 마스킹 | `[이메일]` |
| 주민등록번호 / 계좌번호 | 마스킹 | `[주민등록번호]` |
| 기관 유선전화 / 대표번호 | 공개 | 02-1234-5678 |
| 기관 이메일 (.go.kr, .or.kr 등) | 공개 | info@기관.go.kr |
| 담당자 인명 | 공개 | (위 정책 참조) |

기준: **기관 업무용 = 공개 / 개인 사적 = 마스킹**

### 검증 도구 (evaluation/)

데이터 무결성은 다음 도구로 검증하며, 결과를 매니페스트로 증명합니다.

| 도구 | 역할 |
|------|------|
| `scan_3stage.py` | parsed→masked→final 3단계 PII 누출 검증 |
| `test_masking.py` | 마스킹 회귀 테스트 (pytest 14개) |
| `build_manifest.py` | 마스킹 검증 매니페스트 생성 |
| `build_golden_dataset_v3.py` | 골든셋 라벨 정합성 검증·빌드 |
| `verify_golden_v5.py` | V5 골든셋 무결성 검사 (하드 12축, 재청킹 시 깨짐 자동 감지) |
| `check_chunks.py` | 청크 품질 게이트 (중복/과세분화/PUA/토큰) |
| `run_v5_scoring.py` | 라우트 C 의무항목 추출 채점 (V5 blind gold) |

**한계:** 정규식 기반 탐지로 자연어 PII(예: "공일공에 일이삼사")·이미지 내 텍스트(OCR 미적용)는 범위 밖이며, 담당자 인명의 정확한 노출 카운트는 NER 도입 시에만 가능합니다.

---

## 라이선스

본 프로젝트는 [gpt-5-mini](https://developers.openai.com/api/docs/models/gpt-5-mini) OpenAI API를 사용합니다.

---
