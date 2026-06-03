# 🇪🇺 EU 화장품 규제 Q&A — Agentic RAG

EU 화장품 규정(CPR 1223/2009)을 로컬 LLM으로 검색하는 **Agentic RAG 챗봇**.  
EUR-Lex RSS 피드를 감지해 새 규제 문서를 자동으로 다운로드 · 반영합니다.

> ⚠️ 참고용 시스템입니다. 정확한 규제 해석은 전문가에게 문의하세요.

---

## 동작 방식

```
사용자 질문
    ↓
LLM 판단 (Tool Calling)
    ├─ 금지/제한 성분 질문  → search_banned_ingredients()
    ├─ 라벨링/표시 질문     → search_labeling_rules()
    ├─ 안전성 평가 질문     → search_safety_requirements()
    └─ 잡담/일반 질문       → 바로 답변

ChromaDB에서 관련 청크 검색 → 출처(파일명, 페이지) 포함 답변
```

**자동 업데이트 흐름**
```
APScheduler (24시간마다)
    ↓
EUR-Lex RSS 피드 확인
    ↓ 새 문서 감지 시
PDF 자동 다운로드 → docs/ 저장
    ↓
ChromaDB 자동 업데이트 → 챗봇 즉시 반영 ✅
```

---

## 설치 & 실행

### 0) 사전 준비

```bash
# Ollama 모델 설치 (최초 1회)
ollama pull llama3.1
ollama pull nomic-embed-text
```

### 1) 패키지 설치

```bash
pip install -r requirements.txt
```

### 2) EU 규제 PDF 준비

`docs/` 폴더에 EU CPR 관련 PDF를 저장합니다.

추천 문서 (EUR-Lex에서 무료 다운로드):
- [CPR 통합본 2026](https://eur-lex.europa.eu/eli/reg/2009/1223/2026-05-01/eng) — Annex II 금지성분 + Annex III 제한성분 포함
- [SCCS Notes of Guidance 12th revision](https://health.ec.europa.eu/publications/sccs-notes-guidance-testing-cosmetic-ingredients-and-their-safety-evaluation-12th-revision_en) — 안전성 평가 기준

```
docs/
├── CPR_1223_2009_2026.pdf
└── SCCS_guidance_12th.pdf
```

### 3) 벡터DB 생성

```bash
python ingest.py
```

### 4) 앱 실행

```bash
# 터미널 1 — Ollama 서버
ollama serve

# 터미널 2 — 챗봇 UI
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

### 5) 자동 업데이트 실행 (선택)

EUR-Lex에서 새 규제 문서를 자동으로 감지·반영하려면:

```bash
# 터미널 3 — EUR-Lex 자동 크롤러
python scheduler.py
```

수동으로 PDF를 추가할 때 자동 반영하려면:

```bash
# 터미널 3 — 폴더 감시
python watcher.py
```

---

## 파일 구성

```
eu-cosmetic-rag/
├── docs/                   # EU 규제 PDF 저장 폴더
├── chroma_db/              # 벡터DB (자동 생성)
├── seen_documents.json     # 처리된 문서 ID 기록 (자동 생성)
├── ingest.py               # PDF 파싱 → 청크 → 임베딩 → ChromaDB 저장
├── tools.py                # Agentic 도구 3개 정의
├── watcher.py              # docs/ 폴더 감시 → 자동 ingest
├── scheduler.py            # EUR-Lex RSS 감지 → PDF 자동 다운로드 → ingest
├── app.py                  # Streamlit 챗봇 + Agentic RAG 로직
└── requirements.txt
```

| 파일 | 역할 |
|------|------|
| `ingest.py` | PDF 파싱 → 청크 분할 → 임베딩 → ChromaDB 저장 |
| `tools.py` | Agentic 도구 3개 정의 (성분 / 라벨링 / 안전성) |
| `watcher.py` | docs/ 폴더 감시 → 새 PDF 자동 ingest |
| `scheduler.py` | EUR-Lex RSS 피드 감시 → PDF 자동 다운로드 → ingest |
| `app.py` | Streamlit 챗봇 + Agentic RAG 로직 + 사이드바 문서 현황 |

---

## 기술 스택

| 역할 | 도구 |
|------|------|
| LLM | Ollama `llama3.1` |
| 임베딩 | Ollama `nomic-embed-text` |
| 벡터 DB | ChromaDB |
| PDF 파싱 | PyMuPDF |
| 파일 감시 | Watchdog |
| 자동 크롤링 | APScheduler + feedparser |
| UI | Streamlit |

**사이드바 표시 정보**
- 🔄 마지막 자동 확인 일시 (`seen_documents.json` 수정 시각 기준)
- 📄 등록된 PDF 목록 + 각 문서 업데이트 일시 (`docs/` 파일 수정 시각 기준)
- 🔃 현황 새로고침 버튼

---

## 예시 질문

| 유형 | 질문 예시 |
|------|-----------|
| 성분 규제 | "파라벤의 EU 허용 농도 기준이 뭐야?" |
| 성분 규제 | "레티놀 함량 제한이 있어?" |
| 라벨링 | "화장품 라벨에 반드시 표시해야 하는 항목은?" |
| 라벨링 | "INCI 명칭 표기 의무가 있어?" |
| 안전성 | "CPSR 안전성 평가에 포함되어야 하는 항목은?" |
| 안전성 | "EU에서 동물실험 금지 규정은?" |

---

## MediGuideRAG 대비 차별점

| 항목 | MediGuideRAG | 이 프로젝트 |
|------|-------------|------------|
| 문서 형태 | `.md` 단일 파일 | PDF 멀티 문서 |
| 문서 업데이트 | 수동 재실행 | EUR-Lex RSS 자동 감지 + 다운로드 |
| Agentic 도구 수 | 1개 | 3개 |
| 도메인 | 의료 참고 | 실무 규제 (비즈니스) |
