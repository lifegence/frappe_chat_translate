# Changelog

## 0.3.1 - 2026-09-27

- OpenAI: an exhausted balance (`insufficient_quota`) is logged as such instead of "rate limited".
- OpenAI engine tested live (gpt-6-sol, gpt-6-luna).

## 0.3.0 - 2026-09-27

- OpenAI as a third translation engine (Chat Completions, structured output; default model
  `gpt-6-sol`), with an optional Base URL for OpenAI-compatible services such as Azure OpenAI or a
  self-hosted server. A service that rejects structured output is retried once in JSON mode.
- The Effort setting also applies to OpenAI (without a Base URL).
- New dependency: `openai>=1.60,<4`.

## 0.2.1 - 2026-09-27

Preparation for the Frappe Cloud Marketplace.

- CI on GitHub Actions: tests on Frappe v15 and v16, pre-commit (ruff), Semgrep with the Frappe and
  marketplace rules, pip-audit.
- `pyproject.toml` declares the supported Frappe and ClefinCode Chat versions
  (`[tool.bench.frappe-dependencies]`).
- `get_translations` accepts POST only and no longer commits by hand (Frappe commits POST requests).
- Tests use a role of their own instead of ERPNext's, so they run on a Frappe-only site.
- Code formatted with ruff.

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
