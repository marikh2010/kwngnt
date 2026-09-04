# Kertas Taklimat — Sistem Penilaian Sebut Harga (Streamlit, 4 Peranan)

A Streamlit app for running a full tender evaluation with **separated Kewangan and
Teknikal data entry**, a **Leader** who owns the report structure and reconciles both
sides, and an **Admin** who manages accounts. Nothing about the report's shape is
hardcoded — categories, items, suppliers, and the columns themselves are all data the
Leader (or Admin, with notification) edits through the app.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Data is saved to `kertas_taklimat_data.json` next to
`app.py` — this includes user accounts, so back it up carefully (see Security note below).

## Default accounts

The app seeds four accounts on first run. **Change these passwords immediately** via
the Admin's "Pengurusan Pengguna" tab once you're set up.

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin |
| `leader` | `leader123` | Ketua Pasukan (Leader) |
| `kewangan` | `kewangan123` | Kewangan |
| `teknikal` | `teknikal123` | Teknikal |

## The four roles

### Kewangan
One simple screen: pick a **category**, pick a **supplier**, and a short list of items
appears with just a price field per item — no scrolling through unrelated columns.
Cannot see Teknikal's status/remarks, and cannot see or edit categories, items,
columns, or suppliers (that's the Leader's job).

### Teknikal
Same shape as Kewangan, but for compliance: pick a category and supplier, then mark
each item's status (e.g. M / TM / TT — fully configurable) plus a remark explaining
why. Cannot see Kewangan's prices.

### Leader (Ketua Pasukan)
Owns the structure: Kategori, Lajur (columns), Item, Penyebut Harga (suppliers), and
the tender/evaluation dates. Also has:
- **Matriks Tawaran** — the full merged grid (both price and status) for a top-down view.
- **Semakan** — a tally check: for every item × supplier pair, whether *both* Kewangan
  and Teknikal have filled in their side, with a list of specific mismatches (one side
  done, the other not).
- **Laporan** — the merged final-report preview, with three separate download buttons:
  full report, Kewangan-only, or Teknikal-only. Every export ends with four
  summary rows pulled straight from the original template: **HARGA ANGGARAN
  JABATAN**, **HARGA TAWARAN DARI PENYEBUT HARGA** (per supplier), **HARGA
  YANG DICADANGKAN** (per supplier, based on each item's Kewangan (K) pick),
  and **JUMLAH KESELURUHAN PEROLEHAN**.
- **Notifikasi** — sees when Admin has requested/made edits.

### Admin
Sees every tab, including **Pengurusan Pengguna** (create accounts, assign roles, reset
passwords, delete users — this is Admin's exclusive job, not gated). All the
*content*-editing tabs (Kategori, Lajur, Item, Penyebut Harga, Matriks Tawaran, Data &
Import), however, open in **view-only** mode. To edit, Admin clicks "🔔 Saya ingin edit —
Maklumkan Leader", which immediately sends a notification to the Leader and unlocks
editing for the rest of that session.

## Which fields belong to which team

In the **Lajur** tab, any column marked "Boleh Edit dalam Matriks" gets a **Pasukan**
(team) setting:
- **Kewangan Sahaja** — only appears on the Kewangan page and in the Kewangan-only export.
- **Teknikal Sahaja** — only appears on the Teknikal page and in the Teknikal-only export.
- **Leader/Admin Sahaja** — a shared/decision field (e.g. final recommendation), edited
  only from the full Matriks Tawaran, and included in *every* export.

The supplier bid block itself is split automatically: unit price → Kewangan, status +
remark → Teknikal — this isn't configurable, since it's the core of the workflow.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit UI — login, role-based routing, all tabs/pages. |
| `state.py` | Data model, persistence, auth (salted-hash passwords), notifications, tally logic. No Streamlit dependency — testable on its own. |
| `report.py` | Builds the HTML preview and scoped `.xlsx` exports (full / kewangan / technical). |
| `seed_data.py` | Categories/items extracted from your original `masterlist.xlsx`. |
| `kertas_taklimat_data.json` | Created on first run — all data, including user accounts, lives here. |

## Branding: ISN logo

The top navbar uses the official ISN seal (`logo.png`), already bundled in this
folder — no setup needed. If you ever want to swap it for a different mark, just
replace `logo.png` (or drop in a `logo.jpg` / `logo.svg` instead) and restart the
app; it's picked up automatically.

## Security note (please read)

This is **lightweight, internal-tool-level** access control — appropriate for a
trusted local or office network, not a hardened public-facing system:
- Passwords are salted and hashed (not stored in plain text), but there's no
  brute-force lockout, no HTTPS enforcement, and no session expiry beyond what
  Streamlit itself provides.
- Role separation is enforced by what the app *renders* for each logged-in role — it
  is not a server-side per-request authorization boundary. Anyone with access to the
  underlying `kertas_taklimat_data.json` or the source code could bypass it.
- All roles share one JSON file. Two people saving at the exact same moment can
  overwrite each other (last write wins) — encourage saving in reasonably small,
  frequent steps rather than one big batch at the end.

If you need this hardened for a less-trusted environment (public internet, adversarial
users), that's a different scope — ask and we can talk through options (e.g. a proper
database with row-level locking, real session tokens, HTTPS).

## Example: reusing this for a completely different tender

1. Leader (or Admin, with notification) goes to **Lajur**, adjusts columns — e.g. swap
   "Unit" for "Jenama Dicadangkan" and "Tempoh Waranti" — and sets their **Pasukan** so
   the right team sees them.
2. Leader replaces the categories in **Kategori** and sets supplier count in
   **Penyebut Harga**.
3. Admin creates/updates accounts in **Pengurusan Pengguna** for the new evaluators.
4. Kewangan and Teknikal each just pick category + supplier and fill in their half —
   everything else (Semakan, Laporan, exports) follows automatically.
