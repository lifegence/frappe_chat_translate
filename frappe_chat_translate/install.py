import frappe

# Up to 0.3.x the app shipped a "Chat" workspace, sidebar and apps-screen icon for ClefinCode Chat.
# From 0.4.0 Raven brings its own icon; the translation history and settings live in the
# "Chat Translate" workspace.
OLD_CHAT_RECORDS = (("Desktop Icon", "Chat"), ("Workspace Sidebar", "Chat"), ("Workspace", "Chat"))


def after_install():
    remove_old_chat_records()
    frappe.clear_cache()


def remove_old_chat_records():
    for doctype, name in OLD_CHAT_RECORDS:
        if not frappe.db.table_exists(doctype) or not frappe.db.exists(doctype, name):
            continue
        if frappe.db.has_column(doctype, "app") and frappe.db.get_value(doctype, name, "app") not in (
            None,
            "",
            "frappe_chat_translate",
        ):
            continue  # someone else's record with the same name
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
