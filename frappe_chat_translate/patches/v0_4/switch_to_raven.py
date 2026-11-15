from frappe_chat_translate.migrate_from_clefincode import run


def execute():
    """0.4.0 translates Raven instead of ClefinCode Chat: carry the cached translations over."""
    print("Chat Translate: ClefinCode Chat translations ->", run())
