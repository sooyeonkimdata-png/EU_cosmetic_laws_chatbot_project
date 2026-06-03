"""
ingest.py
EU 화장품 규제 PDF → 텍스트 추출 → 청크 분할 → 임베딩 → ChromaDB 저장
"""

import os
import hashlib
import fitz  # PyMuPDF
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ── 설정 ──────────────────────────────────────────────
DOCS_DIR   = "./docs"          # EU 규제 PDF 저장 폴더
CHROMA_DIR = "./chroma_db"     # 벡터DB 저장 경로
COLLECTION = "eu_cosmetic_regs"

EMBED_MODEL = "nomic-embed-text"   # ollama pull nomic-embed-text
OLLAMA_URL  = "http://localhost:11434"

CHUNK_SIZE    = 500   # 청크당 문자 수
CHUNK_OVERLAP = 50    # 청크 간 오버랩 문자 수
# ──────────────────────────────────────────────────────


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """PDF에서 페이지별 텍스트 추출"""
    doc = fitz.open(pdf_path)
    pages = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            pages.append({"page": page_num, "text": text})
    doc.close()
    return pages


def split_into_chunks(pages: list[dict], filename: str) -> list[dict]:
    """페이지 텍스트를 청크로 분할"""
    chunks = []
    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page"]

        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunk_id = hashlib.md5(
                    f"{filename}-{page_num}-{start}".encode()
                ).hexdigest()

                chunks.append({
                    "id":       chunk_id,
                    "text":     chunk_text,
                    "filename": filename,
                    "page":     page_num,
                })

            start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def get_chroma_collection():
    """ChromaDB 컬렉션 반환"""
    embed_fn = OllamaEmbeddingFunction(
        model_name=EMBED_MODEL,
        url=f"{OLLAMA_URL}/api/embeddings",
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=embed_fn,
    )
    return collection


def ingest_pdf(pdf_path: str):
    """PDF 1개를 파싱 → 청크 → ChromaDB 저장"""
    filename = os.path.basename(pdf_path)
    print(f"[ingest] 처리 중: {filename}")

    pages  = extract_text_from_pdf(pdf_path)
    chunks = split_into_chunks(pages, filename)

    if not chunks:
        print(f"[ingest] 텍스트 없음, 스킵: {filename}")
        return

    collection = get_chroma_collection()

    # 기존 문서 삭제 후 재저장 (업데이트 대응)
    existing = collection.get(where={"filename": filename})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        print(f"[ingest] 기존 데이터 삭제: {len(existing['ids'])}개 청크")

    collection.add(
        ids        = [c["id"]   for c in chunks],
        documents  = [c["text"] for c in chunks],
        metadatas  = [{"filename": c["filename"], "page": c["page"]} for c in chunks],
    )

    print(f"[ingest] 완료: {len(chunks)}개 청크 저장 ({filename})")


def ingest_all():
    """docs/ 폴더의 모든 PDF 처리"""
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"[ingest] '{DOCS_DIR}' 폴더를 생성했습니다. PDF를 넣어주세요.")
        return

    pdf_files = [f for f in os.listdir(DOCS_DIR) if f.endswith(".pdf")]

    if not pdf_files:
        print(f"[ingest] '{DOCS_DIR}' 폴더에 PDF가 없습니다.")
        return

    print(f"[ingest] 총 {len(pdf_files)}개 PDF 처리 시작")
    for pdf_file in pdf_files:
        ingest_pdf(os.path.join(DOCS_DIR, pdf_file))

    print("[ingest] 전체 완료 ✅")


if __name__ == "__main__":
    ingest_all()
