"""
watcher.py
docs/ 폴더를 감시하다가 PDF 추가/수정 시 자동으로 ingest 실행

실행: python watcher.py  (app.py와 별도 터미널에서 실행)

확장 포인트:
  - APScheduler + EUR-Lex 크롤러를 연동하면 완전 자동화 가능
  - 크롤러가 docs/ 폴더에 PDF를 저장하면 watcher가 자동으로 감지
"""

import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ingest import ingest_pdf

DOCS_DIR = "./docs"


class PDFHandler(FileSystemEventHandler):
    """PDF 파일 이벤트 핸들러"""

    def on_created(self, event):
        """새 파일이 추가될 때"""
        if not event.is_directory and event.src_path.endswith(".pdf"):
            print(f"\n[watcher] 새 PDF 감지: {event.src_path}")
            self._safe_ingest(event.src_path)

    def on_modified(self, event):
        """기존 파일이 수정될 때"""
        if not event.is_directory and event.src_path.endswith(".pdf"):
            print(f"\n[watcher] PDF 수정 감지: {event.src_path}")
            self._safe_ingest(event.src_path)

    def on_deleted(self, event):
        """파일이 삭제될 때 (로그만 출력)"""
        if not event.is_directory and event.src_path.endswith(".pdf"):
            filename = os.path.basename(event.src_path)
            print(f"\n[watcher] PDF 삭제 감지: {filename} (DB에서 수동 삭제 필요)")

    def _safe_ingest(self, pdf_path: str):
        """파일이 완전히 저장될 때까지 잠시 대기 후 ingest"""
        time.sleep(1)  # 파일 쓰기 완료 대기
        try:
            ingest_pdf(pdf_path)
        except Exception as e:
            print(f"[watcher] ingest 오류: {e}")


def start_watching():
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)

    handler  = PDFHandler()
    observer = Observer()
    observer.schedule(handler, path=DOCS_DIR, recursive=False)
    observer.start()

    print(f"[watcher] '{DOCS_DIR}' 폴더 감시 시작 ✅")
    print("[watcher] PDF를 폴더에 넣으면 자동으로 벡터DB에 반영됩니다.")
    print("[watcher] 종료: Ctrl+C\n")

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[watcher] 감시 종료")

    observer.join()


if __name__ == "__main__":
    start_watching()
