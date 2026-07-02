---
# 🤖 2026-Agentic-RAG-Project: RFP 문서 요약 & 질문/답변 챗봇

AI 엔지니어 10기 중급 팀 프로젝트 — 경구약제 이미지에서 알약의 **클래스(약품명)** 와 **바운딩 박스**를 검출하는 Object Detection 태스크입니다.

> **기간**: 2026-06-17 ~ 07-08 (3주)  
> **결과물**: 프로젝트 완료 보고서 + GitHub repo 제출

---

## 팀 구성

| 이름 | 역할 | 담당 |
| --- | --- | --- |
| 민재 | PM (Project Manager) | 일정 관리, 이슈 조율, PR 리뷰 |
| 도혁 | DE (Data Engineer) | 문서 청킹 전략 설계 및 검증, 라우트 C 기능 구현 |
| 아인 | DE (Data Engineer) | 문서별 메타데이터 처리, 골든 데이터셋 구축 |
| 재헌 | RE (Retrieval Engineer) | 임베딩 생성, vector DB 구축, retrieval 기법 고도화 |
| 수민 | SD (Service Developer) | 모델 응답 고도화(정확도, 포맷, 길이, 톤 등), 챗봇 서비스 개발 |

---

## 팀 보고서 📊

> **보고서 제출 예정**
<a href="https://github.com/Codeit-Part3-5Team/codeit-part3-5team-project">바로 가기</a>

<!-- <a href="https://Codeit-Part2-2Team.github.io/codeit-part2-2team-project/reports/%EA%B2%BD%EA%B5%AC%EC%95%BD%EC%A0%9C_%EB%B3%B4%EA%B3%A0%EC%84%9C_2%ED%8C%80.pdf">바로 가기</a> -->

---

## 협업일지 및 팀 일간 보고서 📄

<a href="https://github.com/orgs/Codeit-Part3-5Team/discussions">바로 가기</a>

---

## 프로젝트 파이프라인

```
              [사용자 질문]
                   ↓
      [Agentic 파이프라인 (바깥 껍데기)]
                   ↓
             Node: 질문 분석
	               ↓
        ┌─────────────────────┐
        │                     │
        ↓                     ↓
   Node: RAG 검색         Node: 라우트 C
   *하이브리드 구조*       Compliance Validator 도구
   "Naive RAG"           - 필수/반드시 키워드 검색(도구 특화)
   + "Agentic RAG"       - LLM 체크리스트 생성
        │                     │
        └─────────────────────┘
                   ↓
             Node: 답변 생성
                   ↓
               [최종 답변]
```

---

## 프로젝트 구조

```
rfp-chatbot-team5/
├── data/                 # 데이터 ⚠️ .gitignore (NDA)
│   ├── raw/              # 원본 HWP, PDF
│   ├── metadata/         # data_list.csv
│   └── processed/        # 가공 데이터 (청크 JSON 등)
|
├── backend/    ← FastAPI (웹/앱 공통)
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
├── frontend/    # React 웹 프론트엔트
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
# 추후 작성 예정

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
| `validate_golden.py` | 골든셋 라벨 정합성 검증 |
| `check_chunks.py` | 청크 품질 게이트 (중복/과세분화/PUA/토큰) |

**한계:** 정규식 기반 탐지로 자연어 PII(예: "공일공에 일이삼사")·이미지 내 텍스트(OCR 미적용)는 범위 밖이며, 담당자 인명의 정확한 노출 카운트는 NER 도입 시에만 가능합니다.

---

## 라이선스

본 프로젝트는 [gpt-5-mini](https://developers.openai.com/api/docs/models/gpt-5-mini) OpenAI API 사용합니다.

---