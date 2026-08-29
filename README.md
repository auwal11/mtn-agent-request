# RACU International — MTN Agent Onboarding Dashboard

A complete dashboard system that manages agent data entry, stores it in batches,
and automatically generates all 7 required PDF forms + the NCC License into a
single downloadable ZIP package — with no manual editing involved.

## What's Inside

- **Flask web dashboard** (`app.py`) — set up the partner profile, add agents,
  review the current batch, generate and download packages.
- **Database** (SQLite, `database.py`) — stores partners, batches, and agents.
- **Generators** (`generators/`) — each form has its own module:
  - `form1_certificate.py` — Training Course Certificate (original background asset + vector text overlay)
  - `form2_authorisation.py` — Certificate of Authorisation
  - `form3_deduction.py` — Authorization for Deduction (₦5,000) + signature paste
  - `form4_idcard.py` — MTN Agent ID Card (built from scratch, includes agent photo)
  - `form5_agent_form.py` — SIM Registration Agent & Outlet Recruitment Form (3 pages; functional layout, visual calibration against the original still pending — see status table below)
  - `form6_form7_tables.py` — Approved Request & SSP Username Creation (table-style, built from scratch)
- **Batch engine** (`batch_engine.py`) — combines all 7 forms + the license PDF into one ZIP.

## Running Locally

```bash
cd mtn-agent-request
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000` in your browser.

## Workflow

1. **First visit** → you'll be redirected to `/partner/setup` — enter RACU
   International Ltd's details, upload the NCC License PDF, and upload the
   CEO/MD's signature image (Ibrahim Ahmad).
2. **Dashboard** (`/`) → shows the current draft batch (empty at first).
3. **Add Agent** → fill in the form (personal details, outlet, device, photo,
   signature pad). Each submission adds one agent to the draft batch.
4. Once the batch has **10 or more agents**, the **"Generate Package"** button
   becomes active.
5. Click Generate → the system builds Form1–Form7.pdf + Form8 (License) →
   packages them into a single ZIP → **download** directly from the dashboard.
6. After generating, the batch is marked "generated" (closed), and a new
   draft batch starts automatically for the next round.

## Form Completion Status (Fidelity)

| Form | Status | Notes |
|---|---|---|
| Form 1 — Training Certificate | Complete, tested | Uses the actual background asset from your original PDF |
| Form 2 — Certificate of Authorisation | Complete, tested | Same approach |
| Form 3 — Authorization for Deduction | Complete, tested | Includes signature capture from the dashboard |
| Form 4 — ID Card | Complete, tested | Built from scratch (clean layout) |
| Form 5 — SIM Reg Agent Form | Functional, layout not pixel-perfect yet | Needs the same measurement pass used for Forms 1-3 for an exact visual match |
| Form 6 — Approved Request | Complete | Table-style, built from scratch |
| Form 7 — SSP Username Creation | Complete | Table-style, built from scratch |
| Form 8 — NCC License | Complete | Upload-only, never modified |

## Deployment Notes (Persistent Storage)

This app stores data in a **SQLite database** + **uploaded files** (photos,
signatures) + **generated ZIPs** — all on disk. When deploying, make sure the
data folder lives on **persistent disk/volume** storage, not an ephemeral
filesystem (for example, Vercel's serverless platform will NOT work, since it
has no persistent storage).

The app is already set up to use a single environment variable:

```
DATA_DIR=/path/to/persistent/folder
```

If set, the database (`dashboard.db`), `uploads/`, and `outputs/` will all live
there instead of inside the project folder itself. If not set, they'll stay
inside the project folder (fine for local testing, but not suitable for
hosting platforms without persistent disk).

A `SECRET_KEY` environment variable is also required in production (for Flask
session security):

```
SECRET_KEY=<a long random string>
```

A `Procfile` is included for platforms like Render (`web: gunicorn app:app`).
`pythonanywhere_wsgi.py` and `render.yaml` are also included as ready-to-use
deployment configs — see the comments inside each file for setup steps.

## Recommended Next Steps

1. **Fine-tune Form 5**: apply the same method used for Forms 1-3 (pdftoppm to
   PNG, grid overlay, measure coordinates, blank the template, overlay text)
   so Form 5 matches the original exactly.
2. **Polish minor artifacts**: a few spots (e.g. a faint ghost of text on
   Form 2 behind "RACU INTERNATIONAL LTD") could use slightly wider erase
   boxes in `assets/form2_bg.png` — regenerate using the same measurement
   script described above.
3. **Authentication**: if more than one person will use the dashboard, add
   login/session support.
4. **Multi-partner support**: the database schema already supports more than
   one partner — a partner-selector UI would be needed if more than one is added.
5. **Deploy**: can be deployed to any VPS/cloud platform (Render, Fly.io,
   PythonAnywhere, DigitalOcean, or even an office PC that stays on).

## Tech Stack

- Python 3, Flask, SQLite
- ReportLab (PDF generation, vector text overlay)
- Pillow (image processing — ID card compositing)
- img2pdf (PNG to PDF for the ID card)
- SignaturePad.js (JS canvas signature capture on the dashboard)
