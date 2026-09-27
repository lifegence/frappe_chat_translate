"""Authorization guard for ClefinCode Chat's whitelisted API.

ClefinCode Chat (clefincode_chat) exposes several hundred whitelisted methods under
``clefincode_chat.api.*``. Many of them take the acting user (``user_email`` / ``email``)
and the channel (``room`` and friends) from request parameters and run raw SQL without
checking that the logged-in user is that user or a member of that channel. Any logged-in
user - including a Website User - could therefore read other people's channels and messages.

This module wraps every whitelisted method of clefincode_chat through the
``override_whitelisted_methods`` hook, so the check runs after authentication (session,
API key or token) and before the original method:

* channel parameters (room, channel, chat_channel, parent_channel, sub_channel,
  last_active_sub_channel), ``chat_topic`` and ``message_name`` must belong to a channel
  the session user is a member or contributor of (or whose parent channel they belong to);
* parameters naming the acting user (user_email, email, user) must be the session user,
  except for methods where they legitimately name somebody else (IDENTITY_EXEMPT);
* Guest requests are refused unless the method is harmless (GUEST_OK) or portal support
  is enabled in ClefinCode Chat Settings (token-based guest chat is left to clefincode_chat).

Administrator is not checked. Set ``chat_guard_mode`` to ``"log"`` in site_config.json to
log violations without refusing them (for diagnosing false positives).
"""

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path

import frappe
from frappe import _

ROOM_PARAMS = ("room", "channel", "chat_channel", "parent_channel", "sub_channel", "last_active_sub_channel")
IDENTITY_PARAMS = ("user_email", "email", "user")

# methods whose user parameters legitimately name another person (the channel check still applies)
IDENTITY_EXEMPT = {
    "login",
    "remove_group_member",
    "remove_group_member_and_assign_new_admin",
    "get_room_admins",
    "check_if_removed",
    "check_if_room_admin",
    "get_profile_full_name",
    "get_last_active",
    "check_if_contact_has_chat",
    "check_if_contact_has_whatsapp_chat",
    "check_if_contributor_active",
    "get_sub_channel_members",
    "get_user_timezone",
    "send_instagram_message",
    "send_messenger_message",
}

# harmless methods a Guest may always call
GUEST_OK = {"get_settings", "check_server", "get_frappe_major_version", "get_versions", "login"}

_WRAPPERS: dict[str, str] = {}  # original method path -> wrapper path


def _clefincode_api_files():
    spec = importlib.util.find_spec("clefincode_chat")
    if not spec or not spec.submodule_search_locations:
        return []
    root = Path(list(spec.submodule_search_locations)[0])
    return sorted((root / "api").rglob("*.py"))


def _whitelisted_functions(path: Path):
    """Yield (function name, allow_guest) for whitelisted top-level functions, without importing."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if getattr(target, "attr", None) == "whitelist" or getattr(target, "id", None) == "whitelist":
                allow_guest = isinstance(dec, ast.Call) and any(
                    k.arg == "allow_guest" and getattr(k.value, "value", False) for k in dec.keywords
                )
                yield node.name, bool(allow_guest)
                break


def _make_wrapper(method: str, fn_name: str, allow_guest: bool):
    def wrapper(*args, **kwargs):
        check_access(fn_name, kwargs)
        # `method` is fixed when the wrappers are built, from ClefinCode Chat's source files (never
        # from the request): call the original whitelisted method after the checks
        return frappe.call(frappe.get_attr(method), *args, **kwargs)  # nosemgrep

    wrapper.__name__ = f"guarded_{fn_name}"
    wrapper.__doc__ = f"Access-checked wrapper for {method}"
    return frappe.whitelist(allow_guest=allow_guest)(wrapper)


def _build():
    module = sys.modules[__name__]
    root = importlib.util.find_spec("clefincode_chat")
    if not root:
        return
    base = Path(list(root.submodule_search_locations)[0]).parent
    for path in _clefincode_api_files():
        dotted = ".".join(path.relative_to(base).with_suffix("").parts)
        for fn_name, allow_guest in _whitelisted_functions(path):
            method = f"{dotted}.{fn_name}"
            attr = "w_" + hashlib.sha1(method.encode()).hexdigest()[:16]
            setattr(module, attr, _make_wrapper(method, fn_name, allow_guest))
            _WRAPPERS[method] = f"{__name__}.{attr}"


def get_overrides() -> dict[str, str]:
    """Mapping for the override_whitelisted_methods hook."""
    return dict(_WRAPPERS)


# ---------------------------------------------------------------- checks


def _deny(fn_name: str, reason: str):
    user = frappe.session.user
    frappe.logger("frappe_chat_translate.guard").warning(f"denied {fn_name} for {user}: {reason}")
    if (frappe.conf.get("chat_guard_mode") or "enforce") == "log":
        return
    frappe.throw(_("You are not permitted to access this chat resource."), frappe.PermissionError)


def _looks_like_user(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return "@" in value or value in ("Administrator", "Guest") or bool(frappe.db.exists("User", value))


def can_access_channel(channel: str, user: str) -> bool:
    """Member or contributor of the channel, or of its parent channel. Unknown channels hold no data."""
    if (
        not isinstance(channel, str)
        or not channel
        or not frappe.db.exists("ClefinCode Chat Channel", channel)
    ):
        return True
    channels = [channel]
    parent = frappe.db.get_value("ClefinCode Chat Channel", channel, "parent_channel")
    if parent:
        channels.append(parent)
    for table in ("ClefinCode Chat Channel User", "ClefinCode Chat Channel Contributor"):
        if frappe.db.exists(table, {"parent": ["in", channels], "user": user}):
            return True
    return False


def _portal_enabled() -> bool:
    return bool(frappe.db.get_single_value("ClefinCode Chat Settings", "enable_portal_support"))


def check_access(fn_name: str, params: dict):
    user = frappe.session.user
    if user == "Administrator":
        return
    if user == "Guest":
        if fn_name in GUEST_OK or (_is_guest_method(fn_name) and _portal_enabled()):
            return
        return _deny(fn_name, "guest")

    if fn_name not in IDENTITY_EXEMPT:
        for p in IDENTITY_PARAMS:
            value = params.get(p)
            if _looks_like_user(value) and value != user:
                return _deny(fn_name, f"{p}={value}")

    for p in ROOM_PARAMS:
        value = params.get(p)
        if value and not can_access_channel(value, user):
            return _deny(fn_name, f"{p}={value}")

    topic = params.get("chat_topic")
    if topic and isinstance(topic, str):
        channel = frappe.db.get_value("ClefinCode Chat Topic", topic, "chat_channel")
        if channel and not can_access_channel(channel, user):
            return _deny(fn_name, f"chat_topic={topic}")

    message = params.get("message_name")
    if message and isinstance(message, str):
        row = frappe.db.get_value(
            "ClefinCode Chat Message", message, ["chat_channel", "sub_channel"], as_dict=True
        )
        if row and not any(c and can_access_channel(c, user) for c in (row.chat_channel, row.sub_channel)):
            return _deny(fn_name, f"message_name={message}")


_GUEST_METHODS: set[str] = set()


def _is_guest_method(fn_name: str) -> bool:
    return fn_name in _GUEST_METHODS


def _collect_guest_methods():
    for path in _clefincode_api_files():
        for fn_name, allow_guest in _whitelisted_functions(path):
            if allow_guest:
                _GUEST_METHODS.add(fn_name)


_build()
_collect_guest_methods()
