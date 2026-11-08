# RFPilot · 공공조달 RFP 챗봇 개인 고도화

코드잇 AI 엔지니어 10기 5팀에서 만든 공공조달 RFP 챗봇 <strong>입찰메이트(RFPilot)</strong>를 개인적으로 고도화한 저장소입니다. 팀 프로젝트를 마친 뒤 검색 평가 코드와 실제 챗봇의 요청 경로를 다시 따라가며, 검색 조건이 답변에 반영되는 방식과 전체 목록을 조회하는 방식을 개선했습니다.

## 팀 프로젝트에서 만든 것

팀은 공공조달 제안요청서 100건(HWP 96건, PDF 4건)을 대상으로 문서 조회·요약, 근거 인용, 준수 체크리스트 기능을 구현했습니다. 문서를 전처리해 BGE-M3와 FAISS로 검색하고, LangGraph가 질문 유형에 따라 조회와 체크리스트 경로를 선택합니다. FastAPI와 React로 챗봇을 연결했습니다.

팀에서 저는 <strong>검색 담당(Retrieval Engineer)</strong>으로 임베딩 생성, 벡터 인덱스 구축, 검색 기법 개선과 평가를 맡았습니다. 팀원별 역할과 당시 성능 지표는 팀 저장소와 완료 보고서에 정리되어 있습니다. [원본 팀 저장소](https://github.com/Codeit-Part3-5Team/codeit-part3-5team-project) · [팀 프로젝트 완료 보고서](https://codeit-part3-5team.github.io/codeit-part3-5team-project/reports/RFP_프로젝트_완료_보고서_5팀.pdf)

## 검토에서 발견한 문제와 개인 고도화

### 1. 검색 평가에서 사용한 메타데이터 필터를 챗봇에 연결

검색 단독 평가에서는 질문에서 발주기관·예산·날짜를 추출해 검색 함수에 전달했습니다. 챗봇의 첫 검색은 재작성된 질문과 `top_k`만 전달하고 있어, 평가에서 사용한 조건이 답변 근거를 고르는 과정에 빠져 있었습니다.

기존 조건 추출기를 Route A에 연결해 기관·예산·날짜 조건과 정렬을 첫 검색에 적용했습니다. 재검색에서도 조건을 유지하도록 하고, 생성 모델에는 그 조건을 통과한 청크를 전달하도록 했습니다. [Route A](backend/graph/nodes/route_a.py) · [조건 추출기](backend/retrieval/query_parser.py) · [재검색 노드](backend/graph/nodes/re_retrieve.py)

전수 조회를 추가하기 전에 실제 RFP 메타요약 100건과 골든셋 v4의 6문항으로, 같은 챗봇 경로에서 필터를 끈 경우와 켠 경우를 비교했습니다. 이 실험에서는 OpenAI를 사용해 조건 추출과 답변 생성까지 실행했습니다.

| 지표 | 필터 끔 | 필터 켬 |
| --- | ---: | ---: |
| 정답 문서가 검색 1위에 나온 문항 | 3/6 | 6/6 |
| 정답 문서 회수율 평균 (상위 5건) | 50.0% | 87.1% |
| 평균 전체 응답시간 | 7.90초 | 10.44초 |

최대 예산과 최초 공개일 질문은 최종 답변도 오답에서 정답으로 바뀌었습니다. 응답시간은 평균 2.54초 늘었습니다. 위 수치는 메타요약 인덱스와 6문항에 대한 소규모 비교 결과입니다.

### 2. 사업 목록과 건수를 전체 인덱스에서 조회

첫 번째 실험에서 “예산 5억 원 이상인 사업을 모두 알려줘”는 조건에 맞는 사업을 22건 찾았지만, `top_k=5` 제한으로 답변에는 5건만 들어갔습니다. 목록이나 건수를 묻는 질문은 검색 상위권 밖의 사업도 확인해야 했습니다.

전수 조회 경로에서는 인덱스의 문서를 `doc_id`로 묶고, 사업별 대표 메타데이터에 조건을 적용합니다. 코드가 일치한 사업을 모두 나열하거나 건수를 계산합니다. 조건 판단에 필요한 값이 비어 있는 경우는 별도로 표시합니다. [전수 조회 구현](backend/retrieval/catalog.py)

실제 사업 메타요약 100건을 넣고 `/chat`에서 조건 추출 응답을 고정해 조회 로직을 검증했습니다. 예산 5억 원 이상 질문에서 **골든셋과 일치하는 22건 전부**를 반환했고, 예산을 확인할 수 없는 7건을 별도로 안내했습니다. 한국수자원공사 발주 사업도 **정답 3건 전부**를 반환했습니다. 이 검증 범위는 조건 추출 이후의 전수 조회와 응답입니다.

## 개인 고도화 데모

가상 사업 10건을 사용한 로컬 React 화면입니다. 조건 추출과 일반 조회의 생성 응답은 데모용으로 구성했고, 검색 필터와 전수 조회는 실제 챗봇 코드로 실행했습니다.

### 일반 조회 · 메타데이터 필터 적용

미래데이터원이 발주한 예산 5억 원 이상 사업 중 하나를 답변합니다. 참고 문서에는 기관과 예산 조건을 모두 충족한 2건이 표시됩니다.

![RFPilot 일반 조회 데모 — 기관과 예산 필터를 통과한 참고 문서 2건](reports/metadata-filter-demo.png)

### 전수 조회 · 일치하는 사업 전체 반환

예산 5억 원 이상인 사업을 예산 내림차순으로 조회합니다. 조건에 맞는 7건을 모두 나열하고, 예산 정보가 없어 판정할 수 없는 1건은 따로 안내합니다.

![RFPilot 전수 조회 데모 — 예산 5억 원 이상인 예시 사업 7건](reports/exhaustive-lookup-demo.png)

## 현재 파이프라인

```mermaid
flowchart TD
    Q["질문과 대화 이력"] --> R["질문 재작성 · 라우팅"]
    R --> A["Route A · 문서 조회"]
    R --> C["Route C · 준수 체크리스트"]
    A --> P["기관 · 예산 · 날짜 등 조건 추출"]
    P --> S["일반 조회 · FAISS 검색과 조건 필터링"]
    P --> E["전수 조회 · 사업 단위로 전체 조건 검사"]
    S --> G["근거 기반 답변 생성"]
    E --> L["목록 또는 건수 계산"]
    C --> D["문서 선택 · 의무항목 추출"]
    G --> V["최종 규칙 검사 · 응답"]
    L --> V
    D --> V
```

일반 조회는 Naive 모드에서 검색 후 생성으로 넘어가고, Agentic 모드에서는 검색 결과를 평가하고 필요할 때 재검색합니다.

---

## 프로젝트 구조

```
rfp-rag-e2e/
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
git clone https://github.com/kimzaeheon-data/rfp-rag-e2e.git
cd rfp-rag-e2e

# 가상환경 생성 (conda 권장)
conda create -n rfp-rag-e2e python=3.12 -y
conda activate rfp-rag-e2e

pip install -r requirements.txt
```

백엔드와 평가 모듈은 저장소 루트에서 `python -m backend...` 형식으로 실행합니다.

---

## 재현 방법

> 주의: 원본 RFP·골든셋·캐시 등 NDA 데이터는 리포에 포함되지 않습니다(.gitignore). 드라이브(Data Team)에서 별도 수령해 `data/` 하위에 배치한 뒤 실행하세요.

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
# 디렉토리 이동
cd backend/retrieval

# 1) 청크 로드 확인 (data/processed/chunks_v1_enriched.json → LangChain Document)
python loader.py

# 2) bge-m3 임베딩 모델 로드 확인
python embedder_hf.py

# 3) bge-m3 FAISS 인덱스 빌드 (최초 1회 또는 청크 변경 시 → data/faiss_index_bge 생성)
python build_index_hf.py

# 4) FAISS_INDEX_PATH를 bge 인덱스로 지정 (최종 채택 구성)
export FAISS_INDEX_PATH=data/faiss_index_bge

# 5) retriever 단독 테스트 (메타필터 3단계 매칭 + MMR 검색)
python retriever.py

# 6) 전체 검색 파이프라인 실행 (rewrite → parse → retrieve → grade, LangGraph)
python rag_subgraph.py

# 7) (선택) 골든셋 기준 검색 성능 평가 — 최종 채택 구성(rewrite + meta filtering)
python eval_retrieval.py --golden golden_dataset_v4.json --rewrite --meta

```

### 생성 단독 실행

```bash
# 프로젝트 루트에서 실행 (backend는 python -m 으로 import)
# 1) 그래프 단독 확인 (rewrite → routing → route_a 검색 → 답변, LangGraph)
python -m backend.graph.build

# 2) 파이프라인 단독 테스트 (get_ai_response)
python -m backend.pipeline

# 3) (선택) 생성 평가 — 골든셋 답변 생성 후 RAGAS 채점
#    주의: OpenAI 호출로 비용 발생. 전체 실행 전 --limit로 소량 확인 권장.
python -m backend.evaluation.generate_answers --limit 5
python -m backend.evaluation.run_eval
```

일반 조회(Route A)는 기관·예산·날짜·정렬 조건을 첫 검색과 재검색에 적용합니다.

“예산 5억 원 이상인 사업을 모두 알려줘”처럼 사업 목록이나 건수를 요청하면, 인덱스에 등록된 사업을 문서 ID로 중복 제거하고 전체를 조회합니다. 발주기관, 예산 범위, 공개일·입찰일 범위를 지원하며, 필수 메타데이터가 없어 판정할 수 없는 건수는 별도로 표시합니다. 목록과 건수는 조회 결과로 직접 만들고, 일반 질의의 `top_k` 제한은 적용하지 않습니다.

현재 챗봇의 기본 경로와 조건 추출·전수 조회를 끈 경로를 비교하려면 같은 골든셋과 설정으로 아래 두 명령을 실행합니다. 각 결과에는 답변과 검색 근거가 함께 저장됩니다.

```bash
python -m backend.evaluation.generate_answers --limit 5 --no-query-metadata --tag metadata_ab
python -m backend.evaluation.generate_answers --limit 5 --tag metadata_ab
```

### 챗봇 단독 실행

```bash
# 백엔드 (FastAPI, http://localhost:8000) — 프로젝트 루트에서
python -m backend.main

# 프론트엔드 (React, http://localhost:3000) — 별도 터미널
cd frontend
npm install
npm start
```

> 프론트엔드는 `.env`의 `REACT_APP_API_URL`(기본 `http://localhost:8000`)로 백엔드에 연결합니다.

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
| faiss_index | `data/faiss_index_bge/` | 검색 인덱스 (검색팀) |

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

- 일부 스크립트는 OpenAI API 사용합니다: `run_v5_scoring.py`(matcher), `build_golden_dataset_v3.py`(평가), 추출기.
- 실행 전 `.env`에 `OPENAI_API_KEY`가 필요합니다(BOM 없이 UTF-8, gitignore 대상).
- 팀 공용 한도($20)를 공유합니다. 대규모 채점·재추출은 잔여 예산을 확인하고 실행하세요.
- 캐시가 있으면 재호출이 0입니다. 불필요한 `--force` 재추출은 피하세요(8문서 전체 재추출 약 $2.6).

---

## API 유료 사용 정책

<a href="https://github.com/orgs/Codeit-Part3-5Team/discussions/121">바로 가기</a>

---

## 트러블슈팅

| 담당 | 증상 | 원인 | 해결 |
|------|------|------|------|
| 데이터 | 한글 파일이 깨진 채 저장됨 | PowerShell Get-Content/Set-Content가 CP949로 처리 | Python io.open(encoding="utf-8")로 읽고 쓰기 |
| 데이터 | 콘솔에서 한글·기호가 깨져 보임 | 콘솔 출력 인코딩이 CP949 | PYTHONIOENCODING=utf-8 설정 후 실행 |
| 데이터| build_chunks 실행 시 입력 파일 없음 | 마스킹본이 data/processed/에 없음 | 드라이브에서 masked_documents_v3.json 수령 후 배치 |
| 데이터| scan_3stage/build_manifest/골든셋 빌드 에러 | enriched 청크가 data/processed/에 없음 | 드라이브에서 enriched 청크 수령 후 배치 (청킹 이후 단계) |
| 데이터| run_v5_scoring.py 실행 시 파일 없음 에러 | gold(v5_gold_questions.json)가 없음 | make_v5_loader.py로 생성하거나 드라이브 수령 |
| 데이터| 채점이 예상보다 느리고 비용이 큼 | 캐시 미스로 matcher 신규 호출 | 캐시 배치 확인. 캐시 히트 시 재호출 0 |
| 검색 | followup 질문("그럼 이 사업은...") 검색 완전 실패 (HR@5 0.0~0.2) | history 없이 지시어 그대로 벡터 검색에 투입 → retriever가 지시어를 해소 못함 | query_rewriter.py로 질문을 독립 문장으로 재작성 후 검색 (HR@5 1.000으로 개선) |
| 검색 | single_doc 질문의 15%가 정답 청크 5위 밖으로 밀림 | 사업명·기관명 표기 변형(줄임말 등)을 벡터 유사도만으로 처리 못함 | agency 메타 필터 3단계 매칭(exact→별칭사전→rapidfuzz) 적용, _resolve_agency |
| 검색 | agency + project_name 동시 필터링 시 오히려 성능 하락 | project_name은 fallback 없는 단순 substring 매칭이라, 파서가 사업명을 잘못 추출하면 AND 조건으로 정답 청크까지 걸러짐 | project_name 필터 빼고 agency만 필터링(agency-only)으로 최종 채택 |
| 검색 | agency 필터 매칭 실패/0건 시 검색 결과 자체가 0개로 실패 | 기관명 매핑 안 되면 그대로 빈 결과 반환 | re_retrieve_fn으로 agency 필터 자동 스킵 후 재검색(fallback) 추가 |
| 검색 | Reranking(ms-marco, bge-reranker-large) 적용 시 오히려 MRR 하락 | ms-marco는 영어 데이터셋 학습 모델이라 한국어 공공조달 도메인 판별력 없음 / bge-reranker-large도 범용이라 FAISS 임베딩 순위를 오히려 역전시킴 | reranking 최종 미채택. 한국어 특화 cross-encoder 재검토는 향후 과제로 남김 |
| 검색 | rerank_top_n=20에서는 21위 밖 정답 문서를 rerank가 아예 못 봄, top_n=100으로 늘리면 레이턴시 10배(4.8s→44.8s) 증가 + 성능도 저하 | rerank 후보 범위와 레이턴시가 트레이드오프 관계 | 범위 확대·축소 둘 다 실패 → reranking 자체를 파이프라인에서 제외 |
| 검색 | Multi-query RRF 적용 후 multi_doc Context Precision 대폭 하락(0.688→0.560) | MMR 결과에 score 메타데이터가 없어 RRF 정렬이 사실상 무의미 / 중복 제거 시 후보가 오히려 줄어듦 / 무관 문서가 복수 쿼리에서 중복 노출돼 상위권 진입 | multi-query 최종 드롭. RRF 대신 메타데이터 직접 쿼리 방식 검토를 향후 과제로 남김 |
| 검색 | 임베딩 모델 교체(OpenAI text-embedding-3-small → bge-m3) 시 기존 FAISS 인덱스로 검색하면 깨짐 |인덱스는 임베딩 모델(차원·벡터 공간)에 종속적이라 다른 모델의 벡터와 혼용 불가 | build_index_hf.py로 별도 인덱스(data/faiss_index_bge) 새로 빌드, 기존 인덱스와 분리 관리 |
| 생성 | 프론트에서 "서버 연결 실패" 표시 | 백엔드(:8000) 미기동 또는 API 주소 불일치 | `python -m backend.main` 기동 확인 + 프론트 `REACT_APP_API_URL` 점검 |
| 생성 | `python backend/pipeline.py` 실행 시 `ModuleNotFoundError: backend` | 하위 폴더에서 실행 | 프로젝트 루트에서 `python -m backend.pipeline` 형식으로 실행 |
| 생성 | 라우트 C 체크리스트가 문서당 수 분 소요 | 캐시 미스로 라이브 추출 | `data/eval_cache/extractions/`에 추출 캐시 배치(히트 시 즉시) |

---

## 데이터 처리 정책

<a href="https://github.com/orgs/Codeit-Part3-5Team/discussions/152">바로 가기</a>

---

## 라이선스

본 프로젝트는 [gpt-5-mini](https://developers.openai.com/api/docs/models/gpt-5-mini) OpenAI API 사용합니다.

---
