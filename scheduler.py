"""
scheduler.py
EUR-Lex RSS 피드를 주기적으로 확인하여
EU 화장품 규제(CPR 1223/2009) 관련 새 문서를 자동 감지 → PDF 다운로드 → ingest

실행: python scheduler.py  (app.py와 별도 터미널에서 실행)
종료: Ctrl+C

설치 필요:
    pip install apscheduler feedparser requests
"""

import os
import json
import time
import hashlib
import logging
import feedparser
import requests
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from ingest import ingest_pdf

# ── 로깅 설정 ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────
DOCS_DIR    = "./docs"
SEEN_FILE   = "./seen_documents.json"
CHECK_DAYS = 14                      # 확인 주기 (일)

RSS_FEEDS = [
    {
        "name": "CPR 개정 문서",
        "url":  "https://eur-lex.europa.eu/legal-content/EN/OJ-RSS/?uri=CELEX:32009R1223",
    },
    {
        "name": "EU 관보 화장품 섹션",
        "url":  "https://eur-lex.europa.eu/search-result/rss?type=quick&text=cosmetic+products+regulation&CC_1_CODED=28&DTS_DOM=EU_LAW&typeOfActStatus=REG&DTS_SUBDOM=LEGISLATION&page=1",
    },
]
# ──────────────────────────────────────────────────────


def load_seen() -> set:
    """이미 처리한 문서 ID 불러오기"""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    """처리한 문서 ID 저장"""
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f, indent=2)


def get_pdf_url(entry_link: str) -> str | None:
    """EUR-Lex 문서 링크에서 PDF 다운로드 URL 생성"""
    if not entry_link:
        return None
    if "/TXT/" in entry_link:
        return entry_link.replace("/TXT/", "/TXT/PDF/")
    if "/HTML/" in entry_link:
        return entry_link.replace("/HTML/", "/TXT/PDF/")
    if "uri=" in entry_link:
        params = entry_link.split("?", 1)[1] if "?" in entry_link else ""
        return f"https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?{params}"
    return None


def download_pdf(url: str, filename: str) -> str | None:
    """PDF 다운로드 후 docs/ 폴더에 저장, 저장된 경로 반환"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; EU-Reg-Bot/1.0)"}
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            log.warning(f"다운로드 실패 ({response.status_code}): {url}")
            return None

        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower():
            log.warning(f"PDF가 아닌 파일 스킵: {content_type}")
            return None

        os.makedirs(DOCS_DIR, exist_ok=True)
        filepath = os.path.join(DOCS_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        log.info(f"다운로드 완료: {filename} ({len(response.content) // 1024}KB)")
        return filepath

    except requests.exceptions.Timeout:
        log.error(f"다운로드 타임아웃: {url}")
        return None
    except Exception as e:
        log.error(f"다운로드 오류: {e}")
        return None


def make_filename(entry) -> str:
    """RSS 항목에서 안전한 파일명 생성"""
    title = getattr(entry, "title", "unknown")
    safe  = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    safe  = safe[:60].strip()
    date  = datetime.now().strftime("%Y%m%d")
    return f"{date}_{safe}.pdf"


def check_and_update():
    """RSS 피드 확인 → 새 문서 감지 → PDF 다운로드 → ingest"""
    log.info("EUR-Lex RSS 확인 시작")
    seen      = load_seen()
    new_count = 0

    for feed_info in RSS_FEEDS:
        log.info(f"RSS 확인 중: {feed_info['name']}")
        try:
            feed = feedparser.parse(feed_info["url"])

            if not feed.entries:
                log.info("새 항목 없음")
                continue

            for entry in feed.entries:
                doc_id = hashlib.md5(
                    getattr(entry, "link", getattr(entry, "id", str(entry))).encode()
                ).hexdigest()

                if doc_id in seen:
                    continue

                title = getattr(entry, "title", "Unknown")
                log.info(f"새 문서 감지: {title}")

                link    = getattr(entry, "link", "")
                pdf_url = get_pdf_url(link)

                if pdf_url:
                    filename = make_filename(entry)
                    filepath = download_pdf(pdf_url, filename)

                    if filepath:
                        try:
                            ingest_pdf(filepath)
                            new_count += 1
                        except Exception as e:
                            log.error(f"ingest 오류: {e}")

                seen.add(doc_id)

        except Exception as e:
            log.error(f"RSS 파싱 오류 ({feed_info['name']}): {e}")

    save_seen(seen)

    if new_count > 0:
        log.info(f"완료: {new_count}개 새 문서 반영 ✅")
    else:
        log.info(f"새 문서 없음 — 다음 확인: {CHECK_DAYS}일 후")


def start_scheduler():
    """BackgroundScheduler로 실행 — 터미널 블로킹 없음"""
    log.info("=" * 45)
    log.info("  EU 화장품 규제 자동 업데이트 스케줄러")
    log.info(f"  확인 주기: {CHECK_DAYS}일마다")
    log.info(f"  감시 피드: {len(RSS_FEEDS)}개")
    log.info("=" * 45)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_and_update,
        trigger="interval",
        DAYS=CHECK_DAYS,
        id="eu_reg_check",
        next_run_time=datetime.now(),   # 시작 즉시 1회 실행
    )
    scheduler.start()
    log.info("스케줄러 백그라운드 실행 중 (Ctrl+C로 종료)")

    try:
        while True:
            time.sleep(60)             # 메인 스레드 유지 (CPU 점유 없음)
    except KeyboardInterrupt:
        scheduler.shutdown()
        log.info("스케줄러 종료")


if __name__ == "__main__":
    start_scheduler()
