import frappe as _frappe

from frappe_chat_translate.security.guard import get_overrides

app_name = "frappe_chat_translate"
app_title = "Frappe Chat Translate"
app_publisher = "Lifegence Corporation"
app_description = "Access control hardening and real-time message translation for ClefinCode Chat"
app_email = "contact@lifegence.com"
app_license = "GPL-3.0"

required_apps = ["frappe", "clefincode_chat"]

# Every whitelisted method of clefincode_chat.api.* is routed through an access-checked wrapper.
override_whitelisted_methods = get_overrides()

# translations are made when a message is displayed; an edit clears its cached translations
doc_events = {
    "ClefinCode Chat Message": {
        "on_update": "frappe_chat_translate.translation.on_message_update",
    }
}

# the chat runs in the desk and, for website users, on portal pages.
# A bundle gets a content hash in its file name at build time, so browsers never keep an old copy.
app_include_js = "frappe_chat_translate.bundle.js"
web_include_js = "frappe_chat_translate.bundle.js"


after_install = "frappe_chat_translate.install.ensure_chat_icon"
after_migrate = "frappe_chat_translate.install.ensure_chat_icon"

# Frappe v15 has no standard Desktop Icon / Workspace Sidebar (v16 uses desktop_icon/ and
# workspace_sidebar/ in this app); list the Chat workspace on the v15 apps screen instead.
# Not declared on v16, where it would add a second, App-type icon.
if int(_frappe.__version__.split(".")[0]) < 16:
    add_to_apps_screen = [
        {
            "name": "frappe_chat_translate",
            "logo": "/assets/frappe_chat_translate/images/chat.svg",
            "title": "Chat",
            "route": "/app/chat",
            "has_permission": "frappe_chat_translate.install.can_manage_chat",
        }
    ]
