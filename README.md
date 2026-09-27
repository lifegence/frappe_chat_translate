# Frappe Chat Translate

An add-on for [ClefinCode Chat](https://github.com/clefincode/clefincode_chat) on Frappe v15 and v16:

- **Real-time translation** - every participant reads every message in their own language, whatever
  language it was written in. Translations are made when a message is displayed and cached per
  message and language.
- **Access control hardening** - checks that the logged-in user is a member of the channel before
  ClefinCode Chat's API returns or changes its data.
- **Chat workspace** - an apps-screen icon and a workspace with chat history and settings, for
  administrators.
- **Chat button appearance** - replace the icon, colour, size and position of the floating chat button.

It does not modify ClefinCode Chat itself. This project is not affiliated with ClefinCode.

[日本語の README](README_ja.md)

## Requirements

| | Tested with |
|---|---|
| Frappe | v16 (16.33.1, 16.34.2), v15 (15.121.0) |
| ClefinCode Chat | 1.3.913 |
| Python | 3.10 or later (tested with 3.11 on v15, 3.14 on v16) |
| Translation engine | Anthropic Claude or Google Gemini (API key required) |

## Installation

```bash
bench get-app https://github.com/lifegence/frappe_chat_translate
bench --site your-site install-app frappe_chat_translate
bench build --app frappe_chat_translate
bench restart
```

## Configuration

Open **Chat > Settings > Translation Settings** (DocType `Chat Translate Settings`, System Manager only).

| Setting | Notes |
|---|---|
| Enabled | Turns translation on for everyone |
| Translation Engine | `Anthropic Claude` (default model `claude-opus-5`) or `Google Gemini` (default model `gemini-2.5-flash`) |
| API keys | Stored encrypted. Leave empty to use `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` / `GOOGLE_API_KEY` |
| Restrict to Languages | Optional. Empty = every user's language is served |
| Translation Context | Optional. Who is talking to whom; helps with tone and terms |
| Glossary | One entry per line. `term` keeps it untranslated, `term => rendering` fixes the rendering |
| Chat Button | Icon, colour, position and size of the floating chat button |

Each user's language is their **Language** in the user settings.

### How translation works

1. When chat messages appear on screen (history or new ones), the browser asks for translations of
   the visible messages into the viewer's language.
2. Cached translations are returned at once. The rest are translated in one request (up to 50
   messages) and cached per (message, language), so the next viewer with the same language pays
   nothing.
3. Messages already in the viewer's language are not translated. An edited message is translated
   again the next time it is shown.

A translation is only returned for messages in channels the viewer belongs to.

### Data handling

The text of chat messages is sent to the translation engine you choose. Use an API plan whose terms
fit your data (for example, one that does not use your data for training). The API keys are stored
encrypted in the site database.

## Access control hardening

In ClefinCode Chat 1.3.913, many whitelisted API methods take the acting user and the channel from
request parameters without checking them against the logged-in user. As a result, a logged-in user
(including a Website User) could read channels and messages they are not a member of.

This app wraps every whitelisted method of `clefincode_chat.api.*` (via `override_whitelisted_methods`)
and checks, after authentication:

- channel, topic and message parameters belong to a channel the logged-in user is a member or
  contributor of;
- parameters naming the acting user are the logged-in user (except for methods where they
  legitimately name someone else);
- guests may only call harmless methods unless portal support is enabled.

Administrator is not checked. To diagnose a false positive, set `"chat_guard_mode": "log"` in
`site_config.json`: violations are logged instead of refused (`logs/frappe_chat_translate.guard.log`).

The ClefinCode maintainers have been informed. To report a security issue in this app, see
[SECURITY.md](SECURITY.md).

## Chat workspace

The apps screen gets a **Chat** icon (System Manager and Chat Administrator only) that opens a
workspace with:

- **Open Chat** - opens the chat panel on the current page
- **History** - channels, messages, topics and cached translations (all users' conversations)
- **Settings** - ClefinCode Chat settings, translation settings, chat profiles

Other users keep using the floating chat button.

## Known limitations

- Push and e-mail notifications show the original text.
- If a message is edited while another user has it open, that user sees the old translation until
  the page is reloaded.
- The portal chat for Website Users has been tested through the API, not in the browser.
- On Frappe v15, ClefinCode Chat shows a chat icon in the navbar instead of the floating button in
  the desk. The icon image setting applies to it; colour, position and size do not.

## Development

```bash
bench --site your-test-site run-tests --app frappe_chat_translate
```

The tests replace the translation engine with a stand-in, so they need no API key. They create test
users and chat groups: run them on a test site only.

Demo data (two test users and a trilingual group conversation, for local sites only):

```bash
bench --site your-test-site execute frappe_chat_translate.demo.seed_demo.seed --kwargs "{'owner': 'you@example.com'}"
```

## License

GPL-3.0-or-later, the same as ClefinCode Chat. See [LICENSE](LICENSE).

Copyright (c) 2026 Lifegence Corporation
