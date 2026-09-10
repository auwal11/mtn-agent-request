# MTN Agent Onboarding Dashboard (multi-tenant, v2)

A complete dashboard system that manages MTN SIM-registration agent onboarding:
public agents submit their own details, Admins review and batch them, generated
PDF packages (Form1–Form8) get handed to a Receiver Admin who emails them out —
all under a Root/CEO account that can create and manage any number of companies,
Admins, and Receiver Admins.

## Roles (3-tier + public)

```
👑 ROOT / CEO   (one account, full system control)
      │
 ┌────┴─────┐
 ▼          ▼
ADMIN   RECEIVER ADMIN   (one per company, created by Root)
      │
      ▼
 PUBLIC AGENT  (no login — submits their own info, tracked by browser session)
```

- **Root / CEO** — logs in with the Root password (see Environment Variables).
  From the Command Center (`/root`) they can create Admin/Receiver Admin
  accounts (choosing or creating the company each belongs to), Enable /
  Disable / Revoke / Reactivate any account (disabling force-logs-out that
  user on their next request), and see a system-wide overview + activity log.
- **Admin** — manages their company's partner profile (`/admin/partner/setup`,
  one-time setup: dealer code, NCC license, CEO/MD signature, STDM name),
  reviews/edits every agent (`/admin/agent/<id>` — opening it moves status
  `submitted → in_review`), and once a batch has 10+ agents, clicks
  **Submit to Receiver** — this generates Form1–Form8 as individual PDFs
  (not zipped) plus an archive ZIP, and moves the batch to the Receiver
  Admin's queue.
- **Receiver Admin** — sees batches submitted by their company's Admin, and
  for each one can type a recipient email and click **Send to Gmail**, which
  emails all 8 PDFs as attachments via Gmail SMTP. Also has full add/view/edit
  agent access, same as Admin.
- **Public agent** — no login at all. Lands on `/`, types their
  Partner/Company name, fills in the agent form, and can come back anytime to
  `/submit/status` (tracked via a browser session cookie) to see their status:
  `submitted → in_review → confirmed` ("user creation is preparing soon").

## What's Inside

- **`app.py`** — all routes: public submission flow, login, Root/Admin/Receiver
  dashboards.
- **`database.py`** — SQLite: `partners` (= companies), `batches`, `agents`,
  `users` (Root/Admin/Receiver accounts, password-hashed), `audit_log`.
- **`email_sender.py`** — Gmail SMTP sender used by the Receiver Admin's
  "Send to Gmail" button.
- **`generators/`** — one module per PDF form (Form1–Form7; Form8 is the
  uploaded NCC License, attached unchanged):
  - `form1_certificate.py` — Training Course Certificate
  - `form2_authorisation.py` — Certificate of Authorisation
  - `form3_deduction.py` — Authorization for Deduction (₦5,000) — labels and
    values are drawn with measured font-metric spacing so they never collide
  - `form4_idcard.py` — MTN Agent ID Card (built from scratch, includes photo)
  - `form5_agent_form.py` — SIM Registration Agent & Outlet Recruitment Form
  - `form6_form7_tables.py` — Approved Request & SSP Username Creation
- **`batch_engine.py`** — combines all 8 forms into `outputs/batch_<id>/` (for
  the Receiver's email) and a ZIP archive (for the Admin's own download).

## Running Locally

```bash
cd mtn-agent-request
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`. On first run a Root/CEO account is created
automatically (see Environment Variables below for the password) — log in at
`/login` and go to **Command Center → Create Admin/Receiver** to set up your
first company.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session signing — set a long random string in production | dev fallback |
| `ROOT_NAME` | Display name of the Root/CEO account | `Auwal` |
| `ROOT_PASSWORD` | Root/CEO login password (seeded once on first run — changing it later requires editing the `users` table directly) | `AuwalControl` |
| `GMAIL_ADDRESS` | Gmail address used to send batch PDFs | *(empty — Send to Gmail will show a clear error until set)* |
| `GMAIL_APP_PASSWORD` | A Gmail **App Password** (not your normal password — generate one at https://myaccount.google.com/apppasswords) | *(empty)* |
| `DATA_DIR` | Folder for `dashboard.db`, `uploads/`, `outputs/` — point this at persistent disk in production | project folder |

## Fixes in this version (v2)

- **Form 5**: removed the "KYC Username" field (MTN generates that themselves)
  — replaced with Email Address; removed the "CEO/MD Full Name" text line
  (the CEO/MD signature image is kept).
- **Form 3**: labels were being cut off in the original scanned background
  (`First N`, `Surr`, `Device`, …), causing values to visually collide with
  them. Labels are now redrawn in full with measured spacing before each value.
- **Form 1**: background was slightly dark — brightened for clearer text.
- **Form 2**: removed a baked-in "ghost" duplicate of the partner name that
  was printed directly under the dynamic overlay text.
- **Flask reloader bug**: the dev server's auto-reloader was watching the
  `outputs/` folder and restarting mid-request every time a batch was
  generated — disabled (`use_reloader=False`) since it's not needed with
  `debug=True` for manual testing.

## Known Limitation — multi-tenant text on Forms 1 & 2

Forms 1 and 2 reuse the *original scanned* background image, with only
specific fields (agent name, partner name, dates, etc.) drawn dynamically on
top. Two labels — the STDM name ("DAVID BUTU") and, in one spot, the partner
name — are still baked into that background image itself rather than pulled
from each company's own `stdm_name` / partner profile. This was fine for a
single company, but with multi-tenant support now added, every company will
currently see the same baked-in STDM name on Forms 1 & 2. Fixing this needs
the same erase-and-redraw treatment already applied to Form 3 (see
`generators/form3_deduction.py` for the pattern) applied to the STDM-name spot
in `assets/form1_bg.png` / `assets/form2_bg.png`.

## Deployment Notes (Persistent Storage)

This app stores data in **SQLite** + **uploaded files** (photos, signatures)
+ **generated PDFs/ZIPs** — all on disk. Point `DATA_DIR` at a persistent
disk/volume (not ephemeral storage — e.g. Vercel's serverless platform will
NOT work). A `Procfile` (Render/`gunicorn`), `render.yaml`, and
`pythonanywhere_wsgi.py` are included as ready-to-use deployment configs —
see the comments inside each file.

## Tech Stack

- Python 3, Flask, SQLite, Werkzeug (password hashing)
- ReportLab (PDF generation, vector text overlay)
- Pillow (image processing — ID card compositing, asset touch-ups)
- img2pdf (PNG to PDF for the ID card)
- smtplib / Gmail SMTP (Receiver Admin's "Send to Gmail")
- SignaturePad.js (JS canvas signature capture)
