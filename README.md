# RACU International — MTN Agent Onboarding Dashboard

Cikakken tsari na dashboard wanda ke sarrafa saka bayanan agent, adana su a batch,
sannan ya ƙirƙiri duk fayilolin PDF guda 7 + NCC License a matsayin ZIP guda ɗaya —
kai tsaye ba tare da editing na hannu ba.

## Menene ke ciki

- **Flask web dashboard** (`app.py`) — saka partner, ƙara agents, duba batch, generate & download.
- **Database** (SQLite, `database.py`) — ajiye partners, batches, da agents.
- **Generators** (`generators/`) — kowanne form yana da nasa module:
  - `form1_certificate.py` — Training Course Certificate (background-asset + vector text overlay)
  - `form2_authorisation.py` — Certificate of Authorisation
  - `form3_deduction.py` — Authorization for Deduction (₦5,000) + signature paste
  - `form4_idcard.py` — MTN Agent ID Card (an gina daga sifili, tare da hoto)
  - `form5_agent_form.py` — SIM Registration Agent & Outlet Recruitment Form (3-shafuka; layout na farko, ana buƙatar ƙarin daidaita coordinates kamar Form 1-3)
  - `form6_form7_tables.py` — Approved Request & SSP Username Creation (table-style, an gina daga sifili)
- **Batch engine** (`batch_engine.py`) — ya haɗa duk 7 forms + license PDF zuwa ZIP guda ɗaya.

## Yadda za a Gudanar (Run Locally)

```bash
cd mtn_dashboard
pip install -r requirements.txt

# idan Poppins font babu a kwamfutarka, sauke ta ko canza FONT_PATH
# a cikin generators/*.py zuwa wani bold sans-serif font da kake da shi

python app.py
```

Sannan buɗe `http://localhost:5000` a browser.

## Workflow

1. **Buɗewa ta farko** → za a kai ka `/partner/setup` — saka bayanan RACU International Ltd,
   loda NCC License PDF, da hoton sa hannun CEO/MD (Ibrahim Ahmad).
2. **Dashboard** (`/`) → za ka ga batch draft na yanzu (fanko a farko).
3. **+ Ƙara Sabon Agent** → cika form (bayanan sirri, outlet, device, hoto, sa hannu ta pad).
   Kowane submission yana ƙara agent guda ɗaya zuwa batch ɗin draft.
4. Bayan agents sun kai **10 ko sama**, button ɗin **"Generate Package"** zai kunna.
5. Danna Generate → tsarin zai ƙirƙiri Form1-Form7.pdf + Form8 (License) → ya haɗa su cikin
   ZIP guda ɗaya → za ka iya **Download** kai tsaye daga dashboard.
6. Bayan an generate, batch ɗin zai zama "generated" (an rufe), sabon draft batch zai fara
   ta atomatik don sabon zagaye.

## Matsayin Kammala Kowane Form (Fidelity Status)

| Form | Matsayi | Bayani |
|---|---|---|
| Form 1 — Training Certificate | ✅ An kammala, an gwada | Yana amfani da ainihin background asset daga PDF ɗinka na asali |
| Form 2 — Certificate of Authorisation | ✅ An kammala, an gwada | Haka nan |
| Form 3 — Authorization for Deduction | ✅ An kammala, an gwada | Tare da signature capture daga dashboard |
| Form 4 — ID Card | ✅ An kammala, an gwada | An gina daga sifili (design mai sauƙi) |
| Form 5 — SIM Reg Agent Form | ⚠️ Aiki, amma layout ba pixel-perfect ba tukuna | Ana buƙatar maimaita hanyar Form1-3 (measure coordinates daga asali) domin cikakken kamanni |
| Form 6 — Approved Request | ✅ An kammala | Table-style, an gina daga sifili |
| Form 7 — SSP Username Creation | ✅ An kammala | Table-style, an gina daga sifili |
| Form 8 — NCC License | ✅ An kammala | Upload-only, ba a taɓawa |

## Deployment Notes (Persistent Storage)

Wannan app tana ajiye bayanai a **SQLite database** + **uploaded files** (photos,
signatures) + **generated ZIPs** — duk a disk. Idan za a yi deploy, dole a tabbatar
folder ɗin data yana kan **persistent disk/volume**, ba wani ephemeral filesystem ba
(misali Vercel serverless BA zai yi aiki ba domin babu persistent storage).

An riga an shirya app ɗin ta yadda za ka iya saita environment variable guda ɗaya:

```
DATA_DIR=/path/to/persistent/folder
```

Idan an saita wannan, database (`dashboard.db`), `uploads/`, da `outputs/` duk za su
tafi wurin nan maimakon cikin project folder ɗin kansa. Idan ba a saita ba, za su
zauna cikin project folder (yayi aiki don gwaji na gida, amma bazai dace da hosting
platforms marasa persistent disk ba).

Ana buƙatar `SECRET_KEY` environment variable a production (Flask session security):
```
SECRET_KEY=<wani dogon random string>
```

`Procfile` ya riga ya kasance don platforms irin Render (`web: gunicorn app:app`).

## Matakai na Gaba (Recommended Next Steps)

1. **Fine-tune Form 5**: yi amfani da hanyar da aka yi don Form 1-3 (pdftoppm → grid overlay →
   auna coordinates → blank template → overlay text) domin Form 5 ta yi daidai da asali 100%.
2. **Fine-tune ƙananan matsaloli**: akwai ƴan wurare (misali ƙaramin ghost-text a Form 2 bayan
   "RACU INTERNATIONAL LTD") waɗanda za su iya samun ƙarin gyara ta hanyar faɗaɗa erase-boxes
   kaɗan a cikin `assets/form2_bg.png` (za a iya sake ƙirƙira ta amfani da script a cikin
   POC folder da aka riga aka gina).
3. **Authentication**: idan fiye da mutum ɗaya zai yi amfani da dashboard, ƙara login/sessions.
4. **Multi-partner support**: database schema ya riga ya tallafawa fiye da partner ɗaya —
   ana buƙatar UI don zaɓar partner idan an ƙara fiye da ɗaya.
5. **Deploy**: ana iya turawa zuwa kowane VPS/cloud (Render, Railway, DigitalOcean, ko dai
   kwamfutar ofis idan koyaushe kunne take).

## Fasaha da aka Yi Amfani da Ita

- Python 3, Flask, SQLite
- ReportLab (PDF generation, vector text overlay)
- Pillow (image processing — ID card compositing)
- img2pdf (PNG→PDF don ID card)
- SignaturePad.js (JS canvas signature capture a dashboard)
