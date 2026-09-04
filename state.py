"""
Data model + persistence for Kertas Taklimat.

Everything about the report's SHAPE lives in this state, not in the UI code:
categories, items, suppliers, and the columns themselves (what fields exist,
their type, order, and even the bid-status vocabulary) are all data that can
be added/removed/reordered/renamed at runtime. The Streamlit pages read this
state and regenerate their tables/report from it — nothing is hardcoded to
one category set or one field set.

State is persisted to a local JSON file (DATA_FILE) so it survives restarts,
similar in spirit to the browser localStorage used by the original HTML
version of this tool.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime
from pathlib import Path

import seed_data

DATA_FILE = Path(__file__).parent / "kertas_taklimat_data.json"

ROLES = {
    "admin": "Admin",
    "leader": "Ketua Pasukan",
    "kewangan": "Kewangan",
    "technical": "Teknikal",
}

STATUS_COLORS = {
    "ok": {"bg": "#e5f2e9", "fg": "#2f7a4f"},
    "bad": {"bg": "#f7e3e3", "fg": "#a13b3b"},
    "warn": {"bg": "#faeadc", "fg": "#b3541e"},
    "neutral": {"bg": "#eeeeee", "fg": "#4a5b6b"},
}
STATUS_COLOR_LABELS = {
    "ok": "Hijau (Memenuhi)",
    "bad": "Merah (Tidak Memenuhi)",
    "warn": "Kuning (Amaran)",
    "neutral": "Kelabu (Neutral)",
}

COLUMN_TYPES = {
    "text": "Teks (baris tunggal)",
    "longtext": "Teks (perenggan)",
    "number": "Nombor",
    "currency": "Wang (RM)",
    "computed": "Dikira (A op B)",
    "supplier-pick": "Pilihan Penyebut Harga",
    "supplier-matrix": "Blok Tawaran Penyebut Harga",
}


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------
# Auth (lightweight — suitable for a trusted internal tool, not a public
# service: passwords are salted+hashed but there is no session/CSRF hardening
# beyond what Streamlit itself provides).
# --------------------------------------------------------------------------

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
    except (ValueError, AttributeError):
        return False
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == digest


# Setup codes use an alphabet without ambiguous characters (no 0/O, 1/I) so
# they're easy to read aloud or retype from a chat message.
_SETUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_setup_code(length=8):
    return "".join(secrets.choice(_SETUP_CODE_ALPHABET) for _ in range(length))


def create_pending_user(state, username, name, role):
    """
    Create an account with NO password yet. The person completes their own
    account by entering this one-time setup code on the login screen and
    choosing their own password there — the code (like every password in
    this app) is stored only as a salted hash, never in plaintext. Returns
    the plaintext code so the caller (Admin) can hand it to the person
    out-of-band (Slack/WhatsApp/etc) — it is shown once and not recoverable.
    """
    code = generate_setup_code()
    state.setdefault("users", []).append({
        "id": uid("usr"), "username": username, "name": name, "role": role,
        "password": None,
        "pending_setup": True,
        "setup_code_hash": hash_password(code),
    })
    return code


def verify_setup_code(state, username, code):
    """Look up a pending account by username + one-time setup code."""
    uname = (username or "").strip().lower()
    for u in state.get("users", []):
        if u["username"].strip().lower() == uname and u.get("pending_setup"):
            if verify_password(code or "", u.get("setup_code_hash") or ""):
                return u
            return None
    return None


def complete_setup(user, new_password):
    """Finalize a pending account with the password the person chose themselves."""
    user["password"] = hash_password(new_password)
    user["pending_setup"] = False
    user.pop("setup_code_hash", None)
    return user


def regenerate_setup_code(user):
    """Admin can re-issue a fresh one-time code if the original was lost/expired."""
    code = generate_setup_code()
    user["pending_setup"] = True
    user["password"] = None
    user["setup_code_hash"] = hash_password(code)
    return code


def default_users():
    return [
        {"id": uid("usr"), "username": "admin", "name": "Admin", "role": "admin",
         "password": hash_password("admin123")},
        {"id": uid("usr"), "username": "nuhaakhairil4@gmail.com", "name": "Nuha Akhairil", "role": "leader",
         "password": hash_password("xKdpdRpvAIhFwK")},
        {"id": uid("usr"), "username": "kewangan", "name": "Pegawai Kewangan", "role": "kewangan",
         "password": hash_password("kewangan123")},
        {"id": uid("usr"), "username": "teknikal", "name": "Pegawai Teknikal", "role": "technical",
         "password": hash_password("teknikal123")},
    ]


def verify_login(state, username, password):
    uname = (username or "").strip().lower()
    for u in state.get("users", []):
        if u["username"].strip().lower() == uname:
            if u.get("pending_setup") or not u.get("password"):
                return None
            if verify_password(password, u["password"]):
                return u
            return None
    return None


def is_pending_setup(state, username):
    uname = (username or "").strip().lower()
    for u in state.get("users", []):
        if u["username"].strip().lower() == uname and u.get("pending_setup"):
            return True
    return False


def public_user(u):
    """Strip the password hash and setup-code hash before putting a user in
    session_state / notifications."""
    return {k: v for k, v in u.items() if k not in ("password", "setup_code_hash")}


def add_notification(state, from_user, message):
    state.setdefault("notifications", []).insert(0, {
        "id": uid("ntf"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "from_username": from_user["username"],
        "from_name": from_user.get("name", from_user["username"]),
        "message": message,
        "read": False,
    })


def default_columns():
    c_qty = uid("col")
    c_price = uid("col")
    return [
        {"id": uid("col"), "type": "text", "label": "Unit", "order": 1, "deletable": True,
         "show_in_items_tab": True, "editable_in_matrix": False, "tag": "unit"},
        {"id": c_qty, "type": "number", "label": "Kuantiti", "order": 2, "deletable": True,
         "show_in_items_tab": True, "editable_in_matrix": False, "tag": "quantity"},
        {"id": c_price, "type": "currency", "label": "Harga/Unit Anggaran (RM)", "order": 3,
         "deletable": True, "show_in_items_tab": True, "editable_in_matrix": False, "tag": "estUnitPrice"},
        {"id": uid("col"), "type": "computed", "label": "Harga Anggaran (RM)", "order": 4,
         "deletable": True, "show_in_items_tab": True, "editable_in_matrix": False,
         "operand_a": c_qty, "operand_b": c_price, "operator": "*", "display_as": "currency",
         "tag": "estTotal"},
        {"id": uid("col"), "type": "supplier-matrix", "label": "Penyebut Harga", "order": 5,
         "deletable": True, "show_in_items_tab": False, "editable_in_matrix": True},
        {"id": uid("col"), "type": "supplier-pick", "label": "Pembekal Dipilih", "order": 6,
         "deletable": True, "show_in_items_tab": False, "editable_in_matrix": True, "team": "shared",
         "tag": "winner_pick"},
        {"id": uid("col"), "type": "longtext", "label": "Catatan", "order": 7, "deletable": True,
         "show_in_items_tab": False, "editable_in_matrix": True, "team": "shared", "tag": "catatan"},
    ]


def fresh_state_from_seed():
    categories = [
        {"id": uid("cat"), "code": c["code"], "name": c["name"], "order": c["order"], "parent_id": None}
        for c in seed_data.SEED_CATEGORIES
    ]
    code_to_id = {c["code"]: c["id"] for c in categories}

    columns = default_columns()
    unit_col = next(c for c in columns if c.get("tag") == "unit")
    qty_col = next(c for c in columns if c.get("tag") == "quantity")
    price_col = next(c for c in columns if c.get("tag") == "estUnitPrice")

    items = []
    for seq, it in enumerate(seed_data.SEED_ITEMS, start=1):
        items.append({
            "id": uid("itm"),
            "category_id": code_to_id.get(it["categoryCode"]),
            "seq": seq,
            "perkara": it["perkara"],
            "fields": {
                unit_col["id"]: "",
                qty_col["id"]: it["quantity"],
                price_col["id"]: it["estUnitPrice"],
            },
        })

    suppliers = [{"id": uid("sup"), "name": f"Penyebut Harga {n}"} for n in range(1, 8)]

    return {
        "meta": {
            "title": "RUMUSAN LAPORAN PENILAIAN KEWANGAN DAN TEKNIKAL SEBUT HARGA",
            "ref": "ISN/S/1/2026",
        },
        "categories": categories,
        "items": items,
        "suppliers": suppliers,
        "columns": columns,
        "supplier_matrix": {
            "show_unit_price": True,
            "show_total": True,
            "show_status": True,
            "statuses": [
                {"id": "M", "label": "M", "color": "ok"},
                {"id": "TM", "label": "TM", "color": "bad"},
                {"id": "TT", "label": "TT", "color": "neutral"},
            ],
        },
        # bids[item_id][supplier_id] = {"unit_price"/"price_text": <Kewangan>, "status": <Teknikal>}
        "bids": {},
        "users": default_users(),
        "notifications": [],
    }


def migrate(state: dict) -> dict:
    if "columns" not in state:
        state["columns"] = default_columns()
    if "supplier_matrix" not in state:
        state["supplier_matrix"] = {
            "show_unit_price": True, "show_total": True, "show_status": True,
            "statuses": [
                {"id": "M", "label": "M", "color": "ok"},
                {"id": "TM", "label": "TM", "color": "bad"},
                {"id": "TT", "label": "TT", "color": "neutral"},
            ],
        }
    state["supplier_matrix"].pop("show_remark", None)
    state["supplier_matrix"].pop("show_remark_kewangan", None)
    state["supplier_matrix"].pop("show_catatan", None)
    for it in state.get("items", []):
        it.setdefault("fields", {})
        it.pop("catatan", None)
    for item_bids in state.get("bids", {}).values():
        for bid in item_bids.values():
            bid.setdefault("price_text", "")
            bid.pop("remark", None)
            bid.pop("remark_kewangan", None)
    for cat in state.get("categories", []):
        cat.setdefault("parent_id", None)
    has_catatan_tag = any(c.get("tag") == "catatan" for c in state.get("columns", []))
    for col in state.get("columns", []):
        if col.get("editable_in_matrix") and col["type"] != "supplier-matrix":
            col.setdefault("team", "shared")
        if not has_catatan_tag and col["type"] == "longtext" and not col.get("tag") \
                and col["label"].strip().lower() == "catatan":
            col["tag"] = "catatan"
            has_catatan_tag = True

    pick_cols = [c for c in state.get("columns", []) if c["type"] == "supplier-pick"]
    if not any(c.get("tag") == "winner_pick" for c in pick_cols):
        keeper = next((c for c in pick_cols if c.get("tag") == "kewangan_pick"), None) or \
                 (pick_cols[0] if pick_cols else None)
        if keeper is not None:
            keeper["tag"] = "winner_pick"
            keeper.setdefault("label", "Pembekal Dipilih")
        else:
            state.setdefault("columns", []).append({
                "id": uid("col"), "type": "supplier-pick", "label": "Pembekal Dipilih",
                "order": next_order(state["columns"]), "deletable": True,
                "show_in_items_tab": False, "editable_in_matrix": True,
                "team": "shared", "tag": "winner_pick",
            })
    pick_cols = [c for c in state.get("columns", []) if c["type"] == "supplier-pick"]
    extra_pick_ids = {c["id"] for c in pick_cols if c.get("tag") != "winner_pick"}
    if extra_pick_ids:
        state["columns"] = [c for c in state["columns"] if c["id"] not in extra_pick_ids]
        for it in state.get("items", []):
            for cid in extra_pick_ids:
                it.get("fields", {}).pop(cid, None)

    if "users" not in state or not state["users"]:
        state["users"] = default_users()
    for u in state.get("users", []):
        u.setdefault("pending_setup", False)
    state.setdefault("notifications", [])
    state.setdefault("meta", {})
    state["meta"].setdefault("title", "RUMUSAN LAPORAN PENILAIAN KEWANGAN DAN TEKNIKAL SEBUT HARGA")
    state["meta"].setdefault("ref", "")
    state["meta"].pop("tender_date", None)
    state["meta"].pop("evaluation_date", None)
    return state


def load_state() -> dict:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return migrate(json.load(f))
        except Exception:
            pass
    return fresh_state_from_seed()


def save_state(state: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def clear_all_content(state: dict) -> dict:
    """
    Full structural wipe — for reusing this app on a completely different
    tender (see README "reusing this for a completely different tender").

    Empties categories, items, suppliers, and all bids; resets columns back
    to a blank default set (Unit/Kuantiti/Harga Anggaran/Penyebut Harga
    block/Catatan/K & T picks) and the status list to the M/TM/TT default;
    clears the two report dates. User accounts and notification history are
    NOT touched — Admin still manages those separately.
    """
    category_count = len(state.get("categories", []))
    item_count = len(state.get("items", []))
    supplier_count = len(state.get("suppliers", []))
    bid_count = sum(len(v) for v in state.get("bids", {}).values())

    state["categories"] = []
    state["items"] = []
    state["suppliers"] = []
    state["columns"] = default_columns()
    state["bids"] = {}
    state["supplier_matrix"] = {
        "show_unit_price": True, "show_total": True, "show_status": True,
        "show_catatan": True,
        "statuses": [
            {"id": "M", "label": "M", "color": "ok"},
            {"id": "TM", "label": "TM", "color": "bad"},
            {"id": "TT", "label": "TT", "color": "neutral"},
        ],
    }
    state.setdefault("meta", {})

    return {
        "categories": category_count,
        "items": item_count,
        "suppliers": supplier_count,
        "bid_records": bid_count,
    }


def clear_monthly_data(state: dict) -> dict:
    """
    Start a fresh monthly evaluation without destroying the system structure.

    Preserves categories, item names/rows, columns, suppliers, users and
    status definitions. Clears the monthly procurement inputs (supplier bids)
    and item unit/quantity/estimated-price fields. Returns a small summary
    for the UI/audit notification.
    """
    bid_count = sum(
        len(supplier_bids)
        for supplier_bids in state.get("bids", {}).values()
    )
    state["bids"] = {}

    cleared_item_fields = 0
    monthly_tags = {"unit", "quantity", "estUnitPrice", "catatan"}
    for item in state.get("items", []):
        fields = item.setdefault("fields", {})
        for col in state.get("columns", []):
            if col.get("tag") in monthly_tags and col.get("id") in fields:
                if fields.get(col.get("id")) not in (None, ""):
                    cleared_item_fields += 1
                fields[col.get("id")] = "" if col.get("tag") in ("unit", "catatan") else None

    return {
        "bid_records": bid_count,
        "item_fields": cleared_item_fields,
        "items_preserved": len(state.get("items", [])),
    }


# --------------------------------------------------------------------------
# Pure helpers operating on a state dict
# --------------------------------------------------------------------------

def top_level_categories(state):
    """Categories with no parent — what the main Kategori table manages."""
    return sorted(
        [c for c in state["categories"] if not c.get("parent_id")],
        key=lambda c: c["order"],
    )


def subcategories_of(state, parent_id):
    """A category's direct subcategories (nesting is one level deep)."""
    return sorted(
        [c for c in state["categories"] if c.get("parent_id") == parent_id],
        key=lambda c: c["order"],
    )


def sorted_categories(state):
    """
    All categories in display/report order: each top-level category
    immediately followed by its own subcategories (if any). With no
    subcategories defined, this is identical to the old flat sort.
    """
    ordered = []
    for c in top_level_categories(state):
        ordered.append(c)
        ordered.extend(subcategories_of(state, c["id"]))
    return ordered


def leaf_categories(state):
    """
    Categories that actually hold items: a top-level category with no
    subcategories, or any subcategory (subcategories are always leaves).
    A top-level category that HAS subcategories is a header only — its
    items live under its subcategories instead. This is what the
    Kewangan/Teknikal/Matriks pickers should offer, since that's where
    items really are.
    """
    return [c for c in sorted_categories(state) if not subcategories_of(state, c["id"])]


def sorted_columns(state):
    return sorted(state["columns"], key=lambda c: c["order"])


def items_for_category(state, cat_id):
    return sorted(
        [i for i in state["items"] if i["category_id"] == cat_id],
        key=lambda i: i["seq"],
    )


def category_order_number(state, cat_id):
    """Position among TOP-LEVEL categories only, e.g. the '2' in '2.1'."""
    cats = top_level_categories(state)
    for idx, c in enumerate(cats):
        if c["id"] == cat_id:
            return idx + 1
    return None


def category_full_number(state, cat_id):
    """Full dotted number for display: '2' for a top-level category, or
    '2.1' for its first subcategory."""
    cat = next((c for c in state["categories"] if c["id"] == cat_id), None)
    if cat is None:
        return ""
    parent_id = cat.get("parent_id")
    if not parent_id:
        n = category_order_number(state, cat_id)
        return str(n) if n is not None else ""
    siblings = subcategories_of(state, parent_id)
    for idx, s in enumerate(siblings):
        if s["id"] == cat_id:
            return f"{category_full_number(state, parent_id)}.{idx + 1}"
    return ""


def get_field(item, col_id):
    return item.get("fields", {}).get(col_id)


def set_field(item, col_id, value):
    item.setdefault("fields", {})[col_id] = value


def numeric_operand_columns(state):
    return [c for c in sorted_columns(state) if c["type"] in ("number", "currency")]


def compute_column_value(item, col):
    if col["type"] != "computed":
        return get_field(item, col["id"])
    try:
        a = float(get_field(item, col.get("operand_a")) or 0)
    except (TypeError, ValueError):
        a = 0.0
    try:
        b = float(get_field(item, col.get("operand_b")) or 0)
    except (TypeError, ValueError):
        b = 0.0
    op = col.get("operator", "*")
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "/":
        return None if b == 0 else a / b
    return a * b


def fmt_money(n):
    if n is None or n == "":
        return ""
    try:
        return f"{float(n):,.2f}"
    except (TypeError, ValueError):
        return ""


def fmt_number(n):
    if n is None or n == "":
        return ""
    try:
        return f"{float(n):,.0f}" if float(n) == int(float(n)) else f"{float(n):,}"
    except (TypeError, ValueError):
        return ""


def format_column_value(item, col):
    v = compute_column_value(item, col)
    if col["type"] == "currency":
        return fmt_money(v)
    if col["type"] in ("number", "computed"):
        if col.get("display_as") == "currency":
            return fmt_money(v)
        return fmt_number(v) if v not in (None, "") else ""
    return v if v is not None else ""


def get_bid(state, item_id, supplier_id):
    return state["bids"].get(item_id, {}).get(
        supplier_id, {"unit_price": None, "price_text": "", "status": ""}
    )


def set_bid(state, item_id, supplier_id, **patch):
    state["bids"].setdefault(item_id, {}).setdefault(
        supplier_id, {"unit_price": None, "price_text": "", "status": ""}
    )
    state["bids"][item_id][supplier_id].update(patch)


def parse_price_input(text):
    """
    Harga/Unit boxes accept either a number or free text (e.g. Kewangan
    typing 'TT' for Tiada Tawaran instead of leaving it blank). Returns
    (unit_price, price_text) — exactly one of which is set.
    """
    if text is None:
        return None, ""
    text = str(text).strip()
    if text == "":
        return None, ""
    cleaned = text.replace(",", "")
    try:
        return float(cleaned), ""
    except ValueError:
        return None, text


def price_display(bid):
    """What to show in the Harga/Unit cell: the number, the free-text
    override, or nothing."""
    if bid.get("unit_price") is not None:
        return f"{bid['unit_price']:,.2f}"
    return bid.get("price_text") or ""


def status_def(state, status_id):
    for s in state["supplier_matrix"]["statuses"]:
        if s["id"] == status_id:
            return s
    return None


def supplier_name(state, supplier_id):
    for s in state["suppliers"]:
        if s["id"] == supplier_id:
            return s["name"]
    return ""


def compute_tally(state):
    """
    For every (item, supplier) pair, check whether the Kewangan side (unit
    price) and the Teknikal side (status) have both been filled in. Returns
    a summary dict plus a list of specific mismatches for the Leader's
    reconciliation view.
    """
    suppliers = state["suppliers"]
    rows = []
    total = 0
    both_filled = 0
    mismatches = []
    for cat in sorted_categories(state):
        items = items_for_category(state, cat["id"])
        for item in items:
            for sup in suppliers:
                total += 1
                bid = get_bid(state, item["id"], sup["id"])
                price_filled = bid.get("unit_price") is not None
                status_filled = bool(bid.get("status"))
                if price_filled and status_filled:
                    both_filled += 1
                elif price_filled != status_filled:
                    mismatches.append({
                        "category": cat["name"],
                        "item": item["perkara"].split("\n")[0],
                        "supplier": sup["name"],
                        "kewangan_done": price_filled,
                        "teknikal_done": status_filled,
                    })
                rows.append((price_filled, status_filled))
    neither = sum(1 for p, s in rows if not p and not s)
    return {
        "total_pairs": total,
        "both_filled": both_filled,
        "neither_filled": neither,
        "mismatched": len(mismatches),
        "mismatches": mismatches,
    }


def compute_summary(state):
    """
    Overall procurement summary, matching the original template's bottom rows:
    - dept_total: HARGA ANGGARAN JABATAN (RM) — grand total of the department's
      own estimate (qty x estimated unit price) across every item.
    - supplier_totals: HARGA TAWARAN DARI PENYEBUT HARGA (RM) — per supplier,
      the grand total of everything they bid, regardless of outcome.
    - supplier_recommended: HARGA YANG DICADANGKAN (RM) — per supplier, the
      total of only the items where they are the item's chosen winner
      ("Pembekal Dipilih").
    - grand_total: JUMLAH KESELURUHAN PEROLEHAN (RM) — sum of supplier_recommended,
      i.e. the final total procurement value.
    - has_pick_column: whether a "Pembekal Dipilih" pick column exists, so
      callers can show a helpful note instead of a silently-zero total.
    """
    qty_col = next((c for c in state["columns"] if c.get("tag") == "quantity"), None)
    est_col = next((c for c in state["columns"] if c.get("tag") == "estUnitPrice"), None)
    pick_col = next((c for c in state["columns"] if c.get("tag") == "winner_pick"), None)

    dept_total = 0.0
    supplier_totals = {s["id"]: 0.0 for s in state["suppliers"]}
    supplier_recommended = {s["id"]: 0.0 for s in state["suppliers"]}

    for item in state["items"]:
        qty = float(get_field(item, qty_col["id"]) or 0) if qty_col else 0.0
        est_unit = float(get_field(item, est_col["id"]) or 0) if est_col else 0.0
        dept_total += qty * est_unit

        picked_supplier = get_field(item, pick_col["id"]) if pick_col else None
        for s in state["suppliers"]:
            bid = get_bid(state, item["id"], s["id"])
            if bid.get("unit_price") is not None:
                line_total = qty * bid["unit_price"]
                supplier_totals[s["id"]] += line_total
                if picked_supplier == s["id"]:
                    supplier_recommended[s["id"]] += line_total

    grand_total = sum(supplier_recommended.values())
    return {
        "dept_total": dept_total,
        "supplier_totals": supplier_totals,
        "supplier_recommended": supplier_recommended,
        "grand_total": grand_total,
        "has_pick_column": pick_col is not None,
    }


def next_order(rows):
    return (max((r["order"] for r in rows), default=0)) + 1


def next_seq(items):
    return (max((i["seq"] for i in items), default=0)) + 1
