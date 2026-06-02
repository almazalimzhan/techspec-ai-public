import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import faiss

from config import QA_TOP_K, RISK_TOP_K
from embeddings import build_index
from llm_clients import call_alemllm, ensure_language, llm_chat
from pdf_utils import chunk_text, clean_text, extract_pages_by_language
from prompts import (
    JSON_SYSTEM_PROMPT_KZ_TEMPLATE,
    JSON_SYSTEM_PROMPT_RU_TEMPLATE,
    QA_SYSTEM_PROMPT_KZ,
    QA_SYSTEM_PROMPT_RU,
    RISK_SYSTEM_PROMPT_KZ,
    RISK_SYSTEM_PROMPT_RU,
    SUMMARY_SYSTEM_PROMPT_KZ_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT_RU_TEMPLATE,
)
from retrieval import retrieve_context, retrieve_multi

logger = logging.getLogger(__name__)

QUESTION_HINT_RULES = (
    (
        ("адрес", "место", "мекен"),
        " (синонимы: место поставки, адрес оказания услуг, точка подключения, место выполнения работ)",
    ),
    (
        ("срок", "мерзім"),
        " (уточни: срок поставки, срок оказания услуг, срок подключения)",
    ),
    (
        ("оплат", "төлем", "предоплат"),
        " (синонимы: условия оплаты, порядок расчетов, аванс)",
    ),
)

LANGUAGE_SETTINGS = {
    "Русский": {
        "lang_code": "ru",
        "document_label": "Фрагменты документа",
        "question_label": "Вопрос",
        "summary_queries": [
            "Заказчик, организатор, БИН, что закупается, сроки",
            "Бюджет, сумма без НДС, цена, тариф, тенге, условия оплаты, аванс",
            "Технические требования, скорость, риски, штрафы",
        ],
        "summary_system_prompt_template": SUMMARY_SYSTEM_PROMPT_RU_TEMPLATE,
        "json_queries": [
            "Заказчик, организатор, БИН, номер закупки, лот, способ закупки, что закупается, адрес",
            "Срок оказания услуг, поставки или выполнения работ, бюджет, сумма без НДС, цена, тенге, условия оплаты",
            "Квалификационные требования, подтверждающие документы, технические требования, ограничения, риски, штрафы",
        ],
        "json_system_prompt_template": JSON_SYSTEM_PROMPT_RU_TEMPLATE,
        "json_instruction": "Верни ТОЛЬКО JSON — без текста до и после, без markdown, без пояснений.",
        "risk_query": "Найди ключевые риски и ограничения для поставщика",
        "risk_system_prompt": RISK_SYSTEM_PROMPT_RU,
        "qa_system_prompt": QA_SYSTEM_PROMPT_RU,
    },
    "Қазақша": {
        "lang_code": "kz",
        "document_label": "Құжат үзінділері",
        "question_label": "Сұрақ",
        "summary_queries": [
            "Тапсырыс беруші, БСН, не сатып алынады, мерзімдер",
            "Бюджет, НДС-сіз сомасы, баға, теңге, төлем шарттары, аванс",
            "Техникалық талаптар, жылдамдық, тәуекелдер, айыппұл",
        ],
        "summary_system_prompt_template": SUMMARY_SYSTEM_PROMPT_KZ_TEMPLATE,
        "json_queries": [
            "Тапсырыс беруші, БСН, сатып алу нөмірі, лот, не сатып алынады, мекенжай",
            "Қызмет көрсету, жеткізу немесе жұмыс орындау мерзімі, бюджет, ҚҚС-сыз сома, баға, теңге, төлем шарттары",
            "Біліктілік талаптары, растайтын құжаттар, техникалық талаптар, шектеулер, тәуекелдер, айыппұлдар",
        ],
        "json_system_prompt_template": JSON_SYSTEM_PROMPT_KZ_TEMPLATE,
        "json_instruction": "Тек JSON қайтар.",
        "risk_query": "Жеткізуші үшін негізгі тәуекелдер мен шектеулерді тап",
        "risk_system_prompt": RISK_SYSTEM_PROMPT_KZ,
        "qa_system_prompt": QA_SYSTEM_PROMPT_KZ,
    },
}


def _get_language_settings(language: str) -> Dict[str, object]:
    if language == "Қазақша":
        return LANGUAGE_SETTINGS["Қазақша"]
    return LANGUAGE_SETTINGS["Русский"]


def _apply_question_hints(question: str, q_low: str) -> str:
    for triggers, suffix in QUESTION_HINT_RULES:
        if any(token in q_low for token in triggers):
            question += suffix
    return question


def _call_text_model(language: str, system_prompt: str, user_prompt: str, temperature: float = 0) -> str:
    if language == "Қазақша":
        return call_alemllm(user_prompt, system_prompt)
    return ensure_language(llm_chat(system_prompt, user_prompt, temperature=temperature), language)


def _call_structured_model(language: str, system_prompt: str, user_prompt: str) -> str:
    if language == "Қазақша":
        return call_alemllm(user_prompt, system_prompt)
    return llm_chat(system_prompt, user_prompt, temperature=0)


# ── Keyword-поиск для числовых данных ─────────────────────────────────────

_FINANCIAL_KEYWORDS = {
    "ru": ["сумма", "бюджет", "цена", "тариф", "тенге", "млн", "млрд", "ндс", "оплат", "аванс", "стоимост"],
    "kz": ["сома", "бюджет", "баға", "тариф", "теңге", "млн", "млрд", "ққс", "төлем", "аванс"],
}
_DATE_KEYWORDS = {
    "ru": ["срок", "дней", "месяц", "календар", "рабочих", "до ", "не позднее"],
    "kz": ["мерзім", "күн", "ай", "күнтізбелік", "жұмыс", "дейін"],
}


def _keyword_chunks(chunks: List[str], keywords: List[str], max_chunks: int = 5) -> str:
    hits = []
    for chunk in chunks:
        low = chunk.lower()
        if any(kw in low for kw in keywords):
            hits.append(chunk)
        if len(hits) >= max_chunks:
            break
    return "\n---\n".join(hits)


def _is_list_chunk(chunk: str) -> bool:
    """
    Определяет чанки-списки населённых пунктов.
    Признаки: много коротких строк, мало цифровых строк.
    Такие чанки бесполезны для финансового поиска.
    """
    lines = [l.strip() for l in chunk.splitlines() if l.strip()]
    if len(lines) < 4:
        return False
    avg_len = sum(len(l) for l in lines) / len(lines)
    digit_lines = sum(1 for l in lines if re.search(r"\d", l))
    return avg_len < 60 and digit_lines / len(lines) < 0.3


# ── Извлечение шапки документа из сырого текста ───────────────────────────

def _extract_header_block(text: str) -> str:
    """
    Извлекает шапку техспека (таблицу с заказчиком, суммой, сроком) из сырого текста.

    На больших PDF (28+ стр. со списком 329 сёл) keyword-поиск по "тенге/сумма"
    находит чанки из списков и вытесняет шапку. Решение: ищем шапку regex'ом
    до раздела "Описание требуемых характеристик".
    """
    end_pattern = re.compile(
        r"Описание требуемых характеристик"
        r"|Талап етілетін сипаттамалардың"
        r"|Функциональные.*?технические.*?характеристик"
        r"|Техническая спецификация услуг"
        r"|Техникалық сипаттама",
        re.IGNORECASE,
    )
    m = end_pattern.search(text)
    header = text[: m.start()] if m else text[:3000]
    return header[:3000]


_RE_AMOUNT = re.compile(
    r"(?:общая\s+сумма[^:\n]{0,60}[:\n]\s*|сатып\s+алуға\s+бөлінген[^:\n]{0,60}[:\n]\s*)"
    r"([\d\s.,]+)",
    re.IGNORECASE,
)
_RE_DEADLINE_RU = re.compile(
    r"срок\s+оказания\s+услуг[иa]?\s*[:\n]\s*([^\n]{3,80})",
    re.IGNORECASE,
)
_RE_DEADLINE_KZ = re.compile(
    r"қызмет\s+көрсету\s+мерзімі\s*[:\n]\s*([^\n]{3,80})",
    re.IGNORECASE,
)
_RE_CUSTOMER_RU = re.compile(
    r"наименование\s+заказчика\s*[:\n]\s*([^\n]{5,200})",
    re.IGNORECASE,
)
_RE_CUSTOMER_KZ = re.compile(
    r"тапсырыс\s+берушінің\s+атауы\s*[:\n]\s*([^\n]{5,200})",
    re.IGNORECASE,
)


def _regex_extract(text: str, language: str) -> Dict:
    """Regex-извлечение ключевых полей из шапки — без LLM."""
    result: Dict = {}
    is_kz = language == "Қазақша"

    m = _RE_AMOUNT.search(text)
    if m:
        result["total_amount"] = m.group(1).strip()

    m = (_RE_DEADLINE_KZ if is_kz else _RE_DEADLINE_RU).search(text)
    if m:
        result["delivery_deadline"] = m.group(1).strip()

    m = (_RE_CUSTOMER_KZ if is_kz else _RE_CUSTOMER_RU).search(text)
    if m:
        result["customer_name"] = m.group(1).strip()

    return result


# ── LLM-промпты ────────────────────────────────────────────────────────────

_KEY_FIELDS_PROMPT_RU = """Ты — парсер закупочных документов.
Из фрагментов документа извлеки ТОЛЬКО эти поля и верни строго JSON без markdown:
{
  "total_amount": "общая сумма закупки с указанием валюты или null",
  "customer_name": "название заказчика или null",
  "customer_bin": "БИН/БСН заказчика или null",
  "delivery_deadline": "срок поставки/оказания услуг или null",
  "payment_terms": "условия оплаты, аванс или null",
  "subject": "что закупается (кратко) или null",
  "lots": "количество лотов и их описание или null"
}
Если поле не найдено — оставь null. Только JSON, без пояснений."""

_KEY_FIELDS_PROMPT_KZ = """Сен — сатып алу құжаттарын талдаушысын.
Құжат үзінділерінен ТЕК осы өрістерді алып, markdown-сыз таза JSON қайтар:
{
  "total_amount": "сатып алудың жалпы сомасы валютамен немесе null",
  "customer_name": "тапсырыс берушінің атауы немесе null",
  "customer_bin": "тапсырыс берушінің БСН-і немесе null",
  "delivery_deadline": "жеткізу/қызмет көрсету мерзімі немесе null",
  "payment_terms": "төлем шарттары, аванс немесе null",
  "subject": "не сатып алынады (қысқаша) немесе null",
  "lots": "лоттар саны және сипаттамасы немесе null"
}
Өріс табылмаса — null қой. Тек JSON, түсіндірмесіз."""


def _extract_key_fields(chunks: List[str], language: str, raw_text: str = "") -> Dict:
    """
    Извлекаем критичные поля двумя способами:

    1. Regex по сырому тексту через _extract_header_block() — надёжно для шапки
       даже если она не попала в chunks[:3] из-за больших списков сёл.

    2. LLM по header-блоку + keyword-чанкам (без чанков-списков).

    Regex имеет приоритет для числовых полей (сумма, срок).
    LLM добирает то что regex не поймал (subject, lots, payment_terms).
    """
    lang_code = "kz" if language == "Қазақша" else "ru"

    # Шаг 1: regex
    regex_fields: Dict = {}
    if raw_text:
        header_block = _extract_header_block(raw_text)
        regex_fields = _regex_extract(header_block, language)

    # Шаг 2: LLM
    header_text = _extract_header_block(raw_text) if raw_text else "\n---\n".join(chunks[:3])
    clean_chunks = [c for c in chunks if not _is_list_chunk(c)]
    money_chunks = _keyword_chunks(clean_chunks, _FINANCIAL_KEYWORDS[lang_code], max_chunks=4)
    date_chunks  = _keyword_chunks(clean_chunks, _DATE_KEYWORDS[lang_code],      max_chunks=3)

    combined = f"{header_text}\n---\n{money_chunks}\n---\n{date_chunks}"
    combined  = combined[:6000]

    llm_fields: Dict = {}
    try:
        if language == "Қазақша":
            raw = call_alemllm(
                f"Құжат үзінділері:\n{combined}\n\nТек JSON қайтар.",
                _KEY_FIELDS_PROMPT_KZ,
            )
        else:
            raw = llm_chat(
                _KEY_FIELDS_PROMPT_RU,
                f"Фрагменты документа:\n{combined}\n\nВерни только JSON.",
                temperature=0,
            )

        try:
            llm_fields = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    llm_fields = json.loads(m.group(0))
                except Exception:
                    llm_fields = {}
    except RuntimeError as exc:
        logger.warning("Key-field LLM extraction skipped: %s", exc)

    # Шаг 3: merge — regex приоритетнее
    merged = {**llm_fields}
    for key, val in regex_fields.items():
        if val and (not merged.get(key) or merged.get(key) == "null"):
            merged[key] = val

    return merged


def _format_key_fields(fields: Dict, language: str) -> str:
    if not fields:
        return ""

    if language == "Қазақша":
        labels = {
            "total_amount":      "Жалпы сома",
            "customer_name":     "Тапсырыс беруші",
            "customer_bin":      "БСН",
            "delivery_deadline": "Жеткізу мерзімі",
            "payment_terms":     "Төлем шарттары",
            "subject":           "Сатып алу нысаны",
            "lots":              "Лоттар",
        }
    else:
        labels = {
            "total_amount":      "Общая сумма закупки",
            "customer_name":     "Заказчик",
            "customer_bin":      "БИН заказчика",
            "delivery_deadline": "Срок поставки",
            "payment_terms":     "Условия оплаты",
            "subject":           "Предмет закупки",
            "lots":              "Лоты",
        }

    lines = ["[КЛЮЧЕВЫЕ ПОЛЯ ДОКУМЕНТА]"]
    for key, label in labels.items():
        val = fields.get(key)
        if val and val != "null":
            lines.append(f"{label}: {val}")
    lines.append("[КОНЕЦ КЛЮЧЕВЫХ ПОЛЕЙ]")
    return "\n".join(lines)


# ── Публичные функции ──────────────────────────────────────────────────────

def prepare_document(
    pdf_bytes: bytes,
    language: str,
) -> Tuple[List[str], faiss.IndexFlatL2, str, Dict]:
    """Возвращает (chunks, index, preview, key_fields)."""
    target_lang = "kz" if language == "Қазақша" else "ru"
    text = extract_pages_by_language(pdf_bytes, target_lang)
    text = clean_text(text)

    if len(text) < 200:
        raise ValueError("not_enough_text")

    chunks = chunk_text(text, max_chars=1500)
    if not chunks:
        raise ValueError("not_enough_chunks")

    index    = build_index(chunks)
    preview  = text[:5000]

    # raw_text передаём для надёжного regex-извлечения шапки на больших PDF
    key_fields = _extract_key_fields(chunks, language, raw_text=text)

    return chunks, index, preview, key_fields


def answer_question(
    question: str,
    chunks: List[str],
    index: faiss.IndexFlatL2,
    language: str,
    key_fields: Optional[Dict] = None,
) -> Tuple[str, str]:
    q_low = question.lower()
    settings = _get_language_settings(language)
    question = _apply_question_hints(question, q_low)

    context = retrieve_context(question, chunks, index, k=QA_TOP_K)

    lang_code    = settings["lang_code"]
    clean_chunks = [c for c in chunks if not _is_list_chunk(c)]
    extra        = ""

    if any(x in q_low for x in _FINANCIAL_KEYWORDS[lang_code]):
        extra += _keyword_chunks(clean_chunks, _FINANCIAL_KEYWORDS[lang_code], max_chunks=3)
    if any(x in q_low for x in _DATE_KEYWORDS[lang_code]):
        extra += _keyword_chunks(clean_chunks, _DATE_KEYWORDS[lang_code], max_chunks=2)

    kf_block     = _format_key_fields(key_fields or {}, language)
    full_context = (kf_block + "\n\n" + context) if kf_block else context
    if extra:
        full_context += f"\n\n[Дополнительные фрагменты по ключевым словам]\n{extra}"
    full_context = full_context[:10000]

    user_prompt = f"{settings['document_label']}:\n{full_context}\n\n{settings['question_label']}: {question}"
    answer = _call_text_model(language, settings["qa_system_prompt"], user_prompt, temperature=0)

    return answer, full_context


def generate_summary(
    chunks: List[str],
    index: faiss.IndexFlatL2,
    customer_bin: str,
    language: str,
    key_fields: Optional[Dict] = None,
) -> str:
    settings = _get_language_settings(language)
    queries = settings["summary_queries"]

    context  = retrieve_multi(queries, chunks, index, k_per_query=5)
    kf_block = _format_key_fields(key_fields or {}, language)
    if kf_block:
        context = kf_block + "\n\n" + context
    context = context[:10000]

    system_prompt = settings["summary_system_prompt_template"].format(customer_bin=customer_bin)
    user_prompt = f"{settings['document_label']}:\n{context}"
    return _call_text_model(language, system_prompt, user_prompt, temperature=0)


def extract_json_fields(
    chunks: List[str],
    index: faiss.IndexFlatL2,
    customer_bin: str,
    language: str,
    key_fields: Optional[Dict] = None,
) -> str:
    settings = _get_language_settings(language)
    queries = settings["json_queries"]

    context  = retrieve_multi(queries, chunks, index, k_per_query=5)
    kf_block = _format_key_fields(key_fields or {}, language)
    if kf_block:
        context = kf_block + "\n\n" + context
    context = context[:10000]

    system_prompt = settings["json_system_prompt_template"].format(customer_bin=customer_bin)
    user_prompt = f"{settings['document_label']}:\n{context}\n\n{settings['json_instruction']}"
    result = _call_structured_model(language, system_prompt, user_prompt)

    try:
        parsed = json.loads(result)
    except Exception:
        match = re.search(r"\{.*\}", result, re.DOTALL)
        parsed = {}
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                pass

    if key_fields:
        for key in ["total_amount", "customer_name", "customer_bin",
                    "delivery_deadline", "payment_terms", "subject"]:
            if not parsed.get(key) and key_fields.get(key):
                parsed[key] = key_fields[key]

    parsed["customer_bin"] = customer_bin
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def analyze_risks(
    chunks: List[str],
    index: faiss.IndexFlatL2,
    language: str,
    key_fields: Optional[Dict] = None,
) -> str:
    settings = _get_language_settings(language)
    query = settings["risk_query"]
    context  = retrieve_context(query, chunks, index, k=RISK_TOP_K)
    kf_block = _format_key_fields(key_fields or {}, language)
    if kf_block:
        context = kf_block + "\n\n" + context
    context = context[:6000]

    user_prompt = f"{settings['document_label']}:\n{context}"
    return _call_text_model(language, settings["risk_system_prompt"], user_prompt, temperature=0)
