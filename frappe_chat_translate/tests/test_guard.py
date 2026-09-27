"""Access checks around ClefinCode Chat's API, exercised through the real request dispatcher."""

import json

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

API = "clefincode_chat.api.api_1_3_4.api"
WEB = "guard.web@example.com"
STAFF = "guard.staff@example.com"


def call(cmd, **params):
    """Dispatch like /api/method/<cmd> (override_whitelisted_methods applies)."""
    from frappe.handler import execute_cmd

    frappe.local.request = frappe._dict(method="POST", path=f"/api/method/{cmd}")
    frappe.local.form_dict = frappe._dict(params)
    return execute_cmd(cmd)


# a desk role of our own, so the tests need no ERPNext
DESK_ROLE = "Chat Translate Test User"


def ensure_user(email, first_name, user_type, roles=()):
    for role in roles:
        if not frappe.db.exists("Role", role):
            frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert(ignore_permissions=True)
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            dict(
                doctype="User", email=email, first_name=first_name, user_type=user_type, send_welcome_email=0
            )
        )
        for role in roles:
            user.append("roles", {"role": role})
        user.insert(ignore_permissions=True)


def make_group(name, members):
    from clefincode_chat.api.api_1_3_4 import api as capi

    frappe.set_user("Administrator")
    room = capi.create_group(
        json.dumps([{"email": m, "platform": "Chat"} for m in members]), "Administrator"
    )["results"][0]["room"]
    frappe.db.set_value("ClefinCode Chat Channel", room, "channel_name", name)
    message = capi.send(f"{name}: hello", "Administrator", room, "Administrator")["results"][0][
        "new_message_name"
    ]
    return room, message


class TestChatGuard(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user(WEB, "Guard Web", "Website User")
        ensure_user(STAFF, "Guard Staff", "System User", roles=(DESK_ROLE,))
        cls.shared, cls.shared_msg = make_group("guard shared", [WEB])
        cls.private, cls.private_msg = make_group("guard private", [STAFF])
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")

    def as_user(self, user):
        frappe.set_user(user)

    def test_member_can_list_read_and_send(self):
        self.as_user(WEB)
        rooms = [r["room"] for r in call(f"{API}.get_channels_list", user_email=WEB)["results"]]
        self.assertIn(self.shared, rooms)
        self.assertNotIn(self.private, rooms)
        messages = call(f"{API}.get_messages", room=self.shared, user_email=WEB, room_type="Group")["results"]
        self.assertTrue(any("hello" in m["content"] for m in messages))
        sent = call(f"{API}.send", content="Xin chào", user="Guard Web", room=self.shared, email=WEB)
        self.assertTrue(sent["results"][0]["new_message_name"])

    def test_cannot_list_someone_elses_channels(self):
        self.as_user(WEB)
        with self.assertRaises(frappe.PermissionError):
            call(f"{API}.get_channels_list", user_email="Administrator")

    def test_cannot_read_channel_without_membership(self):
        self.as_user(WEB)
        for user_email in (WEB, "Administrator"):
            with self.assertRaises(frappe.PermissionError):
                call(f"{API}.get_messages", room=self.private, user_email=user_email, room_type="Group")

    def test_cannot_read_single_message_without_membership(self):
        self.as_user(WEB)
        with self.assertRaises(frappe.PermissionError):
            call(
                f"{API}.get_single_message",
                message_name=self.private_msg,
                chat_channel=self.private,
                user_email=WEB,
            )

    def test_cannot_send_as_someone_else(self):
        self.as_user(WEB)
        with self.assertRaises(frappe.PermissionError):
            call(
                f"{API}.send", content="spoof", user="Administrator", room=self.shared, email="Administrator"
            )

    def test_older_api_versions_are_guarded(self):
        self.as_user(WEB)
        with self.assertRaises(frappe.PermissionError):
            call(
                "clefincode_chat.api.api_1_2_1.api.get_messages",
                room=self.private,
                user_email=WEB,
                room_type="Group",
            )

    def test_system_user_without_membership_is_refused(self):
        self.as_user(STAFF)
        with self.assertRaises(frappe.PermissionError):
            call(f"{API}.get_messages", room=self.shared, user_email=STAFF, room_type="Group")
        messages = call(f"{API}.get_messages", room=self.private, user_email=STAFF, room_type="Group")[
            "results"
        ]
        self.assertTrue(messages)

    def test_guest(self):
        self.as_user("Guest")
        settings = call(f"{API}.get_settings", token="")
        self.assertEqual(settings["user_type"], "guest")
        with self.assertRaises(frappe.PermissionError):
            call(f"{API}.get_messages", room=self.shared, user_email="Guest", room_type="Group")
