"""Demo data for checking translations: two test users and a trilingual group conversation.

    bench --site SITE execute frappe_chat_translate.demo.seed_demo.seed --kwargs "{'owner': 'you@example.com'}"

`owner` is an existing user who joins the group (their language decides what they see translated).
Re-running removes the previous demo group and posts the conversation again.
Returns the test users' passwords (random, generated per run): demo users are for local sites only.
"""

import json
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
    ("demo.vi@example.com", "Chào anh. Tuần này bên em sẽ hoàn thành chức năng giỏ hàng và API tìm kiếm sản phẩm."),
    ("demo.en@example.com", "Thanks. Please make sure the staging environment is ready by 10/22 so we can start integration tests on 10/23."),
    ("owner", "ステージング環境は10/22までに用意します。試験仕様書の草案は10/9に共有します。"),
    ("demo.vi@example.com", "Em đã sửa lỗi trong file cart_service.py và đẩy lên nhánh develop rồi ạ. Anh xem giúp em Pull Request #12 nhé."),
    ("owner", "確認しました。テスト CART-001 がまだ失敗しているようです。原因を調べてもらえますか？"),
    ("demo.vi@example.com", "Dạ, lỗi là do tổng tiền được làm tròn khác nhau. Em sẽ sửa trước thứ Sáu."),
    ("demo.en@example.com", "Quick reminder: the vulnerability scan must be finished before the Dec 18 release."),
    ("owner", "了解です。脆弱性診断の範囲は、今回リリースするカートと検索の機能に限定してください。"),
    ("demo.vi@example.com", "Vâng, em hiểu rồi. Cảm ơn anh!"),
]


def _ensure_user(email, first, last, lang):
    if not frappe.db.exists("User", email):
        frappe.get_doc(dict(doctype="User", email=email, first_name=first, last_name=last, user_type="System User",
                            send_welcome_email=0, language=lang, roles=[{"role": "Projects User"}])).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("User", email, "language", lang)
    password = secrets.token_urlsafe(12)
    update_password(email, password)
    return password


def _remove_old_groups():
    for name in frappe.get_all("ClefinCode Chat Channel", filters={"channel_name": GROUP}, pluck="name"):
        frappe.db.delete("Chat Message Translation", {"chat_channel": name})
        frappe.db.delete("ClefinCode Chat Message", {"chat_channel": name})
        frappe.delete_doc("ClefinCode Chat Channel", name, force=True, ignore_permissions=True)


def seed(owner: str):
    from clefincode_chat.api.api_1_3_4 import api as capi

    if not frappe.db.exists("User", owner):
        frappe.throw(f"User {owner} not found")
    passwords = {email: _ensure_user(email, first, last, lang) for email, first, last, lang in USERS}
    _remove_old_groups()

    frappe.set_user(owner)
    members = [{"email": email, "platform": "Chat"} for email, *_ in USERS]
    room = capi.create_group(json.dumps(members), owner)["results"][0]["room"]
    frappe.db.set_value("ClefinCode Chat Channel", room, "channel_name", GROUP)

    for sender, text in CONVERSATION:
        email = owner if sender == "owner" else sender
        frappe.set_user(email)
        name = frappe.db.get_value("User", email, "full_name")
        capi.send(f"<p>{frappe.utils.escape_html(text)}</p>", name, room, email)
    frappe.set_user("Administrator")
    frappe.db.commit()
    return {"group": room, "messages": len(CONVERSATION), "passwords": passwords}
