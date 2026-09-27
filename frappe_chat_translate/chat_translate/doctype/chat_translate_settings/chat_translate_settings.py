import frappe
from frappe.model.document import Document


class ChatTranslateSettings(Document):
    def validate(self):
        self.make_button_icon_public()

    def make_button_icon_public(self):
        """The chat button is shown to every user, so its image must be a public file.
        Attach fields upload privately by default; move the file to public files."""
        if not (self.button_icon or "").startswith("/private/files/"):
            return
        name = frappe.db.get_value("File", {"file_url": self.button_icon}, "name")
        if not name:
            return
        file = frappe.get_doc("File", name)
        file.is_private = 0
        file.save(ignore_permissions=True)
        self.button_icon = file.file_url
