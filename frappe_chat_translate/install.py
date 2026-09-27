import os

import frappe
from frappe.modules.import_file import import_file_by_path


def ensure_chat_icon():
    """The apps-screen "Chat" icon is a standard Desktop Icon (desktop_icon/chat.json) that opens the
    Chat workspace. Versions up to 0.1.0 created an App-type icon of the same name from code; replace it."""
    if not frappe.db.exists("DocType", "Desktop Icon"):
        return
    if frappe.db.get_value("Desktop Icon", "Chat", "icon_type") == "App":
        frappe.delete_doc("Desktop Icon", "Chat", force=True, ignore_permissions=True)
        import_file_by_path(os.path.join(os.path.dirname(__file__), "desktop_icon", "chat.json"), force=True)
    frappe.clear_cache()
