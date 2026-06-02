import io
import logging
from typing import Any, Dict, Optional

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
from logging_utils import log_usage
from services import analyze_risks, answer_question, generate_summary, prepare_document

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

LANGUAGE_OPTIONS = ["Русский", "Қазақша"]
CHOOSE_LANGUAGE_PROMPT = "Telegram PDF Reader Bot\n\nВыберите язык / Тілді таңдаңыз:"
CHOOSE_LANGUAGE_INVALID = "Выберите один из двух языков кнопками ниже. / Төмендегі екі тілдің бірін таңдаңыз."
CHOOSE_LANGUAGE_FIRST = (
    "Сначала выберите язык кнопками ниже, затем отправьте PDF.\n"
    "Алдымен тілді төмендегі батырмалардан таңдап, содан кейін PDF жіберіңіз."
)
MAX_TG_MESSAGE_LEN = 3500
PREVIEW_MAX_CHARS = 500
OVERVIEW_FIELD_KEYS = (
    "customer_name",
    "total_amount",
    "delivery_deadline",
    "payment_terms",
    "subject",
    "lots",
)

TG_TEXTS: Dict[str, Dict[str, Any]] = {
    "Русский": {
        "welcome": (
            "Отправьте PDF техспецификации, и я помогу с анализом.\n\n"
            "Сценарий работы:\n"
            "1. Выберите язык\n"
            "2. Загрузите PDF\n"
            "3. Пришлите БИН заказчика\n"
            "4. Нажимайте кнопки или задавайте вопрос текстом"
        ),
        "choose_language": "Выберите язык работы:",
        "language_saved": "Язык сохранен: русский. Теперь отправьте PDF-файл.",
        "send_pdf": "Пришлите PDF-документ.",
        "processing_pdf": "Обрабатываю PDF, извлекаю текст и строю индекс...",
        "pdf_ready": "PDF готов. Ниже короткая выжимка из документа. Теперь пришлите 12-значный БИН заказчика.",
        "pdf_error": "Не удалось извлечь достаточно текста из PDF. Возможно, файл сканированный или выбран не тот язык.",
        "need_pdf_first": "Сначала отправьте PDF-файл.",
        "need_bin": "Пришлите корректный 12-значный БИН заказчика.",
        "bin_saved": "БИН сохранен. Теперь можно получить резюме, риски или задать вопрос текстом.",
        "bad_file": "Нужен именно PDF-файл.",
        "service_error": "Не удалось выполнить запрос. Попробуйте еще раз чуть позже.",
        "doc_overview_title": "Что удалось распознать",
        "file_label": "Файл",
        "chunks_label": "Фрагментов",
        "preview_label": "Короткий предпросмотр",
        "preview_empty": "Предпросмотр недоступен.",
        "overview_field_labels": {
            "customer_name": "Заказчик",
            "total_amount": "Сумма",
            "delivery_deadline": "Срок",
            "payment_terms": "Оплата",
            "subject": "Предмет закупки",
            "lots": "Лоты",
        },
        "summary_btn": "Краткое резюме",
        "risk_btn": "Риски",
        "reset_btn": "Сбросить",
        "summary_wait": "Генерирую краткое резюме...",
        "risk_wait": "Анализирую риски...",
        "question_wait": "Ищу ответ в документе...",
        "summary_title": "Краткое резюме",
        "risk_title": "Риски",
        "answer_title": "Ответ",
        "reset_done": "Состояние очищено. Снова выберите язык, чтобы начать заново.",
        "unknown": "Не понял команду. Используйте кнопки ниже или отправьте вопрос текстом.",
        "start_hint": "Если хотите сменить язык или начать заново, отправьте /start.",
        "summary_file_caption": "Краткое резюме — скачайте TXT файл.",
        "risk_file_caption": "Анализ рисков — скачайте TXT файл.",
    },
    "Қазақша": {
        "welcome": (
            "PDF техникалық ерекшелігін жіберіңіз, мен талдап беремін.\n\n"
            "Жұмыс тәртібі:\n"
            "1. Тілді таңдаңыз\n"
            "2. PDF жіберіңіз\n"
            "3. Тапсырыс берушінің БСН-ін жіберіңіз\n"
            "4. Батырмаларды басыңыз немесе мәтінмен сұрақ қойыңыз"
        ),
        "choose_language": "Жұмыс тілін таңдаңыз:",
        "language_saved": "Тіл сақталды: қазақша. Енді PDF-файл жіберіңіз.",
        "send_pdf": "PDF-құжатты жіберіңіз.",
        "processing_pdf": "PDF өңделіп жатыр, мәтін шығарылып, индекс құрылуда...",
        "pdf_ready": "PDF дайын. Төменде құжаттың қысқаша көрінісі берілген. Енді тапсырыс берушінің 12 таңбалы БСН-ін жіберіңіз.",
        "pdf_error": "PDF-тен жеткілікті мәтін алу мүмкін болмады. Файл скан болуы мүмкін немесе тіл дұрыс таңдалмаған.",
        "need_pdf_first": "Алдымен PDF-файл жіберіңіз.",
        "need_bin": "Тапсырыс берушінің дұрыс 12 таңбалы БСН-ін жіберіңіз.",
        "bin_saved": "БСН сақталды. Енді түйіндеме, тәуекелдер ала аласыз немесе сұрақ қоя аласыз.",
        "bad_file": "PDF-файл жіберу керек.",
        "service_error": "Сұрауды орындау мүмкін болмады. Сәл кейінірек қайта көріңіз.",
        "doc_overview_title": "Танылған деректер",
        "file_label": "Файл",
        "chunks_label": "Үзінділер",
        "preview_label": "Қысқа алдын ала көрініс",
        "preview_empty": "Алдын ала көрініс қолжетімсіз.",
        "overview_field_labels": {
            "customer_name": "Тапсырыс беруші",
            "total_amount": "Сома",
            "delivery_deadline": "Мерзім",
            "payment_terms": "Төлем",
            "subject": "Сатып алу нысаны",
            "lots": "Лоттар",
        },
        "summary_btn": "Қысқаша түйіндеме",
        "risk_btn": "Тәуекелдер",
        "reset_btn": "Қалпына келтіру",
        "summary_wait": "Қысқаша түйіндеме жасалып жатыр...",
        "risk_wait": "Тәуекелдер талданып жатыр...",
        "question_wait": "Құжаттан жауап ізделуде...",
        "summary_title": "Қысқаша түйіндеме",
        "risk_title": "Тәуекелдер",
        "answer_title": "Жауап",
        "reset_done": "Күй тазартылды. Қайта бастау үшін тілді қайта таңдаңыз.",
        "unknown": "Команда түсініксіз болды. Төмендегі батырмаларды қолданыңыз немесе мәтінмен сұрақ қойыңыз.",
        "start_hint": "Тілді ауыстыру немесе қайта бастау үшін /start жіберіңіз.",
        "summary_file_caption": "Қысқаша түйіндеме — TXT файлын жүктеңіз.",
        "risk_file_caption": "Тәуекел талдауы — TXT файлын жүктеңіз.",
    },
}


def get_language(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("language", "Русский")


def get_texts(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    return TG_TEXTS[get_language(context)]


def has_selected_language(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.user_data.get("language") in LANGUAGE_OPTIONS and not context.user_data.get("awaiting_language")


def get_tg_username(update: Update) -> str:
    user = update.effective_user
    return user.username if user and user.username else ""


def main_keyboard(language: str) -> ReplyKeyboardMarkup:
    texts = TG_TEXTS[language]
    keyboard = [
        [texts["summary_btn"], texts["risk_btn"]],
        [texts["reset_btn"]],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def bin_keyboard(language: str) -> ReplyKeyboardMarkup:
    texts = TG_TEXTS[language]
    return ReplyKeyboardMarkup([[texts["reset_btn"]]], resize_keyboard=True)


def language_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[LANGUAGE_OPTIONS[0], LANGUAGE_OPTIONS[1]]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def current_reply_markup(context: ContextTypes.DEFAULT_TYPE):
    if "chunks" not in context.user_data or "index" not in context.user_data:
        return ReplyKeyboardRemove()
    if context.user_data.get("awaiting_bin"):
        return bin_keyboard(get_language(context))
    return main_keyboard(get_language(context))


def reset_document_state(context: ContextTypes.DEFAULT_TYPE, keep_language: bool = True) -> None:
    language = context.user_data.get("language", "Русский") if keep_language else "Русский"
    context.user_data.clear()
    if keep_language:
        context.user_data["language"] = language


def make_txt_file(content: str, filename: str) -> io.BytesIO:
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = filename
    return buf


def split_message(text: str, max_len: int = MAX_TG_MESSAGE_LEN) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(line) > max_len:
            if current.strip():
                chunks.append(current.rstrip())
                current = ""
            for start in range(0, len(line), max_len):
                piece = line[start:start + max_len].rstrip()
                if piece:
                    chunks.append(piece)
            continue

        if len(current) + len(line) > max_len and current.strip():
            chunks.append(current.rstrip())
            current = line
        else:
            current += line

    if current.strip():
        chunks.append(current.rstrip())

    return chunks


async def send_long_reply(
    update: Update,
    text: str,
    *,
    reply_markup=None,
) -> None:
    parts = split_message(text)
    if not parts:
        return

    for index, part in enumerate(parts):
        kwargs = {"reply_markup": reply_markup} if index == 0 and reply_markup is not None else {}
        await update.message.reply_text(part, **kwargs)


def format_document_overview(language: str, filename: str, chunk_count: int, key_fields: Dict[str, Any], preview: str) -> str:
    texts = TG_TEXTS[language]
    lines = [
        texts["doc_overview_title"],
        f"- {texts['file_label']}: {filename}",
        f"- {texts['chunks_label']}: {chunk_count}",
    ]

    field_labels = texts.get("overview_field_labels", {})
    for key in OVERVIEW_FIELD_KEYS:
        value = (key_fields or {}).get(key)
        if value and value != "null":
            lines.append(f"- {field_labels.get(key, key)}: {value}")

    snippet = (preview or "").strip()
    if snippet:
        snippet = " ".join(snippet.split())
        if len(snippet) > PREVIEW_MAX_CHARS:
            snippet = snippet[:PREVIEW_MAX_CHARS].rstrip() + "..."
        lines.extend(["", f"{texts['preview_label']}:", snippet])
    else:
        lines.extend(["", f"{texts['preview_label']}: {texts['preview_empty']}"])

    return "\n".join(lines)


async def prompt_for_language(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str = CHOOSE_LANGUAGE_PROMPT) -> None:
    context.user_data["awaiting_language"] = True
    await update.message.reply_text(message, reply_markup=language_keyboard())


async def send_service_error(update: Update, texts: Dict[str, Any], exc: Exception) -> None:
    logger.exception("Telegram action failed", exc_info=exc)
    await update.message.reply_text(texts["service_error"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reset_document_state(context, keep_language=False)
    await prompt_for_language(update, context)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document

    if not document:
        return

    if not has_selected_language(context):
        await prompt_for_language(update, context, CHOOSE_LANGUAGE_FIRST)
        return

    texts = get_texts(context)
    if document.mime_type != "application/pdf":
        await update.message.reply_text(texts["bad_file"], reply_markup=current_reply_markup(context))
        return

    language = get_language(context)
    reset_document_state(context, keep_language=True)
    context.user_data["awaiting_language"] = False
    await update.message.reply_text(texts["processing_pdf"])
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    telegram_file = await context.bot.get_file(document.file_id)
    pdf_bytes = await telegram_file.download_as_bytearray()

    try:
        chunks, index, preview, key_fields = prepare_document(bytes(pdf_bytes), language)
    except ValueError:
        await update.message.reply_text(texts["pdf_error"])
        return
    except Exception as exc:
        logger.exception("PDF processing failed")
        await update.message.reply_text(texts["pdf_error"])
        return

    context.user_data["chunks"] = chunks
    context.user_data["index"] = index
    context.user_data["preview"] = preview
    context.user_data["key_fields"] = key_fields
    context.user_data["pdf_filename"] = document.file_name or "telegram_upload.pdf"
    context.user_data.pop("customer_bin", None)
    context.user_data["awaiting_bin"] = True

    await update.message.reply_text(texts["pdf_ready"], reply_markup=bin_keyboard(language))
    await send_long_reply(
        update,
        format_document_overview(
            language,
            context.user_data["pdf_filename"],
            len(chunks),
            key_fields,
            preview,
        ),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text in LANGUAGE_OPTIONS or context.user_data.get("awaiting_language"):
        await handle_language(update, context, text)
        return

    if not has_selected_language(context):
        await prompt_for_language(update, context, CHOOSE_LANGUAGE_FIRST)
        return

    language = get_language(context)
    texts = get_texts(context)

    if text == texts["reset_btn"]:
        reset_document_state(context, keep_language=False)
        await update.message.reply_text(texts["reset_done"])
        await prompt_for_language(update, context)
        return

    if "chunks" not in context.user_data or "index" not in context.user_data:
        await update.message.reply_text(texts["need_pdf_first"])
        return

    if context.user_data.get("awaiting_bin"):
        if text.isdigit() and len(text) == 12:
            context.user_data["customer_bin"] = text
            context.user_data["awaiting_bin"] = False
            await update.message.reply_text(texts["bin_saved"], reply_markup=main_keyboard(language))
        else:
            await update.message.reply_text(texts["need_bin"])
        return

    # ── Краткое резюме ────────────────────────────────────────────────────
    if text == texts["summary_btn"]:
        customer_bin = context.user_data.get("customer_bin", "")
        if not (customer_bin.isdigit() and len(customer_bin) == 12):
            await update.message.reply_text(texts["need_bin"])
            return
        await update.message.reply_text(texts["summary_wait"])
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            result = generate_summary(
                context.user_data["chunks"],
                context.user_data["index"],
                customer_bin,
                language,
                context.user_data.get("key_fields"),
            )
            log_usage(
                customer_bin,
                language,
                context.user_data.get("pdf_filename", ""),
                interface="tg",
                tg_username=get_tg_username(update),
            )
            await send_long_reply(
                update,
                f"{texts['summary_title']}:\n\n{result}",
                reply_markup=main_keyboard(language),
            )
            await update.message.reply_document(
                document=make_txt_file(result, "summary.txt"),
                caption=texts["summary_file_caption"],
            )
        except Exception as exc:
            await send_service_error(update, texts, exc)
        return

    # ── Риски ─────────────────────────────────────────────────────────────
    if text == texts["risk_btn"]:
        customer_bin = context.user_data.get("customer_bin", "")
        if not (customer_bin.isdigit() and len(customer_bin) == 12):
            await update.message.reply_text(texts["need_bin"])
            return
        await update.message.reply_text(texts["risk_wait"])
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            result = analyze_risks(
                context.user_data["chunks"],
                context.user_data["index"],
                language,
                context.user_data.get("key_fields"),
            )
            log_usage(
                customer_bin,
                language,
                context.user_data.get("pdf_filename", ""),
                interface="tg",
                tg_username=get_tg_username(update),
            )
            await send_long_reply(
                update,
                f"{texts['risk_title']}:\n\n{result}",
                reply_markup=main_keyboard(language),
            )
            await update.message.reply_document(
                document=make_txt_file(result, "risks.txt"),
                caption=texts["risk_file_caption"],
            )
        except Exception as exc:
            await send_service_error(update, texts, exc)
        return

    # ── Вопрос-ответ ──────────────────────────────────────────────────────
    await update.message.reply_text(texts["question_wait"])
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        answer, _ = answer_question(
            text,
            context.user_data["chunks"],
            context.user_data["index"],
            language,
            context.user_data.get("key_fields"),
        )
        log_usage(
            context.user_data.get("customer_bin", ""),
            language,
            context.user_data.get("pdf_filename", ""),
            interface="tg",
            tg_username=get_tg_username(update),
        )
        await send_long_reply(
            update,
            f"{texts['answer_title']}:\n\n{answer}",
            reply_markup=main_keyboard(language),
        )
    except Exception as exc:
        await send_service_error(update, texts, exc)


async def handle_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    selected_text: Optional[str] = None,
) -> None:
    text = (selected_text or update.message.text or "").strip()
    if text not in LANGUAGE_OPTIONS:
        await update.message.reply_text(CHOOSE_LANGUAGE_INVALID, reply_markup=language_keyboard())
        return

    context.user_data["language"] = text
    context.user_data["awaiting_language"] = False
    texts = get_texts(context)
    await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(texts["language_saved"])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not has_selected_language(context):
        await prompt_for_language(update, context)
        return

    texts = get_texts(context)
    await update.message.reply_text(
        f"{texts['welcome']}\n\n{texts['start_hint']}",
        reply_markup=current_reply_markup(context),
    )


async def handle_bad_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not has_selected_language(context):
        await prompt_for_language(update, context, CHOOSE_LANGUAGE_FIRST)
        return

    texts = get_texts(context)
    await update.message.reply_text(texts["bad_file"], reply_markup=current_reply_markup(context))


def build_application() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty. Add it to .env before running telegram_bot.py")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    application.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.Document.PDF, handle_bad_attachment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


def main() -> None:
    application = build_application()
    logger.info("Telegram bot started in polling mode")
    application.run_polling()


if __name__ == "__main__":
    main()
