"""Demo data for checking translations: two test users and a trilingual Raven channel.

    bench --site SITE execute frappe_chat_translate.demo.seed_demo.seed --kwargs "{'owner': 'you@example.com'}"

`owner` is an existing user who joins the group (their language decides what they see translated).
Re-running removes the previous demo group and posts the conversation again.
Returns the test users' passwords (random, generated per run): demo users are for local sites only.
"""

import secrets

import frappe
from frappe.utils.password import update_password

GROUP = "Chat Translate Demo"
USERS = [
    # (email, first name, last name, language)
    ("demo.vi@example.com", "Nguyen Van", "An (demo)", "vi"),
    ("demo.en@example.com", "Emily", "Carter (demo)", "en"),
]

# (sender: "owner" | email, message). A fictional online-shop project.
CONVERSATION = [
    ("owner", "お疲れ様です。ネットショップ改修の第1回リリースに向けて、今週の進め方を確認させてください。"),
    (
        "demo.vi@example.com",
        "Chào anh. Tuần này bên em sẽ hoàn thành chức năng giỏ hàng và API tìm kiếm sản phẩm.",
    ),
    (
        "demo.en@example.com",
        "Thanks. Please make sure the staging environment is ready by 10/22 so we can start integration tests on 10/23.",
    ),
    ("owner", "ステージング環境は10/22までに用意します。試験仕様書の草案は10/9に共有します。"),
    (
        "demo.vi@example.com",
        "Em đã sửa lỗi trong file cart_service.py và đẩy lên nhánh develop rồi ạ. Anh xem giúp em Pull Request #12 nhé.",
    ),
    ("owner", "確認しました。テスト CART-001 がまだ失敗しているようです。原因を調べてもらえますか？"),
    ("demo.vi@example.com", "Dạ, lỗi là do tổng tiền được làm tròn khác nhau. Em sẽ sửa trước thứ Sáu."),
    (
        "demo.en@example.com",
        "Quick reminder: the vulnerability scan must be finished before the Dec 18 release.",
    ),
    ("owner", "了解です。脆弱性診断の範囲は、今回リリースするカートと検索の機能に限定してください。"),
    ("demo.vi@example.com", "Vâng, em hiểu rồi. Cảm ơn anh!"),
]


WORKSPACE = "Chat Translate Demo"


def _ensure_user(email, first, last, lang):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            doctype="User",
            email=email,
            first_name=first,
            last_name=last,
            user_type="System User",
            send_welcome_email=0,
            language=lang,
            roles=[{"role": "Raven User"}],
        ).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("User", email, "language", lang)
        frappe.get_doc("User", email).add_roles("Raven User")
    password = secrets.token_urlsafe(12)
    update_password(email, password)
    return password


def _ensure_workspace(members):
    if not frappe.db.exists("Raven Workspace", WORKSPACE):
        frappe.get_doc(doctype="Raven Workspace", workspace_name=WORKSPACE, type="Public").insert(
            ignore_permissions=True
        )
    for i, email in enumerate(members):
        if not frappe.db.exists("Raven Workspace Member", {"workspace": WORKSPACE, "user": email}):
            frappe.get_doc(
                doctype="Raven Workspace Member", workspace=WORKSPACE, user=email, is_admin=int(i == 0)
            ).insert(ignore_permissions=True)


def _remove_old_channel():
    for name in frappe.get_all("Raven Channel", filters={"workspace": WORKSPACE}, pluck="name"):
        for msg in frappe.get_all("Raven Message", filters={"channel_id": name}, pluck="name"):
            frappe.db.delete("Chat Message Translation", {"message": msg})
        frappe.delete_doc("Raven Channel", name, force=True, ignore_permissions=True)


def seed(owner: str):
    if not frappe.db.exists("User", owner):
        frappe.throw(f"User {owner} not found")
    passwords = {email: _ensure_user(email, first, last, lang) for email, first, last, lang in USERS}
    frappe.get_doc("User", owner).add_roles("Raven User")
    members = [owner] + [email for email, *_ in USERS]
    _ensure_workspace(members)
    _remove_old_channel()

    # Run from the command line only (bench execute, not whitelisted): each demo message is sent as its
    # author, so Raven records the right sender.
    frappe.set_user(owner)  # nosemgrep
    channel = frappe.get_doc(
        doctype="Raven Channel", channel_name=GROUP, type="Private", workspace=WORKSPACE
    ).insert()
    channel.add_members([email for email, *_ in USERS])

    for sender, text in CONVERSATION:
        frappe.set_user(owner if sender == "owner" else sender)  # nosemgrep
        frappe.get_doc(
            doctype="Raven Message",
            channel_id=channel.name,
            message_type="Text",
            text=f"<p>{frappe.utils.escape_html(text)}</p>",
        ).insert()
    frappe.set_user("Administrator")  # nosemgrep
    frappe.db.commit()
    return {"channel": channel.name, "messages": len(CONVERSATION), "passwords": passwords}
