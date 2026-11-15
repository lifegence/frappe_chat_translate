import frappe
from frappe.model.document import Document


class ChatMessageTranslation(Document):
    pass


def on_doctype_update():
    # One cached translation per message and language. Two viewers opening the same message at the
    # same moment used to store it twice (0.3.x); the second insert now fails and is ignored.
    frappe.db.add_unique("Chat Message Translation", ["message", "language"], "unique_message_language")
