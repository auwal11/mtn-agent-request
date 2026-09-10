import os
import smtplib
from email.message import EmailMessage

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_batch_pdfs(to_email, partner_name, batch_id, pdf_dir):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False, "GMAIL_ADDRESS / GMAIL_APP_PASSWORD are not configured on the server (environment variables)."

    pdf_files = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf"))
    if not pdf_files:
        return False, "No PDF files were found for this batch to send."

    msg = EmailMessage()
    msg["Subject"] = f"{partner_name} - Batch #{batch_id} - MTN Agent Onboarding Documents"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(
        f"Hello,\n\nPlease find the complete documents (PDF) for Batch #{batch_id} from {partner_name}.\n"
        f"{len(pdf_files)} file(s) attached to this email:\n- " + "\n- ".join(pdf_files) +
        "\n\nSent automatically by the MTN Agent Onboarding Dashboard."
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
        return True, f"Successfully sent {len(pdf_files)} PDF(s) to {to_email}."
    except Exception as e:
        return False, f"Failed to send email: {e}"
