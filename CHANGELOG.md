# Changelog

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
