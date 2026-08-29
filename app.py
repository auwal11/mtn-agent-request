import os
import base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash

import database as db
from batch_engine import generate_batch_package

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE)
UPLOADS = os.path.join(DATA_DIR, "uploads")
os.makedirs(os.path.join(UPLOADS, "photos"), exist_ok=True)
os.makedirs(os.path.join(UPLOADS, "signatures"), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")

MIN_BATCH_SIZE = 10

db.init_db()


def save_upload(file_storage, subfolder, prefix):
    if not file_storage or file_storage.filename == "":
        return None
    ext = os.path.splitext(file_storage.filename)[1] or ".png"
    fname = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
    path = os.path.join(UPLOADS, subfolder, fname)
    file_storage.save(path)
    return path


def save_base64_signature(data_url, subfolder, prefix):
    if not data_url or "," not in data_url:
        return None
    header, encoded = data_url.split(",", 1)
    fname = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
    path = os.path.join(UPLOADS, subfolder, fname)
    with open(path, "wb") as f:
        f.write(base64.b64decode(encoded))
    return path


@app.route("/")
def index():
    partner = db.get_or_create_active_partner()
    if not partner:
        return redirect(url_for("partner_setup"))
    batch = db.get_or_create_draft_batch(partner["id"])
    agents = db.get_batch_agents(batch["id"])
    all_batches = db.list_batches(partner["id"])
    return render_template("index.html", partner=partner, batch=batch, agents=agents,
                            min_batch_size=MIN_BATCH_SIZE, all_batches=all_batches)


@app.route("/partner/setup", methods=["GET", "POST"])
def partner_setup():
    if request.method == "POST":
        license_file = save_upload(request.files.get("ncc_license_file"), "photos", "license")
        ceo_sig = save_upload(request.files.get("ceo_signature_file"), "signatures", "ceo_sig")
        db.create_partner(
            name=request.form["name"],
            dealer_code=request.form["dealer_code"],
            region=request.form.get("region", "NORTHEAST"),
            state=request.form.get("state", "TARABA"),
            lga=request.form.get("lga", "TAKUM"),
            address=request.form.get("address", ""),
            ncc_license_no=request.form.get("ncc_license_no", ""),
            ncc_license_file=license_file,
            stdm_name=request.form.get("stdm_name", ""),
            ceo_name=request.form.get("ceo_name", ""),
            ceo_signature_file=ceo_sig,
        )
        flash("An samar da Partner cikin nasara!", "success")
        return redirect(url_for("index"))
    return render_template("partner_setup.html")


@app.route("/agent/add", methods=["GET", "POST"])
def add_agent():
    partner = db.get_or_create_active_partner()
    batch = db.get_or_create_draft_batch(partner["id"])
    if request.method == "POST":
        photo_path = save_upload(request.files.get("photo"), "photos", "photo")
        signature_path = save_base64_signature(request.form.get("signature_data"),
                                                "signatures", "sig")
        data = dict(
            surname=request.form["surname"].upper(),
            first_name=request.form["first_name"].upper(),
            other_name=request.form.get("other_name", "").upper(),
            nin=request.form["nin"],
            gender=request.form.get("gender", ""),
            qualification=request.form.get("qualification", "SSCE"),
            phone_number=request.form["phone_number"],
            momo_number=request.form.get("momo_number", ""),
            email=request.form.get("email", ""),
            kyc_username=request.form.get("kyc_username", ""),
            photo_path=photo_path,
            signature_path=signature_path,
            device_tag_id=request.form["device_tag_id"],
            device_imei=request.form.get("device_imei", ""),
            outlet_name=request.form.get("outlet_name", ""),
            outlet_address=request.form.get("outlet_address", ""),
            outlet_type=request.form.get("outlet_type", "CCR OUTLET"),
            lga=request.form.get("lga", partner["lga"]),
            territory=request.form.get("territory", ""),
            cluster=request.form.get("cluster", ""),
            state=request.form.get("state", partner["state"]),
            latitude=request.form.get("latitude", ""),
            longitude=request.form.get("longitude", ""),
            ncc_region=request.form.get("ncc_region", partner["region"]),
        )
        db.add_agent(batch["id"], data)
        flash(f"An ƙara {data['first_name']} {data['surname']} cikin batch!", "success")
        if request.form.get("action") == "add_another":
            return redirect(url_for("add_agent"))
        return redirect(url_for("index"))
    return render_template("add_agent.html", partner=partner)


@app.route("/agent/<int:agent_id>/delete", methods=["POST"])
def delete_agent(agent_id):
    db.delete_agent(agent_id)
    flash("An cire agent daga batch.", "info")
    return redirect(url_for("index"))


@app.route("/batch/<int:batch_id>/generate", methods=["POST"])
def generate_batch(batch_id):
    partner = db.get_or_create_active_partner()
    batch = db.get_batch(batch_id)
    agents = db.get_batch_agents(batch_id)

    if len(agents) < MIN_BATCH_SIZE:
        flash(f"Kana buƙatar akalla {MIN_BATCH_SIZE} agents kafin Generate (yanzu: {len(agents)}).", "error")
        return redirect(url_for("index"))

    date_str = datetime.now().strftime("%d/%m/%Y")
    conn = db.get_conn()
    conn.execute("UPDATE batches SET date_authorized=? WHERE id=?", (date_str, batch_id))
    conn.commit()
    conn.close()
    batch = db.get_batch(batch_id)

    zip_path = generate_batch_package(partner, batch, agents)
    db.mark_batch_generated(batch_id, zip_path)
    flash("An samar da cikakken package! Danna Download don samun ZIP.", "success")
    return redirect(url_for("index"))


@app.route("/batch/<int:batch_id>/download")
def download_batch(batch_id):
    batch = db.get_batch(batch_id)
    if not batch or not batch["output_zip"] or not os.path.exists(batch["output_zip"]):
        flash("Ba a samu fayil ba tukuna.", "error")
        return redirect(url_for("index"))
    return send_file(batch["output_zip"], as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
