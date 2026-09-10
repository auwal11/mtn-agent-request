import os
import smtplib
from email.message import EmailMessage

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_batch_pdfs(to_email, partner_name, batch_id, pdf_dir):
    """
    Sends every PDF file found in pdf_dir as individual attachments
    (not zipped) to to_email, using Gmail SMTP + an App Password.
    Returns (success: bool, message: str)
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False, "GMAIL_ADDRESS / GMAIL_APP_PASSWORD ba a saita su ba a sabis din (environment variables)."

    pdf_files = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf"))
    if not pdf_files:
        return False, "Ba a sami wani PDF a wannan batch din da za a aika ba."

    msg = EmailMessage()
    msg["Subject"] = f"{partner_name} - Batch #{batch_id} - MTN Agent Onboarding Documents"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(
        f"Sannu,\n\nGa cikakkun takardu (PDF) na Batch #{batch_id} daga {partner_name}.\n"
        f"Fayiloli {len(pdf_files)} da aka haɗa a wannan email:\n- " + "\n- ".join(pdf_files) +
        "\n\nAn turo ta atomatik daga RACU International MTN Agent Onboarding Dashboard."
    )

    for fname in pdf_files:
        fpath = os.path.join(pdf_dir, fname)
        with open(fpath, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=fname)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True, f"An turo PDF {len(pdf_files)} zuwa {to_email} cikin nasara."
    except Exception as e:
        return False, f"An kasa turo email: {e}"
