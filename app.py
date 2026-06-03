"""
app.py
EU 화장품 규제 Agentic RAG 챗봇
Streamlit UI + Ollama Tool Calling
"""

import json
import os
import streamlit as st
import requests
from datetime import datetime
from tools import TOOLS, TOOL_FUNCTIONS

# ── 설정 ──────────────────────────────────────────────
CHAT_MODEL = "llama3.1"
OLLAMA_URL = "http://localhost:11434"
DOCS_DIR   = "./docs"
SEEN_FILE  = "./seen_documents.json"

SYSTEM_PROMPT = """
당신은 EU 화장품 규정(CPR, Cosmetic Products Regulation) 전문 규제 어시스턴트입니다.

역할:
- EU 화장품 규제(성분 제한, 라벨링, 안전성 평가 등)에 관한 질문에 답변합니다.
- 규제 관련 질문은 반드시 제공된 도구를 사용해 문서를 검색한 뒤 답변하세요.
- 검색 결과에 출처(파일명, 페이지)가 있으면 반드시 인용하세요.
- 잡담이나 EU 규제와 무관한 질문은 도구 없이 간단히 답변하세요.

답변 형식:
- 규제 질문: 핵심 내용 요약 → 세부 내용 → 출처 표기
- 답변은 한국어로 작성하세요.
- 확실하지 않은 내용은 "공식 문서를 직접 확인하세요"라고 안내하세요.

주의: 이 시스템은 참고용이며 법적 효력이 없습니다. 정확한 규제 해석은 전문가에게 문의하세요.
""".strip()

TOOL_LABEL = {
    "search_banned_ingredients":  "🚫 금지/제한 성분 검색",
    "search_labeling_rules":      "🏷️ 라벨링 규정 검색",
    "search_safety_requirements": "🔬 안전성 평가 기준 검색",
}
# ──────────────────────────────────────────────────────


def get_docs_info() -> list[dict]:
    """docs/ 폴더의 PDF 목록과 수정 시각 반환"""
    if not os.path.exists(DOCS_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if fname.endswith(".pdf"):
            fpath = os.path.join(DOCS_DIR, fname)
            mtime = os.path.getmtime(fpath)
            files.append({
                "name": fname,
                "updated_at": datetime.fromtimestamp(mtime),
            })
    # 최신 수정 순 정렬
    return sorted(files, key=lambda x: x["updated_at"], reverse=True)


def get_last_crawled() -> str | None:
    """scheduler가 마지막으로 RSS를 확인한 시각 반환"""
    if not os.path.exists(SEEN_FILE):
        return None
    mtime = os.path.getmtime(SEEN_FILE)
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def chat_with_tools(messages: list):
    """
    Ollama Tool Calling API 호출 — Agentic RAG 핵심 로직
    반환: (답변 텍스트, 사용된 도구 이름 리스트)
    """
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model":   CHAT_MODEL,
            "messages": messages,
            "tools":   TOOLS,
            "stream":  False,
        }
    )
    response.raise_for_status()
    msg = response.json()["message"]

    if msg.get("tool_calls"):
        tool_results = []
        tools_used   = []

        for tool_call in msg["tool_calls"]:
            fn_name = tool_call["function"]["name"]
            fn_args = tool_call["function"]["arguments"]
            if isinstance(fn_args, str):
                fn_args = json.loads(fn_args)

            if fn_name in TOOL_FUNCTIONS:
                result_text = TOOL_FUNCTIONS[fn_name](**fn_args)
                tools_used.append(fn_name)
            else:
                result_text = f"알 수 없는 도구: {fn_name}"

            tool_results.append({"role": "tool", "content": result_text})

        final = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model":    CHAT_MODEL,
                "messages": messages + [msg] + tool_results,
                "stream":   False,
            }
        )
        final.raise_for_status()
        return final.json()["message"]["content"], tools_used

    return msg["content"], []


# ── Streamlit UI ───────────────────────────────────────
st.set_page_config(
    page_title="EU 화장품 규제 Q&A",
    page_icon="🇪🇺",
    layout="wide",
)

# ── 사이드바 — 문서 현황 ───────────────────────────────
with st.sidebar:
    st.header("📂 규제 문서 현황")

    docs = get_docs_info()
    last_crawled = get_last_crawled()

    # 마지막 RSS 확인 시각
    if last_crawled:
        st.success(f"🔄 마지막 업데이트 자동 확인\n\n**{last_crawled}**")
    else:
        st.warning("🔄 자동 확인 기록 없음\n\n`python scheduler.py` 실행 필요")

    st.divider()

    # 등록된 문서 목록
    if docs:
        st.markdown(f"**등록 문서 ({len(docs)}개)**")
        for doc in docs:
            updated = doc["updated_at"].strftime("%Y-%m-%d %H:%M")
            st.markdown(f"""
<div style="padding:8px 0; border-bottom:1px solid #eee;">
  <div style="font-size:0.85em; font-weight:600; word-break:break-all;">
    📄 {doc['name']}
  </div>
  <div style="font-size:0.75em; color:#888; margin-top:2px;">
    업데이트: {updated}
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("docs/ 폴더에 PDF가 없습니다.")

    st.divider()

    # 새로고침 버튼
    if st.button("🔃 현황 새로고침"):
        st.rerun()


# ── 메인 화면 ──────────────────────────────────────────
st.title("🇪🇺 EU 화장품 규제 Q&A")
st.caption("EU CPR(Cosmetic Products Regulation) 기반 Agentic RAG 챗봇")

with st.expander("💡 사용법 & 예시 질문"):
    st.markdown("""
**예시 질문:**
- 파라벤의 EU 허용 농도 기준이 어떻게 돼?
- CPNP 신고 절차가 궁금해
- 화장품 라벨에 반드시 표시해야 하는 항목은?
- EU에서 동물실험 금지 규정은 어떻게 돼?
- 레티놀 함량 제한이 있어?
    """)

# 대화 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 기록 출력
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            if msg.get("tools_used"):
                for t in msg["tools_used"]:
                    st.caption(TOOL_LABEL.get(t, t))
            else:
                st.caption("🧠 일반 답변")
            st.write(msg["content"])

# 입력창
if user_input := st.chat_input("EU 화장품 규제에 대해 질문하세요..."):

    with st.chat_message("user"):
        st.write(user_input)

    st.session_state.messages.append({
        "role":    "user",
        "content": user_input,
    })

    with st.chat_message("assistant"):
        with st.spinner("🔍 규제 문서 검색 중..."):
            try:
                ollama_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT}
                ] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]

                answer, tools_used = chat_with_tools(ollama_messages)

                if tools_used:
                    for t in tools_used:
                        st.caption(TOOL_LABEL.get(t, t))
                else:
                    st.caption("🧠 일반 답변")

                st.write(answer)

                st.session_state.messages.append({
                    "role":       "assistant",
                    "content":    answer,
                    "tools_used": tools_used,
                })

            except requests.exceptions.ConnectionError:
                st.error("Ollama 서버에 연결할 수 없습니다. `ollama serve` 실행 여부를 확인하세요.")
            except Exception as e:
                st.error(f"오류 발생: {e}")

# 대화 초기화 버튼
if st.session_state.messages:
    if st.button("🗑️ 대화 초기화"):
        st.session_state.messages = []
        st.rerun()
