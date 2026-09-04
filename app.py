"""
Kertas Taklimat — Sistem Penilaian Sebut Harga (Streamlit, role-based)

Four roles, four views, one shared dataset:

- Kewangan: fills in supplier unit prices only. Cannot see Teknikal's data entry.
- Teknikal: fills in supplier compliance status ("piawaian") + remarks only.
  Cannot see Kewangan's data entry.
- Leader (Ketua Pasukan): owns the report structure (categories, columns,
  items, suppliers, dates), sees both Kewangan and Teknikal data, can check
  whether the two sides tally, previews the merged final report, and can
  export the full report or either half separately.
- Admin: sees everything and manages user accounts/roles. Admin's own
  content-editing tabs open in read-only mode; to edit, Admin must first
  notify the Leader (one click), which unlocks editing for that session.

This is a lightweight, internal-tool level of access control — suitable for
a trusted local/office network, not a hardened public-facing login system.
"""

from pathlib import Path
import base64
import mimetypes

import pandas as pd
import streamlit as st

import state as S
import report as R

st.set_page_config(page_title="Kertas Taklimat", layout="wide", page_icon="📋")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2.2rem; max-width: 1500px; }

    /* ---------------------------------------------------------------- */
    /* Login screen — centered, roomy, rectangular logo                 */
    /* ---------------------------------------------------------------- */
    .kt-login-anchor { display:block; height:0; overflow:hidden; }
    .block-container:has(.kt-login-anchor) {
        display:flex; flex-direction:column; justify-content:center;
        min-height:88vh; max-width: 1500px;
    }
    .kt-login-card {
        display:flex; flex-direction:column; align-items:center;
        gap:22px; padding:56px 48px 44px 48px; margin:0 auto;
        background:#fff; border:1px solid #e3e7eb; border-radius:16px;
        box-shadow:0 8px 28px rgba(20,42,58,.08); max-width:460px;
    }
    .kt-login-logo-img {
        width:220px; max-width:70%; height:auto; max-height:110px;
        object-fit:contain; background:transparent;
    }
    .kt-login-logo-fallback {
        width:220px;max-width:70%;height:96px;border-radius:10px;
        background:#142a3a;border:2px solid #a6773a;
        display:flex;align-items:center;justify-content:center;
        font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:22px;
        color:#f2e6d3;letter-spacing:.04em;
    }
    .kt-login-title { font-weight:800;font-size:23px;color:#142a3a;text-align:center; }
    .kt-login-subtitle { font-size:13.5px;color:#4a5b6b;text-align:center;margin-top:4px; }
    .kt-login-caption { color:#7b8794;font-size:13px;text-align:center;margin:0 0 4px 0; }
    div[data-testid="stForm"]:has(input[aria-label="Nama Pengguna"]) {
        width:100%; border:none; padding:0;
    }
    div[data-testid="stForm"]:has(input[aria-label="Nama Pengguna"]) label {
        font-weight:600; color:#31485c;
    }
    div[data-testid="stForm"]:has(input[aria-label="Nama Pengguna"]) div[data-testid="stTextInput"] {
        margin-bottom: 6px;
    }

    /* ---------------------------------------------------------------- */
    /* Sidebar navigation — collapsible via Streamlit's native control  */
    /* ---------------------------------------------------------------- */
    .kt-sb-brand {
        display:flex; flex-direction:column; align-items:center; text-align:center;
        gap:8px; padding:4px 4px 16px 4px; border-bottom:1px solid #e6e9ec; margin-bottom:14px;
    }
    .kt-sb-logo-img { width:100%; max-width:140px; height:auto; max-height:56px; object-fit:contain; }
    .kt-sb-logo-fallback {
        width:120px;height:46px;border-radius:4px;background:#1c2e3d;
        display:flex;align-items:center;justify-content:center;
        font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:14px;color:#e8ecef;
        letter-spacing:.06em;
    }
    .kt-sb-title { font-weight:700; font-size:15px; color:#1c2e3d; line-height:1.3; letter-spacing:-.01em; }
    .kt-sb-subtitle { font-size:11px; color:#8894a0; letter-spacing:.02em; }

    .kt-sb-section-label {
        font-size:10.5px; font-weight:600; color:#96a2ad; letter-spacing:.08em;
        text-transform:uppercase; padding:2px 10px 6px 10px;
    }

    section[data-testid="stSidebar"] { border-right:1px solid #e6e9ec; }
    section[data-testid="stSidebar"] button {
        text-align:left !important; justify-content:flex-start !important;
        font-weight:500 !important; font-size:13.5px !important;
        border-radius:4px !important; border:none !important; border-left:2px solid transparent !important;
        background:transparent !important; color:#4a5762 !important;
        padding:8px 12px !important; min-height:auto !important; box-shadow:none !important;
        transition:background .1s ease, color .1s ease;
    }
    section[data-testid="stSidebar"] button:hover {
        background:#f1f3f5 !important; color:#1c2e3d !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] {
        background:#eef1f4 !important; color:#1c2e3d !important;
        border-left:2px solid #4a5762 !important; font-weight:600 !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"]:hover { background:#e6eaee !important; }
    section[data-testid="stSidebar"] hr { margin:14px 0 !important; border-color:#e6e9ec !important; }

    .kt-sb-userinfo {
        display:flex; flex-direction:column; gap:5px; padding:12px 4px 2px 4px;
    }
    .kt-role-badge {
        display:inline-block;padding:2px 10px;border-radius:3px;font-size:10.5px;
        font-weight:600;letter-spacing:.04em; width:fit-content; text-transform:uppercase;
    }
    .kt-role-admin { background:#f0e9dc;color:#8a6423; }
    .kt-role-leader { background:#e2ede6;color:#2f6b48; }
    .kt-role-kewangan { background:#dfe6ee;color:#2c4a5f; }
    .kt-role-technical { background:#f1e0e0;color:#943a3a; }
    .kt-sb-username { color:#1c2e3d; font-weight:600; font-size:13px; }

    .kt-notif-unread { border-left:3px solid #a6773a;padding:8px 12px;background:#faf7f0;margin-bottom:6px;border-radius:4px; }
    .kt-notif-read { border-left:3px solid #d8d3c4;padding:8px 12px;background:#fff;margin-bottom:6px;border-radius:4px;opacity:.7; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _find_logo_data_uri():
    """
    Auto-detects a logo dropped next to app.py (logo.png / logo.jpg / logo.svg).
    Falls back to None so the caller can render a text-monogram badge instead —
    just drop a real ISN logo file in this folder with one of those names and
    it'll be picked up automatically, no code changes needed.
    """
    here = Path(__file__).parent
    for name in ("logo.png", "logo.jpg", "logo.jpeg", "logo.svg"):
        p = here / name
        if p.exists():
            mime = mimetypes.guess_type(p.name)[0] or "image/png"
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"
    return None


_LOGO_URI = _find_logo_data_uri()

# --------------------------------------------------------------------------
# State bootstrap
# --------------------------------------------------------------------------

if "state" not in st.session_state:
    st.session_state.state = S.load_state()

STATE = st.session_state.state


def persist():
    S.save_state(STATE)


def rerun():
    persist()
    st.rerun()


def render_fill_down(items, label, apply_fn, key_prefix, placeholder=""):
    """
    A small 'fill down' control: type one value, say how many rows (counted
    from the top of the current list), click Isi — that value gets applied
    to that many items via apply_fn(item, value) and saved immediately.
    """
    if not items:
        return
    with st.expander(f"⬇ Isi {label} ke Bawah (fill down)"):
        fc1, fc2, fc3 = st.columns([3, 2, 2])
        with fc1:
            fill_value = st.text_input(f"Nilai {label} untuk diisi", key=f"{key_prefix}_fill_value", placeholder=placeholder)
        with fc2:
            fill_count = st.number_input(
                "Bilangan baris (dari atas)", min_value=1, max_value=len(items),
                value=len(items), step=1, key=f"{key_prefix}_fill_count",
            )
        with fc3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button(f"⬇ Isi {label}", key=f"{key_prefix}_fill_btn", use_container_width=True):
                for it in items[: int(fill_count)]:
                    apply_fn(it, fill_value)
                st.success(f"{int(fill_count)} baris dikemaskini.")
                rerun()


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------

def login_screen():
    st.markdown('<div class="kt-login-anchor"></div>', unsafe_allow_html=True)
    if _LOGO_URI:
        logo_html = f'<img src="{_LOGO_URI}" class="kt-login-logo-img">'
    else:
        logo_html = '<div class="kt-login-logo-fallback">ISN</div>'

    mode = st.session_state.get("login_mode", "login")

    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown(
            f'<div class="kt-login-card">'
            f'{logo_html}'
            f'<div>'
            f'<div class="kt-login-title">Kertas Taklimat</div>'
            f'<div class="kt-login-subtitle">Sistem Penilaian Sebut Harga</div>'
            f'</div>'
            f'<div class="kt-login-caption">{"Sila log masuk untuk meneruskan." if mode == "login" else "Tetapkan kata laluan anda sendiri buat kali pertama."}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.write("")

        if mode == "login":
            with st.form("login_form"):
                username = st.text_input("Nama Pengguna")
                password = st.text_input("Kata Laluan", type="password")
                st.write("")
                submitted = st.form_submit_button("Log Masuk", use_container_width=True, type="primary")
            if submitted:
                user = S.verify_login(STATE, username, password)
                if user:
                    st.session_state.auth_user = S.public_user(user)
                    st.rerun()
                elif S.is_pending_setup(STATE, username):
                    st.warning("Akaun ini belum menetapkan kata laluan lagi. Gunakan pautan di bawah untuk tetapkan kata laluan anda.")
                else:
                    st.error("Nama pengguna atau kata laluan salah.")
            st.write("")
            if st.button("Akaun baharu? Tetapkan kata laluan pertama kali", use_container_width=True, key="switch_to_setup"):
                st.session_state["login_mode"] = "setup"
                st.rerun()
        else:
            st.caption(
                "Masukkan nama pengguna dan kod persediaan yang diberikan oleh Admin/Ketua Pasukan anda, "
                "kemudian pilih kata laluan anda sendiri."
            )
            with st.form("setup_form"):
                su_username = st.text_input("Nama Pengguna (cth: emel anda)")
                su_code = st.text_input("Kod Persediaan")
                su_pw1 = st.text_input("Kata Laluan Baharu", type="password")
                su_pw2 = st.text_input("Sahkan Kata Laluan Baharu", type="password")
                st.write("")
                su_submit = st.form_submit_button("Tetapkan Kata Laluan & Log Masuk", use_container_width=True, type="primary")
            if su_submit:
                user = S.verify_setup_code(STATE, su_username, su_code)
                if not user:
                    st.error("Nama pengguna atau kod persediaan tidak sah.")
                elif not su_pw1 or len(su_pw1) < 6:
                    st.error("Kata laluan mestilah sekurang-kurangnya 6 aksara.")
                elif su_pw1 != su_pw2:
                    st.error("Kata laluan tidak sepadan.")
                else:
                    S.complete_setup(user, su_pw1)
                    persist()
                    st.session_state.auth_user = S.public_user(user)
                    st.session_state.pop("login_mode", None)
                    st.rerun()
            st.write("")
            if st.button("Kembali ke log masuk", use_container_width=True, key="switch_to_login"):
                st.session_state.pop("login_mode", None)
                st.rerun()
    st.stop()


if "auth_user" not in st.session_state:
    login_screen()

CURRENT_USER = st.session_state.auth_user
ROLE = CURRENT_USER["role"]
ROLE_CLASS = {"admin": "kt-role-admin", "leader": "kt-role-leader",
              "kewangan": "kt-role-kewangan", "technical": "kt-role-technical"}[ROLE]


def _clear_dialog_body(caption, warning_text, confirm_word, do_clear, metrics=None):
    """Shared confirmation UI for every page-scoped 'Kosongkan' dialog:
    metrics, a warning, a type-to-confirm text box, and Cancel/Confirm
    buttons. `do_clear` is called only once the exact confirm word is typed."""
    st.caption(caption)
    if metrics:
        cols = st.columns(len(metrics))
        for col, (label, value) in zip(cols, metrics.items()):
            col.metric(label, value)
    st.error(warning_text)
    state_key = f"clear_confirm_{confirm_word.replace(' ', '_')}"
    confirm_text = st.text_input(
        f'Taip **{confirm_word}** untuk mengesahkan', key=state_key, placeholder=confirm_word,
    )
    confirmed = confirm_text.strip().upper() == confirm_word

    cbtn1, cbtn2 = st.columns(2)
    with cbtn1:
        if st.button("Batal", use_container_width=True, key=f"cancel_{state_key}"):
            st.session_state.pop(state_key, None)
            st.rerun()
    with cbtn2:
        if st.button("Sahkan & Kosongkan", type="primary", disabled=not confirmed,
                      use_container_width=True, key=f"confirm_{state_key}"):
            do_clear()
            st.session_state.pop(state_key, None)
            persist()
            st.success("Berjaya dikosongkan.")
            st.rerun()


@st.dialog("Kosongkan Kategori")
def _clear_categories_dialog():
    cat_count = len(STATE.get("categories", []))
    item_count = len(STATE.get("items", []))

    def _do():
        STATE["categories"] = []
        STATE["items"] = []
        S.add_notification(
            STATE, CURRENT_USER,
            f"{S.ROLES[ROLE]} {CURRENT_USER['name']} mengosongkan semua Kategori ({cat_count}) dan Item ({item_count}).",
        )

    _clear_dialog_body(
        caption="Kosongkan senarai Kategori beserta semua Item di bawahnya.",
        warning_text="Ini akan memadam **semua Kategori** dan **semua Item**. Lajur, Penyebut Harga dan akaun pengguna tidak disentuh.",
        confirm_word="PADAM KATEGORI",
        do_clear=_do,
        metrics={"Kategori": cat_count, "Item": item_count},
    )


@st.dialog("Kosongkan Lajur")
def _clear_columns_dialog():
    col_count = len(STATE.get("columns", []))

    def _do():
        STATE["columns"] = S.default_columns()
        STATE["supplier_matrix"] = {
            "show_unit_price": True, "show_total": True, "show_status": True, "show_remark": False,
            "statuses": [
                {"id": "M", "label": "M", "color": "ok"},
                {"id": "TM", "label": "TM", "color": "bad"},
                {"id": "TT", "label": "TT", "color": "neutral"},
            ],
        }
        S.add_notification(
            STATE, CURRENT_USER,
            f"{S.ROLES[ROLE]} {CURRENT_USER['name']} mengosongkan struktur Lajur dan konfigurasi Status kembali ke set asas.",
        )

    _clear_dialog_body(
        caption="Set semula struktur Lajur dan konfigurasi Blok Penyebut Harga/Status kembali ke asas.",
        warning_text="Ini akan memadam semua Lajur tersuai dan konfigurasi Status, kembali ke set asas sistem. "
                      "Kategori, Item dan Penyebut Harga tidak disentuh — tetapi nilai lajur tersuai yang telah "
                      "diisi pada item tidak lagi digunakan.",
        confirm_word="PADAM LAJUR",
        do_clear=_do,
        metrics={"Lajur semasa": col_count},
    )


@st.dialog("Kosongkan Item")
def _clear_items_dialog(cat_id, cat_label):
    items_in_cat = S.items_for_category(STATE, cat_id)
    count = len(items_in_cat)

    def _do():
        removed_ids = {i["id"] for i in items_in_cat}
        STATE["items"] = [i for i in STATE["items"] if i["id"] not in removed_ids]
        S.add_notification(
            STATE, CURRENT_USER,
            f"{S.ROLES[ROLE]} {CURRENT_USER['name']} mengosongkan {count} item dalam kategori {cat_label}.",
        )

    _clear_dialog_body(
        caption=f"Kosongkan semua Item dalam kategori **{cat_label}**.",
        warning_text=f"Ini akan memadam **{count} item** dalam kategori ini sahaja. Kategori lain, Lajur dan Penyebut Harga tidak disentuh.",
        confirm_word="PADAM ITEM",
        do_clear=_do,
        metrics={"Item dalam kategori ini": count},
    )


@st.dialog("Kosongkan Penyebut Harga")
def _clear_suppliers_dialog():
    sup_count = len(STATE.get("suppliers", []))
    bid_count = sum(len(v) for v in STATE.get("bids", {}).values())

    def _do():
        removed_ids = {s["id"] for s in STATE["suppliers"]}
        STATE["suppliers"] = []
        STATE["bids"] = {}
        for it in STATE["items"]:
            for col in STATE["columns"]:
                if col["type"] == "supplier-pick" and S.get_field(it, col["id"]) in removed_ids:
                    S.set_field(it, col["id"], None)
        S.add_notification(
            STATE, CURRENT_USER,
            f"{S.ROLES[ROLE]} {CURRENT_USER['name']} mengosongkan {sup_count} Penyebut Harga dan {bid_count} rekod tawaran.",
        )

    _clear_dialog_body(
        caption="Kosongkan senarai Penyebut Harga beserta semua tawaran mereka.",
        warning_text="Ini akan memadam **semua Penyebut Harga** dan **semua rekod tawaran** (Kewangan + Teknikal). Kategori, Item dan Lajur tidak disentuh.",
        confirm_word="PADAM PENYEBUT",
        do_clear=_do,
        metrics={"Penyebut Harga": sup_count, "Rekod tawaran": bid_count},
    )


@st.dialog("Kosongkan Matriks Tawaran")
def _clear_matrix_dialog(cat_id, cat_label):
    items_in_cat = S.items_for_category(STATE, cat_id)
    item_ids = {i["id"] for i in items_in_cat}
    bid_count = sum(len(m) for iid, m in STATE.get("bids", {}).items() if iid in item_ids)

    def _do():
        for iid in item_ids:
            STATE["bids"].pop(iid, None)
        editable_cols = [c for c in STATE["columns"] if c.get("editable_in_matrix") and c["type"] != "supplier-matrix"]
        for it in items_in_cat:
            for c in editable_cols:
                S.set_field(it, c["id"], None)
        S.add_notification(
            STATE, CURRENT_USER,
            f"{S.ROLES[ROLE]} {CURRENT_USER['name']} mengosongkan matriks tawaran untuk kategori {cat_label} ({bid_count} rekod).",
        )

    _clear_dialog_body(
        caption=f"Kosongkan semua tawaran (Kewangan + Teknikal) untuk kategori **{cat_label}**.",
        warning_text=f"Ini akan memadam **{bid_count} rekod tawaran** dan medan boleh-edit (Catatan, K/T) untuk item dalam kategori ini sahaja.",
        confirm_word="PADAM MATRIKS",
        do_clear=_do,
        metrics={"Rekod tawaran": bid_count},
    )


@st.dialog("Kosongkan Harga Saya")
def _clear_kewangan_dialog(cat_label, sup_id, sup_label, items):
    filled = [it for it in items
              if (lambda b: b["unit_price"] is not None or b.get("price_text"))(S.get_bid(STATE, it["id"], sup_id))]
    count = len(filled)

    def _do():
        for it in filled:
            S.set_bid(STATE, it["id"], sup_id, unit_price=None, price_text="")
        S.add_notification(
            STATE, CURRENT_USER,
            f"Kewangan {CURRENT_USER['name']} mengosongkan {count} harga untuk {cat_label} — {sup_label}.",
        )

    _clear_dialog_body(
        caption=f"Kosongkan harga yang **anda** isi untuk **{cat_label} — {sup_label}**.",
        warning_text=f"Ini akan memadam **{count} harga/unit** yang anda isi untuk kategori & penyebut harga ini sahaja. "
                      "Status Teknikal, Catatan item, dan struktur sistem tidak disentuh.",
        confirm_word="PADAM HARGA",
        do_clear=_do,
        metrics={"Harga diisi": count},
    )


@st.dialog("Kosongkan Penilaian Saya")
def _clear_teknikal_dialog(cat_label, sup_id, sup_label, items):
    filled = [it for it in items if S.get_bid(STATE, it["id"], sup_id)["status"]]
    count = len(filled)

    def _do():
        for it in filled:
            S.set_bid(STATE, it["id"], sup_id, status="")
        S.add_notification(
            STATE, CURRENT_USER,
            f"Teknikal {CURRENT_USER['name']} mengosongkan {count} penilaian untuk {cat_label} — {sup_label}.",
        )

    _clear_dialog_body(
        caption=f"Kosongkan status yang **anda** isi untuk **{cat_label} — {sup_label}**.",
        warning_text=f"Ini akan memadam **{count} status** yang anda isi untuk kategori & penyebut harga ini sahaja. "
                      "Harga Kewangan, Catatan item, dan struktur sistem tidak disentuh.",
        confirm_word="PADAM PENILAIAN",
        do_clear=_do,
        metrics={"Penilaian diisi": count},
    )


def render_sidebar(pages=None):
    """Collapsible left-hand navigation (native Streamlit sidebar toggle),
    replacing the old top navbar/nav-row/user-bar."""
    with st.sidebar:
        if _LOGO_URI:
            logo_html = f'<img src="{_LOGO_URI}" class="kt-sb-logo-img">'
        else:
            logo_html = '<div class="kt-sb-logo-fallback">ISN</div>'
        st.markdown(
            f'<div class="kt-sb-brand">{logo_html}'
            f'<div><div class="kt-sb-title">Kertas Taklimat</div>'
            f'<div class="kt-sb-subtitle">Sistem Penilaian Sebut Harga</div></div></div>',
            unsafe_allow_html=True,
        )

        if pages:
            active_page = st.session_state.get("active_page")
            if active_page not in pages:
                active_page = pages[0]
                st.session_state["active_page"] = active_page
            for name in pages:
                is_active = st.session_state.get("active_page") == name
                if st.button(
                    name,
                    key=f"navbtn_{name}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["active_page"] = name
                    st.rerun()
            st.divider()

        st.markdown(
            f'<div class="kt-sb-userinfo">'
            f'<span class="kt-role-badge {ROLE_CLASS}">{S.ROLES[ROLE]}</span>'
            f'<span class="kt-sb-username">{CURRENT_USER["name"]}</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("Log Keluar", key="navbtn_logout", use_container_width=True):
            st.session_state.pop("auth_user", None)
            st.session_state.pop("active_page", None)
            st.rerun()


def header_bar(editable_meta=False, pages=None):
    render_sidebar(pages=pages)

    if editable_meta:
        t1, t2 = st.columns([3, 1])
        with t1:
            new_title = st.text_input("Tajuk Dokumen", value=STATE["meta"]["title"])
            if new_title != STATE["meta"]["title"]:
                STATE["meta"]["title"] = new_title
                persist()
        with t2:
            new_ref = st.text_input("Rujukan", value=STATE["meta"]["ref"])
            if new_ref != STATE["meta"]["ref"]:
                STATE["meta"]["ref"] = new_ref
                persist()
    else:
        st.caption(f"**{STATE['meta']['title']}**" + (f" — {STATE['meta']['ref']}" if STATE["meta"]["ref"] else ""))

# --------------------------------------------------------------------------
# Admin edit-gate: content tabs open read-only for Admin until they notify
# the Leader, which unlocks editing for the rest of this session.
# --------------------------------------------------------------------------

def admin_gate(tab_key, tab_label):
    if ROLE != "admin":
        return True
    unlock_key = f"admin_unlock_{tab_key}"
    if st.session_state.get(unlock_key):
        st.success(f"Leader telah dimaklumkan — anda kini boleh edit **{tab_label}**.")
        return True
    st.warning(f"Anda melihat **{tab_label}** dalam mod lihat sahaja.")
    if st.button(f"🔔 Saya ingin edit — Maklumkan Leader", key=f"btn_{unlock_key}"):
        S.add_notification(STATE, CURRENT_USER, f"Admin **{CURRENT_USER['name']}** membuka akses edit untuk **{tab_label}**.")
        st.session_state[unlock_key] = True
        rerun()
    return False


# ==========================================================================
# Shared content tabs (used by Leader always-editable, Admin gated)
# ==========================================================================

def render_categories_tab(editable):
    st.subheader("Kategori")
    st.caption(
        "Setiap kategori mewakili satu mesin/kumpulan item. Tambah, buang atau susun semula "
        "(ubah nombor **Turutan**). Kategori boleh dipecahkan kepada **sub-kategori** — pilih "
        "kategori di bawah untuk urus sub-kategorinya."
    )
    all_cats = S.sorted_categories(STATE)
    top_cats = S.top_level_categories(STATE)

    if editable and all_cats:
        _, bcol = st.columns([5, 2])
        with bcol:
            if st.button("Kosongkan Kategori", key="btn_clear_categories", use_container_width=True):
                _clear_categories_dialog()

    item_counts = {c["id"]: len(S.items_for_category(STATE, c["id"])) for c in all_cats}
    rows = [
        {"id": c["id"], "Turutan": c["order"], "Kod": c["code"], "Nama Kategori": c["name"],
         "Bil. Item": item_counts[c["id"]]}
        for c in top_cats
    ]
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id", "Turutan", "Kod", "Nama Kategori", "Bil. Item"])

    if not editable:
        st.dataframe(df.drop(columns=["id"]), use_container_width=True, hide_index=True)
        for c in top_cats:
            subs = S.subcategories_of(STATE, c["id"])
            if subs:
                st.caption(f"↳ Sub-kategori bagi **{c['name']}**")
                sdf = pd.DataFrame([
                    {"Turutan": s["order"], "Kod": s["code"], "Nama Sub-kategori": s["name"],
                     "Bil. Item": item_counts[s["id"]]}
                    for s in subs
                ])
                st.dataframe(sdf, use_container_width=True, hide_index=True)
        return

    edited = st.data_editor(
        df,
        column_order=["Turutan", "Kod", "Nama Kategori", "Bil. Item"],
        column_config={
            "Turutan": st.column_config.NumberColumn("Turutan", width="small", step=1),
            "Kod": st.column_config.TextColumn("Kod", width="small"),
            "Nama Kategori": st.column_config.TextColumn("Nama Kategori", width="large"),
            "Bil. Item": st.column_config.NumberColumn("Bil. Item", width="small", disabled=True),
        },
        num_rows="dynamic", use_container_width=True, hide_index=True, key="categories_editor",
    )
    if st.button("💾 Simpan Perubahan Kategori", key="save_cats"):
        new_categories = []
        kept_ids = set()
        for _, row in edited.iterrows():
            cid = row.get("id")
            if pd.isna(cid) or not cid:
                cid = S.uid("cat")
            kept_ids.add(cid)
            new_categories.append({
                "id": cid, "code": str(row.get("Kod") or "").strip().upper() or "BARU",
                "name": str(row.get("Nama Kategori") or "").strip() or "Kategori Baharu",
                "order": float(row.get("Turutan") or 0), "parent_id": None,
            })
        # existing subcategories are managed in their own panel below and are
        # left untouched here — just carried over as long as their parent survives
        for c in all_cats:
            if c.get("parent_id") and c["parent_id"] in kept_ids:
                kept_ids.add(c["id"])
                new_categories.append(c)
        removed_ids = {c["id"] for c in all_cats} - kept_ids
        if removed_ids:
            STATE["items"] = [i for i in STATE["items"] if i["category_id"] not in removed_ids]
        STATE["categories"] = new_categories
        if ROLE == "admin":
            S.add_notification(STATE, CURRENT_USER, "Admin mengemas kini senarai **Kategori**.")
        rerun()

    st.markdown("---")
    st.markdown("**Sub-kategori** _(pilihan)_")
    if not top_cats:
        st.caption("Tambah sekurang-kurangnya satu kategori dahulu untuk boleh menambah sub-kategori.")
        return

    parent_labels = {c["id"]: f"{S.category_order_number(STATE, c['id'])}. {c['name']}" for c in top_cats}
    selected_parent = st.selectbox(
        "Kategori", options=list(parent_labels.keys()), format_func=lambda x: parent_labels[x],
        key="subcat_parent_select",
    )
    subs = S.subcategories_of(STATE, selected_parent)
    srows = [
        {"id": s["id"], "Turutan": s["order"], "Kod": s["code"],
         "Nama Sub-kategori": s["name"], "Bil. Item": item_counts.get(s["id"], 0)}
        for s in subs
    ]
    sdf = pd.DataFrame(srows) if srows else pd.DataFrame(
        columns=["id", "Turutan", "Kod", "Nama Sub-kategori", "Bil. Item"])
    sub_edited = st.data_editor(
        sdf,
        column_order=["Turutan", "Kod", "Nama Sub-kategori", "Bil. Item"],
        column_config={
            "Turutan": st.column_config.NumberColumn("Turutan", width="small", step=1),
            "Kod": st.column_config.TextColumn("Kod", width="small"),
            "Nama Sub-kategori": st.column_config.TextColumn("Nama Sub-kategori", width="large"),
            "Bil. Item": st.column_config.NumberColumn("Bil. Item", width="small", disabled=True),
        },
        num_rows="dynamic", use_container_width=True, hide_index=True,
        key=f"subcats_editor_{selected_parent}",
    )
    if st.button("➕ Simpan Sub-kategori", key="save_subcats"):
        new_subs = []
        kept_sub_ids = set()
        for _, row in sub_edited.iterrows():
            cid = row.get("id")
            if pd.isna(cid) or not cid:
                cid = S.uid("cat")
            kept_sub_ids.add(cid)
            new_subs.append({
                "id": cid, "code": str(row.get("Kod") or "").strip().upper() or "BARU",
                "name": str(row.get("Nama Sub-kategori") or "").strip() or "Sub-kategori Baharu",
                "order": float(row.get("Turutan") or 0), "parent_id": selected_parent,
            })
        removed_sub_ids = {s["id"] for s in subs} - kept_sub_ids
        if removed_sub_ids:
            STATE["items"] = [i for i in STATE["items"] if i["category_id"] not in removed_sub_ids]
        STATE["categories"] = [c for c in STATE["categories"] if c.get("parent_id") != selected_parent] + new_subs
        if ROLE == "admin":
            S.add_notification(STATE, CURRENT_USER, f"Admin mengemas kini **sub-kategori** bagi {parent_labels[selected_parent]}.")
        rerun()


def render_columns_tab(editable):
    st.subheader("Lajur (Struktur Laporan)")
    st.caption(
        "Tentukan medan/lajur apa yang wujud dalam sistem ini. Untuk lajur yang **boleh edit dalam "
        "Matriks Tawaran**, tetapkan **Pasukan** — ini mengawal sama ada ia muncul pada halaman "
        "Kewangan atau Teknikal."
    )
    cols = S.sorted_columns(STATE)

    if editable and cols:
        _, bcol = st.columns([5, 2])
        with bcol:
            if st.button("Kosongkan Lajur", key="btn_clear_columns", use_container_width=True):
                _clear_columns_dialog()

    team_labels = {"kewangan": "Kewangan Sahaja", "technical": "Teknikal Sahaja", "shared": "Leader/Admin Sahaja"}
    cols_rows = [
        {
            "id": c["id"], "Turutan": c["order"], "Label": c["label"],
            "Jenis": S.COLUMN_TYPES.get(c["type"], c["type"]),
            "Tab Item": bool(c.get("show_in_items_tab", False)),
            "Matriks Tawaran": bool(c.get("editable_in_matrix", False)),
            "Pasukan": team_labels.get(c.get("team", "shared"), "Leader/Admin Sahaja") if c.get("editable_in_matrix") and c["type"] != "supplier-matrix" else "—",
            "_deletable": c.get("deletable", True), "_type_raw": c["type"],
        }
        for c in cols
    ]
    cdf = pd.DataFrame(cols_rows) if cols_rows else pd.DataFrame(
        columns=["id", "Turutan", "Label", "Jenis", "Tab Item", "Matriks Tawaran", "Pasukan", "_deletable", "_type_raw"]
    )

    if not editable:
        st.dataframe(cdf.drop(columns=["id", "_deletable", "_type_raw"]), use_container_width=True, hide_index=True)
    else:
        type_options = list(S.COLUMN_TYPES.values())
        team_options = list(team_labels.values())
        edited_cols = st.data_editor(
            cdf,
            column_order=["Turutan", "Label", "Jenis", "Tab Item", "Matriks Tawaran", "Pasukan"],
            column_config={
                "Turutan": st.column_config.NumberColumn("Turutan", width="small", step=1),
                "Label": st.column_config.TextColumn("Label", width="medium"),
                "Jenis": st.column_config.SelectboxColumn("Jenis", options=type_options, width="medium"),
                "Tab Item": st.column_config.CheckboxColumn("Papar dalam Tab Item"),
                "Matriks Tawaran": st.column_config.CheckboxColumn("Boleh Edit dalam Matriks"),
                "Pasukan": st.column_config.SelectboxColumn("Pasukan", options=team_options, width="medium"),
            },
            num_rows="dynamic", use_container_width=True, hide_index=True, key="columns_editor",
        )
        if st.button("💾 Simpan Struktur Lajur", key="save_cols"):
            label_to_type = {v: k for k, v in S.COLUMN_TYPES.items()}
            team_label_to_key = {v: k for k, v in team_labels.items()}
            new_columns = []
            kept_ids = set()
            for _, row in edited_cols.iterrows():
                cid = row.get("id")
                is_new = pd.isna(cid) or not cid
                if is_new:
                    cid = S.uid("col")
                kept_ids.add(cid)
                new_type = label_to_type.get(row.get("Jenis"), row.get("_type_raw") if not is_new else "text")
                existing = next((c for c in cols if c["id"] == cid), {})
                new_col = {
                    **existing, "id": cid, "type": new_type,
                    "label": str(row.get("Label") or "").strip() or "Lajur",
                    "order": float(row.get("Turutan") or 0),
                    "deletable": bool(row.get("_deletable", True)),
                    "show_in_items_tab": bool(row.get("Tab Item", False)),
                    "editable_in_matrix": bool(row.get("Matriks Tawaran", False)),
                }
                if new_col["editable_in_matrix"] and new_type != "supplier-matrix":
                    new_col["team"] = team_label_to_key.get(row.get("Pasukan"), "shared")
                new_columns.append(new_col)
            removed_ids = {c["id"] for c in cols} - kept_ids
            STATE["columns"] = new_columns
            if removed_ids:
                for it in STATE["items"]:
                    for rid in removed_ids:
                        it.get("fields", {}).pop(rid, None)
            if ROLE == "admin":
                S.add_notification(STATE, CURRENT_USER, "Admin mengemas kini **Struktur Lajur**.")
            rerun()

    computed_cols = [c for c in S.sorted_columns(STATE) if c["type"] == "computed"]
    if computed_cols and editable:
        st.markdown("##### Formula Lajur Dikira")
        numeric_cols = S.numeric_operand_columns(STATE)
        numeric_options = {c["id"]: c["label"] for c in numeric_cols}
        op_labels = {"*": "×", "+": "+", "-": "−", "/": "÷"}
        for col in computed_cols:
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 2, 2])
            with c1:
                st.caption(f"**{col['label']}** =")
            ids = list(numeric_options.keys())
            with c2:
                a_idx = ids.index(col.get("operand_a")) if col.get("operand_a") in ids else 0
                a = st.selectbox("A", ids, index=a_idx if ids else 0, format_func=lambda x: numeric_options.get(x, "?"),
                                  key=f"opa_{col['id']}", label_visibility="collapsed") if ids else None
            with c3:
                ops = list(op_labels.keys())
                op_idx = ops.index(col.get("operator", "*"))
                op = st.selectbox("op", ops, index=op_idx, format_func=lambda x: op_labels[x],
                                   key=f"op_{col['id']}", label_visibility="collapsed")
            with c4:
                b_idx = ids.index(col.get("operand_b")) if col.get("operand_b") in ids else 0
                b = st.selectbox("B", ids, index=b_idx if ids else 0, format_func=lambda x: numeric_options.get(x, "?"),
                                  key=f"opb_{col['id']}", label_visibility="collapsed") if ids else None
            with c5:
                disp_cur = st.checkbox("Papar sebagai RM", value=col.get("display_as") == "currency", key=f"dc_{col['id']}")
            if a != col.get("operand_a") or b != col.get("operand_b") or op != col.get("operator") \
                    or (disp_cur != (col.get("display_as") == "currency")):
                col["operand_a"] = a; col["operand_b"] = b; col["operator"] = op
                col["display_as"] = "currency" if disp_cur else "number"
                persist()

    st.divider()
    st.markdown("##### Konfigurasi Blok Penyebut Harga")
    cfg = STATE["supplier_matrix"]
    if editable:
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            v = st.checkbox("Papar Harga/Unit", value=cfg["show_unit_price"], key="cfg_up")
            if v != cfg["show_unit_price"]:
                cfg["show_unit_price"] = v; rerun()
        with cc2:
            v = st.checkbox("Papar Jumlah", value=cfg["show_total"], key="cfg_tot")
            if v != cfg["show_total"]:
                cfg["show_total"] = v; rerun()
        with cc3:
            v = st.checkbox("Papar Status", value=cfg["show_status"], key="cfg_st")
            if v != cfg["show_status"]:
                cfg["show_status"] = v; rerun()
        st.caption("Harga/Unit dan Status boleh diisi dengan nombor/kod (cth. TT, M, TM) ATAU teks bebas jika perlu — "
                   "boleh diisi di **Kewangan**, **Teknikal**, atau **Matriks Tawaran**. Lajur **Catatan** dikongsi "
                   "antara Kewangan & Teknikal (satu nota setiap item) — urus/buang ia macam lajur lain di atas.")

        st_rows = [
            {"Kod": s["id"], "Label": s["label"], "Warna": S.STATUS_COLOR_LABELS.get(s["color"], s["color"])}
            for s in cfg["statuses"]
        ]
        sdf = pd.DataFrame(st_rows) if st_rows else pd.DataFrame(columns=["Kod", "Label", "Warna"])
        color_options = list(S.STATUS_COLOR_LABELS.values())
        edited_st = st.data_editor(
            sdf,
            column_config={
                "Kod": st.column_config.TextColumn("Kod", width="small"),
                "Label": st.column_config.TextColumn("Label", width="medium"),
                "Warna": st.column_config.SelectboxColumn("Warna", options=color_options, width="medium"),
            },
            num_rows="dynamic", use_container_width=True, hide_index=True, key="statuses_editor",
        )
        if st.button("💾 Simpan Status", key="save_statuses"):
            color_label_to_key = {v: k for k, v in S.STATUS_COLOR_LABELS.items()}
            new_statuses = []
            for _, row in edited_st.iterrows():
                code = str(row.get("Kod") or "").strip()
                if not code:
                    continue
                new_statuses.append({"id": code, "label": str(row.get("Label") or code).strip(),
                                      "color": color_label_to_key.get(row.get("Warna"), "neutral")})
            cfg["statuses"] = new_statuses or cfg["statuses"]
            if ROLE == "admin":
                S.add_notification(STATE, CURRENT_USER, "Admin mengemas kini **senarai Status**.")
            rerun()
    else:
        st.write(f"Papar Harga/Unit: **{cfg['show_unit_price']}** · Papar Jumlah: **{cfg['show_total']}** · "
                 f"Papar Status: **{cfg['show_status']}**")
        st.dataframe(pd.DataFrame(cfg["statuses"]), use_container_width=True, hide_index=True)


def render_items_tab(editable):
    st.subheader("Item")
    cats = S.leaf_categories(STATE)
    item_cols = [c for c in S.sorted_columns(STATE) if c.get("show_in_items_tab")]
    if not cats:
        st.info("Tiada kategori lagi.")
        return
    cat_labels = {c["id"]: f"{S.category_full_number(STATE, c['id'])} {c['name']}" for c in cats}
    selected_cat = st.selectbox("Kategori", options=list(cat_labels.keys()), format_func=lambda x: cat_labels[x], key="items_cat_select")

    items = S.items_for_category(STATE, selected_cat)

    if editable and items:
        _, bcol = st.columns([5, 2])
        with bcol:
            if st.button("Kosongkan Item", key="btn_clear_items", use_container_width=True):
                _clear_items_dialog(selected_cat, cat_labels[selected_cat])

    rows = []
    for idx, it in enumerate(items):
        row = {"id": it["id"], "Bil.": f"{S.category_full_number(STATE, selected_cat)}.{idx+1}", "Perkara": it["perkara"]}
        for col in item_cols:
            row[col["id"]] = S.compute_column_value(it, col) if col["type"] == "computed" else S.get_field(it, col["id"])
        rows.append(row)
    idf = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id", "Bil.", "Perkara"] + [c["id"] for c in item_cols])

    col_config = {"Bil.": st.column_config.TextColumn("Bil.", width="small", disabled=True),
                  "Perkara": st.column_config.TextColumn("Perkara", width="large")}
    for col in item_cols:
        label = col["label"]
        if col["type"] == "computed":
            col_config[col["id"]] = st.column_config.NumberColumn(label, disabled=True, format="%.2f")
        elif col["type"] == "currency":
            col_config[col["id"]] = st.column_config.NumberColumn(label, format="RM %.2f", step=0.01)
        elif col["type"] == "number":
            col_config[col["id"]] = st.column_config.NumberColumn(label, step=1.0)
        elif col["type"] == "longtext":
            col_config[col["id"]] = st.column_config.TextColumn(label, width="large")
        else:
            col_config[col["id"]] = st.column_config.TextColumn(label)
    order = ["Bil.", "Perkara"] + [c["id"] for c in item_cols]

    if not editable:
        display_cols = ["Bil.", "Perkara"] + [c["id"] for c in item_cols]
        disp = idf[display_cols].rename(columns={c["id"]: c["label"] for c in item_cols}) if rows else idf
        st.dataframe(disp, use_container_width=True, hide_index=True)
        return

    edited_items = st.data_editor(
        idf, column_order=order, column_config=col_config, num_rows="dynamic",
        use_container_width=True, hide_index=True, key=f"items_editor_{selected_cat}",
    )
    if st.button("💾 Simpan Item", key="save_items"):
        other_items = [i for i in STATE["items"] if i["category_id"] != selected_cat]
        max_seq = S.next_seq(STATE["items"])
        new_cat_items = []
        for _, row in edited_items.iterrows():
            iid = row.get("id")
            is_new = pd.isna(iid) or not iid
            if is_new:
                iid = S.uid("itm")
            existing = next((i for i in items if i["id"] == iid), None)
            fields = dict(existing["fields"]) if existing else {}
            for col in item_cols:
                if col["type"] != "computed":
                    val = row.get(col["id"])
                    fields[col["id"]] = None if pd.isna(val) else val
            new_cat_items.append({
                "id": iid, "category_id": selected_cat,
                "seq": existing["seq"] if existing else max_seq,
                "perkara": str(row.get("Perkara") or ""), "fields": fields,
            })
            if is_new:
                max_seq += 1
        STATE["items"] = other_items + new_cat_items
        if ROLE == "admin":
            S.add_notification(STATE, CURRENT_USER, f"Admin mengemas kini **Item** dalam kategori {cat_labels[selected_cat]}.")
        rerun()


def render_suppliers_tab(editable):
    st.subheader("Penyebut Harga")
    st.caption("Senarai syarikat yang menyebut harga.")

    if editable and STATE["suppliers"]:
        _, bcol = st.columns([5, 2])
        with bcol:
            if st.button("Kosongkan Penyebut Harga", key="btn_clear_suppliers", use_container_width=True):
                _clear_suppliers_dialog()

    sup_rows = [{"id": s["id"], "Nama Syarikat": s["name"]} for s in STATE["suppliers"]]
    sup_df = pd.DataFrame(sup_rows) if sup_rows else pd.DataFrame(columns=["id", "Nama Syarikat"])

    if not editable:
        st.dataframe(sup_df.drop(columns=["id"]), use_container_width=True, hide_index=True)
        return

    edited_sup = st.data_editor(
        sup_df, column_order=["Nama Syarikat"],
        column_config={"Nama Syarikat": st.column_config.TextColumn("Nama Syarikat", width="large")},
        num_rows="dynamic", use_container_width=True, hide_index=True, key="suppliers_editor",
    )
    if st.button("💾 Simpan Penyebut Harga", key="save_suppliers"):
        old_ids = {s["id"] for s in STATE["suppliers"]}
        new_suppliers = []
        keep_ids = set()
        for _, row in edited_sup.iterrows():
            sid = row.get("id")
            if pd.isna(sid) or not sid:
                sid = S.uid("sup")
            keep_ids.add(sid)
            new_suppliers.append({"id": sid, "name": str(row.get("Nama Syarikat") or "").strip() or "Penyebut Harga"})
        removed_ids = old_ids - keep_ids
        STATE["suppliers"] = new_suppliers
        for m in STATE["bids"].values():
            for rid in removed_ids:
                m.pop(rid, None)
        if removed_ids:
            for it in STATE["items"]:
                for col in STATE["columns"]:
                    if col["type"] == "supplier-pick" and S.get_field(it, col["id"]) in removed_ids:
                        S.set_field(it, col["id"], None)
        if ROLE == "admin":
            S.add_notification(STATE, CURRENT_USER, "Admin mengemas kini **senarai Penyebut Harga**.")
        rerun()


def render_full_bids_matrix_tab(editable):
    st.subheader("Matriks Tawaran & Penilaian (Penuh)")
    st.caption("Paparan gabungan Kewangan + Teknikal. Digunakan oleh Leader/Admin untuk semakan menyeluruh.")

    cats = S.leaf_categories(STATE)
    if not cats or not STATE["suppliers"]:
        st.info("Perlukan sekurang-kurangnya satu kategori dan satu penyebut harga.")
        return
    cat_labels = {c["id"]: f"{S.category_full_number(STATE, c['id'])} {c['name']}" for c in cats}
    selected_cat = st.selectbox("Kategori", options=list(cat_labels.keys()), format_func=lambda x: cat_labels[x], key="bids_cat_select")

    if editable:
        _, bcol = st.columns([5, 2])
        with bcol:
            if st.button("Kosongkan Matriks", key="btn_clear_matrix", use_container_width=True):
                _clear_matrix_dialog(selected_cat, cat_labels[selected_cat])

    cols = S.sorted_columns(STATE)
    cfg = STATE["supplier_matrix"]
    context_cols = [c for c in cols if c.get("show_in_items_tab") and not c.get("editable_in_matrix") and c["type"] != "supplier-matrix"]
    editable_cols = [c for c in cols if c.get("editable_in_matrix") and c["type"] != "supplier-matrix"]
    suppliers = STATE["suppliers"]

    items = S.items_for_category(STATE, selected_cat)

    if editable:
        for c in editable_cols:
            if c["type"] == "supplier-pick":
                sup_by_name = {s["name"]: s["id"] for s in suppliers}
                render_fill_down(
                    items, c["label"],
                    lambda it, v, cid=c["id"]: S.set_field(it, cid, sup_by_name.get(v.strip()) if v else None),
                    key_prefix=f"matrix_{c['id']}_{selected_cat}",
                    placeholder=f"nama penyebut harga, cth: {suppliers[0]['name'] if suppliers else ''}",
                )
            else:
                render_fill_down(
                    items, c["label"],
                    lambda it, v, cid=c["id"]: S.set_field(it, cid, v),
                    key_prefix=f"matrix_{c['id']}_{selected_cat}",
                )

    rows = []
    for idx, it in enumerate(items):
        row = {"id": it["id"], "Bil.": f"{S.category_full_number(STATE, selected_cat)}.{idx+1}",
               "Perkara": it["perkara"][:60] + ("…" if len(it["perkara"]) > 60 else "")}
        for c in context_cols:
            row[f"ctx__{c['id']}"] = S.format_column_value(it, c)
        for s in suppliers:
            bid = S.get_bid(STATE, it["id"], s["id"])
            if cfg["show_unit_price"]:
                row[f"price__{s['id']}"] = S.price_display(bid)
            if cfg["show_status"]:
                row[f"status__{s['id']}"] = bid.get("status") or ""
        for c in editable_cols:
            row[f"field__{c['id']}"] = (S.supplier_name(STATE, S.get_field(it, c["id"])) or "") if c["type"] == "supplier-pick" else S.get_field(it, c["id"])
        rows.append(row)

    col_order = ["Bil.", "Perkara"] + [f"ctx__{c['id']}" for c in context_cols]
    col_config = {"Bil.": st.column_config.TextColumn("Bil.", width="small", disabled=True),
                  "Perkara": st.column_config.TextColumn("Perkara", width="large", disabled=True)}
    for c in context_cols:
        col_config[f"ctx__{c['id']}"] = st.column_config.TextColumn(c["label"], disabled=True, width="small")

    status_hint = " / ".join(s["id"] for s in cfg["statuses"])
    for s in suppliers:
        if cfg["show_unit_price"]:
            col_order.append(f"price__{s['id']}")
            col_config[f"price__{s['id']}"] = st.column_config.TextColumn(f"{s['name']} — RM/unit", width="small", disabled=not editable)
        if cfg["show_status"]:
            col_order.append(f"status__{s['id']}")
            col_config[f"status__{s['id']}"] = st.column_config.TextColumn(f"{s['name']} — Status ({status_hint})", width="small", disabled=not editable)

    supplier_name_to_id = {s["name"]: s["id"] for s in suppliers}
    for c in editable_cols:
        col_order.append(f"field__{c['id']}")
        if c["type"] == "supplier-pick":
            col_config[f"field__{c['id']}"] = st.column_config.SelectboxColumn(c["label"], options=[""] + list(supplier_name_to_id.keys()), width="medium", disabled=not editable)
        elif c["type"] in ("number", "currency"):
            col_config[f"field__{c['id']}"] = st.column_config.NumberColumn(c["label"], step=0.01, disabled=not editable)
        else:
            col_config[f"field__{c['id']}"] = st.column_config.TextColumn(c["label"], width="medium", disabled=not editable)

    mdf = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id", "Bil.", "Perkara"])

    if not editable:
        st.dataframe(mdf.drop(columns=["id"]) if "id" in mdf.columns else mdf,
                     column_order=col_order[1:], column_config=col_config, use_container_width=True, hide_index=True)
        return

    edited_bids = st.data_editor(
        mdf, column_order=col_order, column_config=col_config, use_container_width=True, hide_index=True,
        disabled=["Bil.", "Perkara"] + [f"ctx__{c['id']}" for c in context_cols], key=f"bids_editor_{selected_cat}",
    )
    if st.button("💾 Simpan Matriks Tawaran", key="save_bids"):
        for _, row in edited_bids.iterrows():
            iid = row.get("id")
            if pd.isna(iid) or not iid:
                continue
            item = next((i for i in STATE["items"] if i["id"] == iid), None)
            if not item:
                continue
            for s in suppliers:
                patch = {}
                if cfg["show_unit_price"]:
                    up, ptext = S.parse_price_input(row.get(f"price__{s['id']}"))
                    patch["unit_price"] = up
                    patch["price_text"] = ptext
                if cfg["show_status"]:
                    v = row.get(f"status__{s['id']}")
                    patch["status"] = "" if (pd.isna(v) or v is None) else v
                if patch:
                    S.set_bid(STATE, iid, s["id"], **patch)
            for c in editable_cols:
                v = row.get(f"field__{c['id']}")
                if c["type"] == "supplier-pick":
                    S.set_field(item, c["id"], supplier_name_to_id.get(v) if v else None)
                else:
                    S.set_field(item, c["id"], None if pd.isna(v) else v)
        if ROLE == "admin":
            S.add_notification(STATE, CURRENT_USER, f"Admin mengemas kini **Matriks Tawaran** untuk {cat_labels[selected_cat]}.")
        rerun()


def render_report_tab():
    st.subheader("Laporan")
    st.caption("Pratonton kertas taklimat lengkap (gabungan Kewangan + Teknikal), dijana secara langsung.")

    b1, b2, b3 = st.columns(3)
    with b1:
        try:
            st.download_button("⬇ Laporan Penuh (Gabungan)", data=R.build_excel(STATE, scope="full"),
                                file_name=f"Kertas_Taklimat_Penuh_{STATE['meta']['ref'].replace('/', '-') or 'laporan'}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True)
        except Exception as e:
            st.error(f"Ralat: {e}")
    with b2:
        try:
            st.download_button("⬇ Laporan Kewangan Sahaja", data=R.build_excel(STATE, scope="kewangan"),
                                file_name=f"Kertas_Taklimat_Kewangan_{STATE['meta']['ref'].replace('/', '-') or 'laporan'}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True)
        except Exception as e:
            st.error(f"Ralat: {e}")
    with b3:
        try:
            st.download_button("⬇ Laporan Teknikal Sahaja", data=R.build_excel(STATE, scope="technical"),
                                file_name=f"Kertas_Taklimat_Teknikal_{STATE['meta']['ref'].replace('/', '-') or 'laporan'}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True)
        except Exception as e:
            st.error(f"Ralat: {e}")

    st.caption("Untuk cetak/PDF: gunakan fungsi cetak pelayar (Ctrl/Cmd+P) pada halaman pratonton di bawah.")
    html = R.build_report_html(STATE)
    st.markdown(
        f'<div style="background:#fff;color:#1c2b39;border:1px solid #d8d3c4;border-radius:6px;padding:24px;overflow-x:auto">{html}</div>',
        unsafe_allow_html=True,
    )


def render_tally_tab():
    st.subheader("Semakan (Tally Kewangan vs Teknikal)")
    st.caption("Menyemak sama ada setiap pasangan item × penyebut harga telah diisi oleh KEDUA-DUA pasukan.")

    tally = S.compute_tally(STATE)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jumlah Pasangan", tally["total_pairs"])
    m2.metric("Lengkap (Kedua-dua)", tally["both_filled"])
    m3.metric("Belum Mula", tally["neither_filled"])
    m4.metric("Tidak Tally ⚠️", tally["mismatched"])

    if tally["mismatches"]:
        st.markdown("##### Butiran Tidak Tally")
        st.caption("Item/penyebut harga di mana satu pihak sudah isi tetapi satu lagi belum.")
        mdf = pd.DataFrame(tally["mismatches"])
        mdf["Status"] = mdf.apply(
            lambda r: "✅ Kewangan sahaja" if r["kewangan_done"] else "✅ Teknikal sahaja", axis=1
        )
        st.dataframe(
            mdf[["category", "item", "supplier", "Status"]].rename(
                columns={"category": "Kategori", "item": "Perkara", "supplier": "Penyebut Harga"}
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.success("Tiada percanggahan — semua entri yang telah diisi adalah tally di kedua-dua pihak.")




def render_notifications_tab():
    st.subheader("Notifikasi")
    notifs = STATE.get("notifications", [])
    if not notifs:
        st.info("Tiada notifikasi.")
        return
    for n in notifs:
        cls = "kt-notif-read" if n.get("read") else "kt-notif-unread"
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(
                f'<div class="{cls}"><b>{n["from_name"]}</b> · <span style="color:#4a5b6b;font-size:11px">{n["timestamp"]}</span><br>{n["message"]}</div>',
                unsafe_allow_html=True,
            )
        with col2:
            if not n.get("read") and st.button("Tandakan Dibaca", key=f"read_{n['id']}"):
                n["read"] = True
                rerun()


def render_user_management_tab():
    st.subheader("Pengurusan Pengguna")
    st.caption("Cipta akaun untuk Kewangan, Teknikal dan Leader, serta urus peranan mereka.")

    setup_msg = st.session_state.pop("last_setup_code_msg", None)
    if setup_msg:
        st.success(
            f"Akaun **{setup_msg['username']}** dicipta. Kongsikan kod persediaan ini dengan mereka "
            f"secara peribadi (Slack/WhatsApp/dsb) — ia hanya dipaparkan sekali:"
        )
        st.code(setup_msg["code"], language=None)
        st.caption(
            "Mereka log masuk di skrin log masuk → \"Akaun baharu? Tetapkan kata laluan pertama kali\", "
            "masukkan nama pengguna + kod ini, dan pilih kata laluan mereka sendiri."
        )

    udf = pd.DataFrame([
        {
            "Nama Pengguna": u["username"], "Nama": u["name"], "Peranan": S.ROLES[u["role"]],
            "Status": "⏳ Belum tetapkan kata laluan" if u.get("pending_setup") else "Aktif",
        }
        for u in STATE["users"]
    ])
    st.dataframe(udf, use_container_width=True, hide_index=True)

    with st.expander("➕ Tambah Pengguna Baharu"):
        password_mode = st.radio(
            "Kaedah kata laluan",
            options=["self", "admin"],
            format_func=lambda x: "Biarkan pengguna tetapkan kata laluan sendiri (kod persediaan)" if x == "self"
                                    else "Saya tetapkan kata laluan sekarang",
            key="new_user_pw_mode",
        )
        with st.form("add_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_username = st.text_input("Nama Pengguna (untuk log masuk, cth: emel)")
                new_name = st.text_input("Nama Penuh")
            with c2:
                new_password = None if password_mode == "self" else st.text_input("Kata Laluan", type="password")
                new_role = st.selectbox("Peranan", options=list(S.ROLES.keys()), format_func=lambda x: S.ROLES[x])
            submitted = st.form_submit_button("Cipta Pengguna")
            if submitted:
                uname = new_username.strip().lower()
                if not uname:
                    st.error("Nama pengguna diperlukan.")
                elif password_mode == "admin" and not new_password:
                    st.error("Nama pengguna dan kata laluan diperlukan.")
                elif any(u["username"].lower() == uname for u in STATE["users"]):
                    st.error("Nama pengguna sudah wujud.")
                else:
                    display_name = new_name.strip() or uname
                    if password_mode == "self":
                        code = S.create_pending_user(STATE, uname, display_name, new_role)
                        persist()
                        st.session_state["last_setup_code_msg"] = {"username": uname, "code": code}
                    else:
                        STATE["users"].append({
                            "id": S.uid("usr"), "username": uname, "name": display_name,
                            "role": new_role, "password": S.hash_password(new_password),
                            "pending_setup": False,
                        })
                        persist()
                    st.rerun()

    with st.expander("🔄 Jana Semula Kod Persediaan"):
        st.caption("Untuk akaun yang masih menunggu tetapan kata laluan, jika kod asal hilang/luput.")
        pending_users = [u for u in STATE["users"] if u.get("pending_setup")]
        if not pending_users:
            st.caption("Tiada akaun menunggu tetapan kata laluan.")
        else:
            pending_options = {u["id"]: f"{u['username']} ({S.ROLES[u['role']]})" for u in pending_users}
            pend_id = st.selectbox("Pengguna", options=list(pending_options.keys()), format_func=lambda x: pending_options[x], key="regen_code_target")
            if st.button("Jana Kod Baharu"):
                u = next(u for u in STATE["users"] if u["id"] == pend_id)
                new_code = S.regenerate_setup_code(u)
                persist()
                st.session_state["last_setup_code_msg"] = {"username": u["username"], "code": new_code}
                st.rerun()

    with st.expander("🔑 Set Semula Kata Laluan"):
        st.caption("Untuk akaun yang sudah aktif — ini menetapkan kata laluan baharu terus (bukan kod persediaan).")
        target_options = {u["id"]: f"{u['username']} ({S.ROLES[u['role']]})" for u in STATE["users"]}
        target_id = st.selectbox("Pengguna", options=list(target_options.keys()), format_func=lambda x: target_options[x], key="reset_pw_target")
        new_pw = st.text_input("Kata Laluan Baharu", type="password", key="reset_pw_value")
        if st.button("Set Semula Kata Laluan"):
            if not new_pw:
                st.error("Sila masukkan kata laluan baharu.")
            else:
                u = next(u for u in STATE["users"] if u["id"] == target_id)
                u["password"] = S.hash_password(new_pw)
                u["pending_setup"] = False
                u.pop("setup_code_hash", None)
                persist()
                st.success(f"Kata laluan untuk '{u['username']}' telah diset semula.")

    with st.expander("🗑 Padam Pengguna"):
        deletable = [u for u in STATE["users"] if u["id"] != CURRENT_USER["id"]]
        if not deletable:
            st.caption("Tiada pengguna lain untuk dipadam.")
        else:
            del_options = {u["id"]: f"{u['username']} ({S.ROLES[u['role']]})" for u in deletable}
            del_id = st.selectbox("Pengguna", options=list(del_options.keys()), format_func=lambda x: del_options[x], key="del_user_target")
            if st.button("Padam Pengguna Ini", type="secondary"):
                STATE["users"] = [u for u in STATE["users"] if u["id"] != del_id]
                persist()
                st.success("Pengguna telah dipadam.")
                st.rerun()


# ==========================================================================
# Kewangan — simplified, single-purpose page
# ==========================================================================

def render_kewangan_page():
    st.subheader("💰 Pengisian Harga (Kewangan)")
    st.caption("Pilih kategori dan penyebut harga, kemudian isi harga/unit bagi setiap item.")

    cats = S.leaf_categories(STATE)
    suppliers = STATE["suppliers"]
    if not cats or not suppliers:
        st.info("Belum ada kategori/penyebut harga lagi — hubungi Leader.")
        return

    c1, c2 = st.columns(2)
    with c1:
        cat_labels = {c["id"]: f"{S.category_full_number(STATE, c['id'])} {c['name']}" for c in cats}
        selected_cat = st.selectbox("Kategori", options=list(cat_labels.keys()), format_func=lambda x: cat_labels[x], key="kew_cat")
    with c2:
        sup_labels = {s["id"]: s["name"] for s in suppliers}
        selected_sup = st.selectbox("Penyebut Harga", options=list(sup_labels.keys()), format_func=lambda x: sup_labels[x], key="kew_sup")

    items = S.items_for_category(STATE, selected_cat)
    if not items:
        st.info("Tiada item dalam kategori ini.")
        return

    filled = sum(1 for it in items if (lambda b: b["unit_price"] is not None or b.get("price_text"))(S.get_bid(STATE, it["id"], selected_sup)))
    pcol, bcol = st.columns([5, 2])
    with pcol:
        st.progress(filled / len(items) if items else 0, text=f"{filled} daripada {len(items)} item telah diisi")
    with bcol:
        if filled and st.button("Kosongkan Harga Saya", key="btn_clear_kew", use_container_width=True):
            _clear_kewangan_dialog(cat_labels[selected_cat], selected_sup, sup_labels[selected_sup], items)

    qty_col = next((c for c in STATE["columns"] if c.get("tag") == "quantity"), None)
    catatan_col = next((c for c in STATE["columns"] if c.get("tag") == "catatan"), None)

    def _apply_price(it, v):
        up, ptext = S.parse_price_input(v)
        S.set_bid(STATE, it["id"], selected_sup, unit_price=up, price_text=ptext)

    render_fill_down(items, "Harga/Unit", _apply_price, key_prefix=f"kew_price_{selected_cat}_{selected_sup}", placeholder="cth: 100 atau TT")
    if catatan_col:
        render_fill_down(
            items, "Catatan",
            lambda it, v: S.set_field(it, catatan_col["id"], v),
            key_prefix=f"kew_catatan_{selected_cat}_{selected_sup}", placeholder="cth: Tiada bekalan",
        )

    rows = []
    for idx, it in enumerate(items):
        bid = S.get_bid(STATE, it["id"], selected_sup)
        rows.append({
            "id": it["id"], "Bil.": f"{idx+1}", "Perkara": it["perkara"],
            "Kuantiti": (S.get_field(it, qty_col["id"]) if qty_col else None),
            "Harga/Unit (RM)": S.price_display(bid),
            "Catatan": (S.get_field(it, catatan_col["id"]) or "") if catatan_col else "",
        })
    df = pd.DataFrame(rows)

    edited = st.data_editor(
        df, column_order=["Bil.", "Perkara", "Kuantiti", "Harga/Unit (RM)", "Catatan"],
        column_config={
            "Bil.": st.column_config.TextColumn("Bil.", width="small", disabled=True),
            "Perkara": st.column_config.TextColumn("Perkara", width="large", disabled=True),
            "Kuantiti": st.column_config.NumberColumn("Kuantiti", disabled=True, width="small"),
            "Harga/Unit (RM)": st.column_config.TextColumn("Harga/Unit (RM) — nombor atau teks (cth: TT)", width="medium"),
            "Catatan": st.column_config.TextColumn("Catatan (dikongsi dgn Teknikal)", width="large", disabled=not catatan_col),
        },
        use_container_width=True, hide_index=True, key=f"kew_editor_{selected_cat}_{selected_sup}",
    )

    if st.button("💾 Simpan Harga", key="save_kew"):
        for _, row in edited.iterrows():
            up, ptext = S.parse_price_input(row.get("Harga/Unit (RM)"))
            S.set_bid(STATE, row["id"], selected_sup, unit_price=up, price_text=ptext)
            if catatan_col:
                it = next((i for i in STATE["items"] if i["id"] == row["id"]), None)
                if it is not None:
                    S.set_field(it, catatan_col["id"], row.get("Catatan") or "")
        rerun()


# ==========================================================================
# Teknikal — simplified, single-purpose page
# ==========================================================================

def render_technical_page():
    st.subheader("🔧 Penilaian Piawaian (Teknikal)")
    st.caption("Pilih kategori dan penyebut harga, kemudian tandakan status pematuhan piawaian + catatan.")

    cats = S.leaf_categories(STATE)
    suppliers = STATE["suppliers"]
    if not cats or not suppliers:
        st.info("Belum ada kategori/penyebut harga lagi — hubungi Leader.")
        return

    c1, c2 = st.columns(2)
    with c1:
        cat_labels = {c["id"]: f"{S.category_full_number(STATE, c['id'])} {c['name']}" for c in cats}
        selected_cat = st.selectbox("Kategori", options=list(cat_labels.keys()), format_func=lambda x: cat_labels[x], key="tek_cat")
    with c2:
        sup_labels = {s["id"]: s["name"] for s in suppliers}
        selected_sup = st.selectbox("Penyebut Harga", options=list(sup_labels.keys()), format_func=lambda x: sup_labels[x], key="tek_sup")

    items = S.items_for_category(STATE, selected_cat)
    if not items:
        st.info("Tiada item dalam kategori ini.")
        return

    filled = sum(1 for it in items if S.get_bid(STATE, it["id"], selected_sup)["status"])
    pcol, bcol = st.columns([5, 2])
    with pcol:
        st.progress(filled / len(items) if items else 0, text=f"{filled} daripada {len(items)} item telah dinilai")
    with bcol:
        if filled and st.button("Kosongkan Penilaian Saya", key="btn_clear_tek", use_container_width=True):
            _clear_teknikal_dialog(cat_labels[selected_cat], selected_sup, sup_labels[selected_sup], items)

    statuses = STATE["supplier_matrix"]["statuses"]
    status_hint = " / ".join(s["id"] for s in statuses)
    catatan_col = next((c for c in STATE["columns"] if c.get("tag") == "catatan"), None)

    render_fill_down(
        items, "Status", lambda it, v: S.set_bid(STATE, it["id"], selected_sup, status=v),
        key_prefix=f"tek_status_{selected_cat}_{selected_sup}", placeholder=f"cth: {status_hint}",
    )
    if catatan_col:
        render_fill_down(
            items, "Catatan",
            lambda it, v: S.set_field(it, catatan_col["id"], v),
            key_prefix=f"tek_catatan_{selected_cat}_{selected_sup}", placeholder="cth: Tidak berkenaan",
        )

    rows = []
    for idx, it in enumerate(items):
        bid = S.get_bid(STATE, it["id"], selected_sup)
        rows.append({
            "id": it["id"], "Bil.": f"{idx+1}", "Perkara": it["perkara"],
            "Status": bid.get("status") or "",
            "Catatan": (S.get_field(it, catatan_col["id"]) or "") if catatan_col else "",
        })
    df = pd.DataFrame(rows)

    edited = st.data_editor(
        df, column_order=["Bil.", "Perkara", "Status", "Catatan"],
        column_config={
            "Bil.": st.column_config.TextColumn("Bil.", width="small", disabled=True),
            "Perkara": st.column_config.TextColumn("Perkara", width="large", disabled=True),
            "Status": st.column_config.TextColumn(f"Status ({status_hint}, atau teks lain)", width="small"),
            "Catatan": st.column_config.TextColumn("Catatan (dikongsi dgn Kewangan)", width="large", disabled=not catatan_col),
        },
        use_container_width=True, hide_index=True, key=f"tek_editor_{selected_cat}_{selected_sup}",
    )

    if st.button("💾 Simpan Penilaian", key="save_tek"):
        for _, row in edited.iterrows():
            S.set_bid(STATE, row["id"], selected_sup, status=row.get("Status") or "")
            if catatan_col:
                it = next((i for i in STATE["items"] if i["id"] == row["id"]), None)
                if it is not None:
                    S.set_field(it, catatan_col["id"], row.get("Catatan") or "")
        rerun()


# ==========================================================================
# Role dispatch
# ==========================================================================

if ROLE == "kewangan":
    header_bar(editable_meta=False)
    render_kewangan_page()

elif ROLE == "technical":
    header_bar(editable_meta=False)
    render_technical_page()

elif ROLE == "leader":
    pages = ["Kategori", "Lajur", "Item", "Penyebut Harga", "Matriks Tawaran", "Semakan", "Laporan", "Notifikasi"]
    header_bar(editable_meta=True, pages=pages)
    active = st.session_state.get("active_page", pages[0])
    if active == "Kategori": render_categories_tab(editable=True)
    elif active == "Lajur": render_columns_tab(editable=True)
    elif active == "Item": render_items_tab(editable=True)
    elif active == "Penyebut Harga": render_suppliers_tab(editable=True)
    elif active == "Matriks Tawaran": render_full_bids_matrix_tab(editable=True)
    elif active == "Semakan": render_tally_tab()
    elif active == "Laporan": render_report_tab()
    elif active == "Notifikasi": render_notifications_tab()

elif ROLE == "admin":
    pages = ["Pengguna", "Kategori", "Lajur", "Item", "Penyebut Harga",
             "Matriks Tawaran", "Semakan", "Laporan", "Notifikasi"]
    header_bar(editable_meta=True, pages=pages)
    active = st.session_state.get("active_page", pages[0])
    if active == "Pengguna": render_user_management_tab()
    elif active == "Kategori": render_categories_tab(editable=admin_gate("categories", "Kategori"))
    elif active == "Lajur": render_columns_tab(editable=admin_gate("columns", "Lajur"))
    elif active == "Item": render_items_tab(editable=admin_gate("items", "Item"))
    elif active == "Penyebut Harga": render_suppliers_tab(editable=admin_gate("suppliers", "Penyebut Harga"))
    elif active == "Matriks Tawaran": render_full_bids_matrix_tab(editable=admin_gate("bids", "Matriks Tawaran"))
    elif active == "Semakan": render_tally_tab()
    elif active == "Laporan": render_report_tab()
    elif active == "Notifikasi": render_notifications_tab()
