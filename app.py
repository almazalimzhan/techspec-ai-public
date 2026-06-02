import streamlit as st

from logging_utils import log_usage
from services import analyze_risks, answer_question, extract_json_fields, generate_summary, prepare_document
from ui_texts import UI


st.set_page_config(page_title="AI Анализ техспецификации", layout="wide")

language = st.sidebar.selectbox("Тіл / Язык", ["Русский", "Қазақша"])
T = UI[language]
st.title(T["title"])
st.caption(T["caption"])

with st.sidebar:
    st.header(T["sidebar_header"])
    pdf_file = st.file_uploader(T["upload_label"], type=["pdf"])
    customer_bin = st.text_input(T["bin_label"], placeholder=T["bin_placeholder"], max_chars=12)
    st.markdown("---")
    st.caption(T["bin_note"])
    st.caption(T["models_note"])

for key, default in {
    "chunks": None,
    "index": None,
    "doc_ready": False,
    "raw_text_preview": "",
    "key_fields": {},
    "last_filename": None,
    "last_language": None,
    "summary_result": "",
    "json_result": "",
    "risk_result": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

current_file = pdf_file.name if pdf_file else None
if current_file != st.session_state.last_filename or language != st.session_state.last_language:
    st.session_state.doc_ready = False
    st.session_state.chunks = None
    st.session_state.index = None
    st.session_state.raw_text_preview = ""
    st.session_state.key_fields = {}
    st.session_state.summary_result = ""
    st.session_state.json_result = ""
    st.session_state.risk_result = ""
    st.session_state.last_filename = current_file
    st.session_state.last_language = language

bin_valid = customer_bin.isdigit() and len(customer_bin) == 12

if pdf_file and not st.session_state.doc_ready:
    with st.spinner("PDF өңделуде..." if language == "Қазақша" else "Читаю PDF и строю индекс..."):
        pdf_bytes = pdf_file.getvalue()
        try:
            chunks, index, preview, key_fields = prepare_document(pdf_bytes, language)
        except ValueError:
            st.error(T["extract_error"])
        else:
            st.session_state.chunks = chunks
            st.session_state.index = index
            st.session_state.doc_ready = True
            st.session_state.raw_text_preview = preview
            st.session_state.key_fields = key_fields

    if st.session_state.doc_ready:
        st.success(T["ready"].format(n=len(st.session_state.chunks)))

with st.expander(T["extract_preview"]):
    if st.session_state.raw_text_preview:
        st.text(st.session_state.raw_text_preview)
    else:
        st.write(T["preview_empty"])

st.markdown(f"## {T['quick_analysis']}")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button(T["summary_btn"], use_container_width=True):
        if not st.session_state.doc_ready:
            st.warning(T["need_pdf"])
        elif not bin_valid:
            st.warning(T["need_bin"])
        else:
            log_usage(customer_bin, language, current_file or "", interface="streamlit")
            with st.spinner(T["summary_spinner"]):
                st.session_state.summary_result = generate_summary(
                    st.session_state.chunks,
                    st.session_state.index,
                    customer_bin,
                    language,
                    st.session_state.key_fields,
                )

with col2:
    if st.button(T["json_btn"], use_container_width=True):
        if not st.session_state.doc_ready:
            st.warning(T["need_pdf"])
        elif not bin_valid:
            st.warning(T["need_bin"])
        else:
            log_usage(customer_bin, language, current_file or "", interface="streamlit")
            with st.spinner(T["json_spinner"]):
                st.session_state.json_result = extract_json_fields(
                    st.session_state.chunks,
                    st.session_state.index,
                    customer_bin,
                    language,
                    st.session_state.key_fields,
                )

with col3:
    if st.button(T["risk_btn"], use_container_width=True):
        if not st.session_state.doc_ready:
            st.warning(T["need_pdf"])
        else:
            try:
                log_usage(customer_bin, language, current_file or "", interface="streamlit")
                with st.spinner(T["risk_spinner"]):
                    st.session_state.risk_result = analyze_risks(
                        st.session_state.chunks,
                        st.session_state.index,
                        language,
                        st.session_state.key_fields,
                    )
            except Exception as exc:
                st.error(f"{T['risk_error']}: {exc}")

if st.session_state.summary_result:
    st.markdown(f"### {T['summary_header']}")
    st.write(st.session_state.summary_result)
    st.download_button(
        label=T["download_summary"],
        data=st.session_state.summary_result.encode("utf-8"),
        file_name="summary.txt",
        mime="text/plain",
    )

if st.session_state.json_result:
    st.markdown(f"### {T['json_header']}")
    st.code(st.session_state.json_result, language="json")
    st.download_button(
        label=T["download_json"],
        data=st.session_state.json_result.encode("utf-8"),
        file_name="fields.json",
        mime="application/json",
    )

if st.session_state.risk_result:
    st.markdown(f"### {T['risk_header']}")
    st.write(st.session_state.risk_result)

st.markdown("---")
st.markdown(f"## {T['qa_header']}")

question = st.text_input(
    T["qa_input"],
    placeholder=T["qa_placeholder"],
)

if st.button(T["ask_btn"], type="primary", use_container_width=False):
    if not st.session_state.doc_ready:
        st.warning(T["need_pdf"])
    elif not question.strip():
        st.warning(T["need_question"])
    else:
        log_usage(customer_bin, language, current_file or "", interface="streamlit")
        with st.spinner(T["thinking"]):
            ans, used_ctx = answer_question(
                question.strip(),
                st.session_state.chunks,
                st.session_state.index,
                language,
                st.session_state.key_fields,
            )
        st.markdown(f"### {T['answer_header']}")
        st.write(ans)

        with st.expander(T["ctx_header"]):
            st.text(used_ctx)

st.markdown("---")
st.markdown(f"## {T['fast_questions']}")

if st.session_state.doc_ready:
    cols = st.columns(2)
    for i, q in enumerate(T["demo_qs"]):
        with cols[i % 2]:
            if st.button(q, use_container_width=True):
                log_usage(customer_bin, language, current_file or "", interface="streamlit")
                with st.spinner(T["thinking"]):
                    ans, _ = answer_question(
                        q,
                        st.session_state.chunks,
                        st.session_state.index,
                        language,
                        st.session_state.key_fields,
                    )
                st.markdown(f"### {T['answer_header']}")
                st.write(ans)
else:
    st.info(T["fast_info"])
