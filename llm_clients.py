import re

import ollama
import requests

from config import (
    ALEM_MODEL,
    LATIN_RE,
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    VERIFY_TLS,
)


def _strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    return text.strip()


def _litellm_base_url() -> str:
    base_url = LITELLM_BASE_URL.rstrip("/")
    if not base_url:
        raise RuntimeError("LITELLM_BASE_URL is required when using LiteLLM.")
    return base_url


def _auth_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_API_KEY}"
    return headers


def _call_litellm_chat(model: str, system_prompt: str, user_prompt: str, temperature: float = 0) -> str:
    url = _litellm_base_url() + "/chat/completions"
    headers = _auth_headers()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "stream": False,
    }

    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=300,
            verify=VERIFY_TLS,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"LiteLLM request failed: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"LiteLLM bad status: {resp.status_code}, {resp.text}")

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("LiteLLM returned an empty response.")
    return _strip_thinking(content)


def llm_chat(system_prompt: str, user_prompt: str, temperature: float = 0) -> str:
    if LLM_PROVIDER == "litellm":
        return _call_litellm_chat(
            model=LLM_MODEL,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )

    if LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

    try:
        resp = ollama.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature},
        )
    except Exception as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    content = resp.get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Ollama returned an empty response.")
    return _strip_thinking(content)


def call_alemllm(prompt: str, system_prompt: str) -> str:
    try:
        return _call_litellm_chat(
            model=ALEM_MODEL,
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.0,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"AlemLLM request failed: {exc}") from exc


def check_llm_backend_ready() -> str:
    if LLM_PROVIDER == "litellm":
        try:
            url = _litellm_base_url() + "/models"
        except RuntimeError as exc:
            return str(exc)
        headers = {"Authorization": f"Bearer {LITELLM_API_KEY}"} if LITELLM_API_KEY else {}
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=VERIFY_TLS)
        except requests.RequestException as exc:
            return f"LiteLLM unavailable: {exc}"
        if resp.status_code != 200:
            return f"LiteLLM bad status: {resp.status_code}"
        return ""

    if LLM_PROVIDER == "ollama":
        try:
            ollama.list()
            return ""
        except Exception as exc:
            return f"Ollama unavailable: {exc}"

    return f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}"


def ensure_russian(answer: str) -> str:
    if not LATIN_RE.search(answer):
        return answer

    fix_prompt = (
        "Перепиши текст строго на русском языке. "
        "Не используй латиницу вообще. Сохрани смысл и структуру.\n\n"
        f"Текст:\n{answer}"
    )
    try:
        return llm_chat(
            "Ты редактор. Только русский язык, без латиницы.",
            fix_prompt,
            temperature=0,
        )
    except RuntimeError:
        return answer


def ensure_language(answer: str, language: str) -> str:
    if language == "Русский":
        return ensure_russian(answer)
    return answer
