app_name = "frappe_chat_translate"
app_title = "Frappe Chat Translate"
app_publisher = "Lifegence Corporation"
app_description = "Real-time message translation for Raven"
app_email = "contact@lifegence.com"
app_license = "GPL-3.0"

required_apps = ["frappe", "raven"]

# translations are made when a message is displayed; an edit clears its cached translations
doc_events = {
    "Raven Message": {
        "on_update": "frappe_chat_translate.translation.on_message_update",
        "on_trash": "frappe_chat_translate.translation.on_message_trash",
    }
}

# Raven's web app (/raven) is its own page without Frappe's include hooks: add the translation
# script to that page's HTML. Raven itself is not modified.
after_request = ["frappe_chat_translate.raven_page.add_translation_script"]

after_install = "frappe_chat_translate.install.after_install"
after_migrate = "frappe_chat_translate.install.after_install"
