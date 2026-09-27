# Privacy Policy - Frappe Chat Translate

Last updated: 2026-09-27

Frappe Chat Translate ("the app") is an open-source add-on for ClefinCode Chat, published by
Lifegence Corporation. The app runs inside your own Frappe site. This policy explains what data the
app handles and where it goes.

## What Lifegence receives

Nothing. The app does not send any data to Lifegence Corporation, and it has no analytics,
telemetry or usage tracking.

## Data sent to the translation engine

To translate, the app sends the text of chat messages, the reader's language, and the glossary and
translation context set by your administrator to the translation engine chosen by your site
administrator:

- Anthropic (Claude API),
- Google (Gemini API), or
- OpenAI (OpenAI API), or another OpenAI-compatible service at the address your administrator
  configures (for example Azure OpenAI or a server you run yourself).

Messages are sent when they are displayed to a reader whose language differs from the message, using
the API key configured on your site. The provider's terms and privacy policy apply to that data;
with a self-hosted service, the data stays on the servers you run.
Choose an API plan whose terms fit your data, for example one that does not use your data for
training. Attachments, voice clips and images are not sent.

## Data stored in your site

- Translations are cached in your site's database (DocType "Chat Message Translation"), per message
  and language. They are deleted when the message is edited.
- API keys are stored encrypted in your site's database.
- When the access checks refuse or (in log-only mode) record a request, the app writes the user, the
  API method and the reason to your site's log files. Errors from the translation engine are written
  to your site's Error Log.

This data stays in your site, under your control, and follows your site's backup and retention
settings.

## Contact

Lifegence Corporation - contact@lifegence.com
Security issues: see SECURITY.md in the repository.
