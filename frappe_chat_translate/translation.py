"""Translate ClefinCode Chat messages into the viewer's language when they are displayed.

Flow: the chat screen shows messages (history or new ones arriving over ClefinCode's own
realtime) -> the browser asks for translations of the visible messages -> cached ones are
returned at once, the rest are translated in one Claude request and cached per
(message, language) -> shown under each bubble. Every participant therefore reads every
message in their own language, whatever language it was written in.
"""

import json
import re
from html import unescape

import frappe

from frappe_chat_translate.security.guard import can_access_channel

MAX_BATCH = 50  # messages translated per request
LANGUAGE_NAMES = {"ja": "Japanese", "vi": "Vietnamese", "en": "English"}


# ---------------------------------------------------------------- settings and helpers


def get_settings():
    return frappe.get_cached_doc("Chat Translate Settings")


def allowed_languages(settings=None) -> set[str] | None:
    """Optional restriction from settings; None means every user language is served."""
    settings = settings or get_settings()
    codes = {code.strip().lower() for code in (settings.languages or "").split(",") if code.strip()}
    return codes or None


def user_language(user: str) -> str | None:
    lang = frappe.db.get_value("User", user, "language") or frappe.db.get_default("lang") or ""
    return lang.split("-")[0].lower() or None


def plain_text(content: str) -> str:
    """ClefinCode stores rich text (HTML from the editor); translate the visible text only."""
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", content or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", unescape(text)).strip()


def is_translatable(doc) -> bool:
    if doc.is_deleted or doc.is_media or doc.is_document or doc.is_voice_clip or doc.is_screenshot:
        return False
    if doc.message_type or doc.message_template_type:  # info / template / system messages
        return False
    return bool(plain_text(doc.content))


# ---------------------------------------------------------------- cache invalidation


def on_message_update(doc, method=None):
    """An edited message must be translated again the next time it is shown."""
    if not doc.is_new() and doc.has_value_changed("content"):
        frappe.db.delete("Chat Message Translation", {"message": doc.name})


# ---------------------------------------------------------------- translation engines

DEFAULT_MODELS = {"Anthropic Claude": "claude-opus-5", "Google Gemini": "gemini-2.5-flash"}


def model_name(settings) -> str:
    if settings.provider == "Google Gemini":
        return settings.gemini_model or DEFAULT_MODELS["Google Gemini"]
    return settings.model or DEFAULT_MODELS["Anthropic Claude"]


def build_prompt(items: list[tuple[str, str]], target: str, settings) -> tuple[str, str, dict]:
    """(system instruction, user message, JSON schema) for one batch; shared by every engine.
    Each message's language is detected and the message is translated into `target`."""
    glossary = [line.strip() for line in (settings.glossary or "").splitlines() if line.strip()]
    system = (
        "You translate workplace chat messages between colleagues who write in different languages. "
        "Keep the tone and level of politeness of each original; render greetings and sign-offs as the "
        "natural polite business expression of the target language. Keep code, identifiers, IDs, URLs, "
        "file names and numbers exactly as written, and keep dates in the format the writer used. "
        "Translate only; do not add explanations."
    )
    if settings.translation_context:
        system += f"\nContext: {settings.translation_context.strip()}"
    if glossary:
        system += ("\nGlossary (\"term\" = keep untranslated, \"term => rendering\" = always use that rendering):\n"
                   + "\n".join(glossary))
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        # ISO 639-1 code of the language the message is written in
                        "source_language": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["id", "source_language", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }
    name = f"{target} ({LANGUAGE_NAMES.get(target, target)})"
    messages_xml = "\n".join(f'<message id="{mid}">\n{text}\n</message>' for mid, text in items)
    user = (
        f"Translate each message below into {name}. For each message return its id, its original "
        "language as an ISO 639-1 code in source_language, and the translation in text. If a message is "
        f"already in {name}, return it unchanged.\n\n{messages_xml}"
    )
    return system, user, schema


def _rows(text: str | None) -> dict[str, dict] | None:
    try:
        data = json.loads(text) if text else None
    except json.JSONDecodeError:
        frappe.log_error(title="Chat Translate", message="Chat Translate: response was not valid JSON")
        return None
    return {row["id"]: row for row in (data or {}).get("items", []) if row.get("id")}


def call_llm(items: list[tuple[str, str]], target: str, settings) -> dict[str, dict] | None:
    """Translate with the engine chosen in settings.
    Returns {message id: {"source_language": str, "text": str}} or None on failure (already logged)."""
    if settings.provider == "Google Gemini":
        return call_gemini(items, target, settings)
    return call_claude(items, target, settings)


# ---------------------------------------------------------------- Anthropic Claude


def build_request(items: list[tuple[str, str]], target: str, settings) -> dict:
    system, user, schema = build_prompt(items, target, settings)
    return dict(
        model=model_name(settings),
        max_tokens=16000,
        system=system,
        output_config={"effort": settings.effort or "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )


def call_claude(items: list[tuple[str, str]], target: str, settings) -> dict[str, dict] | None:
    import anthropic

    api_key = settings.get_password("api_key", raise_exception=False) or None
    client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2)
    try:
        # Opus-tier safety classifiers can decline a request; let the server re-run it on the
        # recommended fallback model instead of losing the translation.
        response = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            **build_request(items, target, settings),
        )
    except anthropic.AuthenticationError:
        frappe.log_error(title="Chat Translate", message="Chat Translate: invalid Claude API key")
        return None
    except anthropic.RateLimitError:
        frappe.log_error(title="Chat Translate", message="Chat Translate: Claude rate limited")
        return None
    except anthropic.APIStatusError as e:
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: Claude API error {e.status_code}: {e.message}")
        return None
    except anthropic.APIConnectionError:
        frappe.log_error(title="Chat Translate", message="Chat Translate: Claude connection error")
        return None
    except (TypeError, anthropic.AnthropicError) as e:
        # e.g. no API key configured and none in the environment: keep serving cached translations
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: could not call Claude: {e}")
        return None

    if response.stop_reason == "refusal":
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: refused ({getattr(response.stop_details, 'category', None)})")
        return None
    if response.stop_reason == "max_tokens":
        frappe.log_error(title="Chat Translate", message="Chat Translate: output truncated (max_tokens)")
        return None
    return _rows(next((b.text for b in response.content if b.type == "text"), None))


# ---------------------------------------------------------------- Google Gemini


def build_gemini_config(system: str, schema: dict):
    from google.genai import types

    return types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_json_schema=schema,
        max_output_tokens=16000,
    )


def call_gemini(items: list[tuple[str, str]], target: str, settings) -> dict[str, dict] | None:
    from google import genai
    from google.genai import errors, types

    system, user, schema = build_prompt(items, target, settings)
    # empty key: the SDK falls back to the GEMINI_API_KEY / GOOGLE_API_KEY environment variables
    api_key = settings.get_password("gemini_api_key", raise_exception=False) or None
    try:
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60_000))
        response = client.models.generate_content(
            model=model_name(settings), contents=user, config=build_gemini_config(system, schema)
        )
    except errors.ClientError as e:  # 4xx: bad key, unknown model, quota
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: Gemini API error {e.code}: {e.message}")
        return None
    except errors.ServerError as e:
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: Gemini server error {e.code}: {e.message}")
        return None
    except Exception as e:  # missing key, network errors
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: could not call Gemini: {e}")
        return None

    feedback = getattr(response, "prompt_feedback", None)
    if feedback and getattr(feedback, "block_reason", None):
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: Gemini blocked the request ({feedback.block_reason})")
        return None
    candidate = (response.candidates or [None])[0]
    reason = str(getattr(candidate, "finish_reason", "") or "")
    if reason.endswith("MAX_TOKENS"):
        frappe.log_error(title="Chat Translate", message="Chat Translate: Gemini output truncated (MAX_TOKENS)")
        return None
    if reason and not reason.endswith("STOP"):
        frappe.log_error(title="Chat Translate", message=f"Chat Translate: Gemini stopped ({reason})")
        return None
    return _rows(response.text)


# ---------------------------------------------------------------- cache


def _cached(names: list[str], lang: str) -> dict[str, str | None]:
    rows = frappe.get_all("Chat Message Translation", filters={"message": ["in", names], "language": lang},
                          fields=["message", "text", "source_language"])
    # a row whose source language equals the target means "already in this language": nothing to show
    return {r.message: (None if r.source_language == lang else r.text) for r in rows}


def _store(message: str, channel: str, lang: str, source: str | None, text: str | None, model: str | None):
    if frappe.db.exists("Chat Message Translation", {"message": message, "language": lang}):
        return  # another viewer cached it meanwhile
    frappe.get_doc(dict(doctype="Chat Message Translation", message=message, chat_channel=channel,
                        language=lang, source_language=source, text=text, model=model)).insert(ignore_permissions=True)


def translate_for_user(names: list[str], user: str) -> dict[str, str]:
    """Translations of the given messages into the user's language, using and filling the cache."""
    settings = get_settings()
    lang = user_language(user)
    allowed = allowed_languages(settings)
    if not settings.enabled or not lang or (allowed is not None and lang not in allowed):
        return {}

    docs = {}
    for row in frappe.get_all("ClefinCode Chat Message", filters={"name": ["in", names]},
                              fields=["name", "chat_channel", "sub_channel", "content", "is_deleted", "is_media",
                                      "is_document", "is_voice_clip", "is_screenshot", "message_type",
                                      "message_template_type"]):
        channel = row.sub_channel or row.chat_channel
        # never translate (and so reveal) a message from a channel the user cannot read
        if user == "Administrator" or can_access_channel(channel, user) or (
                row.chat_channel and can_access_channel(row.chat_channel, user)):
            docs[row.name] = (row, channel)

    result = {}
    cached = _cached(list(docs), lang)
    todo = []
    for name, (row, channel) in docs.items():
        if name in cached:
            if cached[name]:
                result[name] = cached[name]
        elif is_translatable(row):
            todo.append(name)
        else:
            _store(name, channel, lang, lang, None, None)  # remember: nothing to translate

    for start in range(0, len(todo), MAX_BATCH):
        batch = todo[start:start + MAX_BATCH]
        translated = call_llm([(n, plain_text(docs[n][0].content)) for n in batch], lang, settings)
        if translated is None:
            break  # failure already logged; untranslated messages are retried on the next display
        for name in batch:
            row = translated.get(name)
            if not row:
                continue
            source = (row.get("source_language") or "").split("-")[0].lower() or None
            text = None if source == lang else row.get("text")
            _store(name, docs[name][1], lang, source, text, model_name(settings))
            if text:
                result[name] = text
    frappe.db.commit()
    return result


# ---------------------------------------------------------------- API for the chat screen


@frappe.whitelist(allow_guest=False)
def get_translations(message_names: str | list):
    """Translations in the session user's language for the given (visible) messages."""
    names = json.loads(message_names) if isinstance(message_names, str) else message_names
    names = list(dict.fromkeys(n for n in (names or []) if isinstance(n, str)))[:200]
    if not names:
        return {}
    return translate_for_user(names, frappe.session.user)


@frappe.whitelist(allow_guest=False)
def get_client_settings():
    """What the browser needs: whether to translate for this user, and the chat button's appearance."""
    settings = get_settings()
    lang = user_language(frappe.session.user)
    allowed = allowed_languages(settings)
    size = min(max(int(settings.button_size or 56), 32), 96)
    return {
        "enabled": bool(settings.enabled) and bool(lang) and (allowed is None or lang in allowed),
        "language": lang,
        "button": {
            "icon": settings.button_icon or None,
            "color": settings.button_color or None,
            "position": "left" if settings.button_position == "Bottom Left" else "right",
            "size": size,
        },
    }
