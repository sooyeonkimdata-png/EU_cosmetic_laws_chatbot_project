"""
tools.py
Agentic RAG 도구 3개 정의
LLM이 질문 유형에 따라 적절한 도구를 선택해서 호출
"""

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ── 설정 ──────────────────────────────────────────────
CHROMA_DIR  = "./chroma_db"
COLLECTION  = "eu_cosmetic_regs"
EMBED_MODEL = "nomic-embed-text"
OLLAMA_URL  = "http://localhost:11434"
TOP_K       = 3   # 검색 시 반환할 청크 수
# ──────────────────────────────────────────────────────


def _get_collection():
    embed_fn = OllamaEmbeddingFunction(
        model_name=EMBED_MODEL,
        url=f"{OLLAMA_URL}/api/embeddings",
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=embed_fn,
    )


def _search(query: str, where_filter: dict | None = None) -> str:
    """공통 벡터 검색 함수"""
    collection = _get_collection()

    kwargs = {"query_texts": [query], "n_results": TOP_K}
    if where_filter:
        kwargs["where"] = where_filter

    results = collection.query(**kwargs)

    if not results["documents"][0]:
        return "관련 규제 문서를 찾을 수 없습니다."

    output = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        source = f"[{meta['filename']} — {meta['page']}p]"
        output.append(f"{source}\n{doc}")

    return "\n\n---\n\n".join(output)


# ── 도구 1: 금지/제한 성분 검색 ────────────────────────
def search_banned_ingredients(query: str) -> str:
    """
    EU CPR에서 금지·제한된 성분, 농도 기준, 허용 조건을 검색합니다.
    예) 파라벤 함량 기준, 레티놀 제한 농도, CMR 물질 목록
    """
    return _search(query)


# ── 도구 2: 라벨링·표시 규정 검색 ──────────────────────
def search_labeling_rules(query: str) -> str:
    """
    EU CPR의 라벨링 요건, 표시 의무 사항, CPNP 신고 절차를 검색합니다.
    예) 성분 표시 순서, 유통기한 표기, 경고 문구 의무, INCI 명칭
    """
    return _search(query)


# ── 도구 3: 안전성 평가 기준 검색 ──────────────────────
def search_safety_requirements(query: str) -> str:
    """
    EU CPR의 안전성 평가(CPSR), PIF 기술문서 요건, 책임자(RP) 의무를 검색합니다.
    예) 안전성 평가 항목, 동물실험 금지 규정, GMP 기준
    """
    return _search(query)


# ── 도구 목록 (app.py에서 LLM에 전달) ──────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_banned_ingredients",
            "description": search_banned_ingredients.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 성분명 또는 규제 내용"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_labeling_rules",
            "description": search_labeling_rules.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 라벨링 또는 표시 관련 내용"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_safety_requirements",
            "description": search_safety_requirements.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 안전성 평가 또는 기술문서 관련 내용"
                    }
                },
                "required": ["query"]
            }
        }
    },
]

# 도구 이름 → 함수 매핑
TOOL_FUNCTIONS = {
    "search_banned_ingredients":  search_banned_ingredients,
    "search_labeling_rules":      search_labeling_rules,
    "search_safety_requirements": search_safety_requirements,
}
