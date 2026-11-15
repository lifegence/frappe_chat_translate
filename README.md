# Frappe Chat Translate

Real-time translation for [Raven](https://github.com/The-Commit-Company/raven), the chat app for
Frappe v16: every participant reads every message in their own language, whatever language it was
written in. Translations are made when a message is displayed and cached per message and language.

It does not modify Raven itself. This project is not affiliated with The Commit Company.

Up to 0.3.x this app worked with ClefinCode Chat (see [Moving from ClefinCode Chat](#moving-from-clefincode-chat)).

[日本語の README](README_ja.md)

## Requirements

| | Tested with |
|---|---|
| Frappe | v16 (16.55.2) |
| Raven | 3.2.0 |
| Python | 3.10 or later (tested with 3.14) |
| Translation engine | Anthropic Claude, Google Gemini, or OpenAI / an OpenAI-compatible service such as the LiteLLM gateway (API key required) |

## Installation

```bash
bench get-app https://github.com/lifegence/frappe_chat_translate
bench --site your-site install-app frappe_chat_translate
bench restart
```

## Configuration

Open the **Chat Translate** workspace > **Translation Settings** (DocType `Chat Translate Settings`,
System Manager only).

| Setting | Notes |
|---|---|
| Enabled | Turns translation on for everyone |
| Translation Engine | `Anthropic Claude` (default model `claude-opus-5`), `Google Gemini` (default model `gemini-2.5-flash`) or `OpenAI` (default model `gpt-6-sol`) |
| API keys | Stored encrypted. Leave empty to use `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`, or `OPENAI_API_KEY` |
| Base URL (OpenAI) | Optional. An OpenAI-compatible Chat Completions endpoint, e.g. a LiteLLM gateway (`https://gateway.example.com/v1`), Azure OpenAI or a self-hosted server; the model field then takes that service's model name |
| Effort | Claude, and OpenAI without a Base URL. Raise it if translations miss nuance |
| Restrict to Languages | Optional. Empty = every user's language is served |
| Translation Context | Optional. Who is talking to whom; helps with tone and terms |
| Glossary | One entry per line. `term` keeps it untranslated, `term => rendering` fixes the rendering |

Each user's language is their **Language** in the user settings.

### How translation works

1. Raven's web app (`/raven`) gets a small script from this app (added to the page's HTML; Raven's
   files are not changed). When messages appear on screen (history or new ones), it asks for
   translations of the visible messages into the viewer's language.
2. Cached translations are returned at once. The rest are translated in one request (up to 50
   messages) and cached per (message, language), so the next viewer with the same language pays
   nothing.
3. The translation is shown under the message. Messages already in the viewer's language, and
   translations identical to the original (a bare URL, a code), are not shown. An edited message is
   translated again; a deleted message's translations are removed.

A translation is only returned for messages in channels the viewer can read in Raven (Raven's own
permission rule). Files, images, polls, system and bot messages are not translated.

### Data handling

The text of chat messages is sent to the translation engine you choose. Use an API plan whose terms
fit your data (for example, one that does not use your data for training). The API keys are stored
encrypted in the site database.

Nothing is sent to Lifegence. See [PRIVACY.md](PRIVACY.md) for details.

## Moving from ClefinCode Chat

0.4.0 translates Raven instead of ClefinCode Chat. The translation settings (engine, keys, glossary)
stay as they are. Cached translations follow the messages when the chat is converted to Raven:

1. Convert the ClefinCode Chat data to Raven with a script that writes the message map
   `private/files/clefincode_raven_map.json` (`{"messages": {old: new}, "captions": {old: new}}`).
2. Run `bench --site your-site execute frappe_chat_translate.migrate_from_clefincode.run`
   (the conversion can also call it). Translations of converted messages are re-pointed; those of
   messages that were not converted are removed. Without the map file nothing is changed.
3. Uninstall ClefinCode Chat. Do not uninstall this app: that would remove the translations and
   settings.

Version 0.3.x (the ClefinCode Chat add-on, including its access-control hardening) stays available
under the `v0.3.3` tag.

## Known limitations

- Raven's mobile apps (iOS / Android) do not show translations; only the web app at `/raven` does.
- Push and e-mail notifications show the original text.
- Raven's own AI features are not used. If both are enabled, they work independently.
- OpenAI-compatible services: the request uses structured output (JSON schema) and, if the service
  rejects it, is retried once in JSON mode.

## Development

```bash
bench --site your-test-site run-tests --app frappe_chat_translate
```

The tests replace the translation engine with a stand-in, so they need no API key. They create test
users and Raven channels: run them on a test site only.

Demo data (two test users and a trilingual Raven channel, for local sites only):

```bash
bench --site your-test-site execute frappe_chat_translate.demo.seed_demo.seed --kwargs "{'owner': 'you@example.com'}"
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

Copyright (c) 2026 Lifegence Corporation
