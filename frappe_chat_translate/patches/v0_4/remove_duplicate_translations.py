from frappe_chat_translate.migrate_from_clefincode import remove_duplicates


def execute():
    """Before the unique (message, language) index is added: drop translations stored twice."""
    print("Chat Translate: duplicate translations removed:", remove_duplicates())
