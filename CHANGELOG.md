# Changelog

## 0.2.0 - 2026-09-27

- Frappe v15 support (tested with 15.121.0, Python 3.11):
  - apps-screen Chat icon through `add_to_apps_screen` on v15 (v16 keeps its Desktop Icon);
  - the "Open Chat" shortcut opens the chat panel in place on v15 too (v15 redirects /desk to
    /app without the query string);
  - the chat button icon setting also applies to ClefinCode's navbar icon, used on v15.
- `requires-python` lowered to 3.10.
- Tests stub the engine dispatcher, so they pass whichever engine the site is set to.

## 0.1.0 - 2026-09-27

First public release.

- Access checks for every whitelisted method of `clefincode_chat.api.*` (channel membership,
  acting user, guest restrictions); `chat_guard_mode: log` for diagnosis.
- Display-time translation into each viewer's language, cached per (message, language), batched
  up to 50 messages per request.
- Translation engines: Anthropic Claude and Google Gemini; glossary, translation context and
  optional language restriction.
- Chat workspace and apps-screen icon for System Manager / Chat Administrator.
- Chat button appearance settings (icon, colour, position, size).
- Demo data script for local test sites.
