import os
import uuid
import base64
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session

import database as db
from batch_engine import generate_batch_package
from email_sender import send_batch_pdfs

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE)
UPLOADS = os.path.join(DATA_DIR, "uploads")
os.makedirs(os.path.join(UPLOADS, "photos"), exist_ok=True)
os.makedirs(os.path.join(UPLOADS, "signatures"), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")

MIN_BATCH_SIZE = 10

db.init_db()


@app.context_processor
def inject_identity():
    role = session.get("role")
    company_name = None
    if role in ("admin", "receiver_admin") and session.get("company_id"):
        company = db.get_partner(session["company_id"])
        if company:
            company_name = company["name"]
    return dict(role=role, current_user_name=session.get("name"),
                company_name=company_name or "Workspace")


# ---------------------------------------------------------------- helpers ----
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


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login", next=request.path))
            user = db.get_user(session["user_id"])
            if not user or user["status"] not in ("enabled", "active"):
                session.clear()
                flash("Your account access has been suspended. Contact the Root/CEO.", "error")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You don't have permission to access this page.", "error")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_public_token():
    if "public_token" not in session:
        session["public_token"] = uuid.uuid4().hex
    return session["public_token"]


def _forbid_cross_company(entity_company_id, redirect_endpoint):
    """Returns a redirect response (to abort the caller) if entity_company_id
    doesn't match the logged-in user's own company. Returns None if access is
    allowed. Every route that loads an agent or batch by a client-supplied ID
    must call this before doing anything else with it — see the SECURITY
    note in the module docstring / handoff report for why this was missing
    in the version this was merged from."""
    if entity_company_id is None or entity_company_id != session.get("company_id"):
        flash("You do not have permission to access that record.", "error")
        return redirect(url_for(redirect_endpoint))
    return None


@app.template_filter("basename")
def basename_filter(path):
    return os.path.basename(path) if path else ""


@app.route("/uploads-preview/<path:filename>")
@login_required()
def uploads_preview(filename):
    # SECURITY: filename comes from the URL and the <path:...> converter
    # allows slashes, so it must never be joined onto a filesystem path
    # unsanitized — a value like "../../app.py" or "../../.env" would
    # otherwise let any logged-in user read arbitrary files on the server
    # (path traversal). basename() strips any directory components, and the
    # realpath check below is defense-in-depth in case of symlink tricks.
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name != filename.split("/")[-1]:
        return "", 404
    for sub in ("photos", "signatures"):
        base_dir = os.path.realpath(os.path.join(UPLOADS, sub))
        candidate = os.path.realpath(os.path.join(base_dir, safe_name))
        if not candidate.startswith(base_dir + os.sep):
            continue
        if os.path.exists(candidate):
            return send_file(candidate)
    return "", 404


def agent_form_data(request, partner):
    """Builds the agent data dict shared by the public and admin/receiver add-agent forms."""
    photo_path = save_upload(request.files.get("photo"), "photos", "photo")
    signature_path = save_base64_signature(request.form.get("signature_data"), "signatures", "sig")
    return dict(
        surname=request.form["surname"].upper(),
        first_name=request.form["first_name"].upper(),
        other_name=request.form.get("other_name", "").upper(),
        nin=request.form["nin"],
        gender=request.form.get("gender", ""),
        qualification=request.form.get("qualification", "SSCE"),
        phone_number=request.form["phone_number"],
        momo_number=request.form.get("momo_number", ""),
        email=request.form.get("email", ""),
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


# ---------------------------------------------------------- public routes ----
@app.route("/")
def home():
    if session.get("role") == "root":
        return redirect(url_for("root_dashboard"))
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("role") == "receiver_admin":
        return redirect(url_for("receiver_dashboard"))

    token = get_public_token()
    my_agents = db.get_agents_by_session(token)
    return render_template("public_landing.html", my_agents=my_agents)


@app.route("/submit/start", methods=["POST"])
def submit_start():
    session["pending_partner_name"] = request.form.get("partner_name", "").strip()
    return redirect(url_for("submit_agent"))


@app.route("/submit", methods=["GET", "POST"])
def submit_agent():
    if not session.get("pending_partner_name"):
        return redirect(url_for("home"))

    partner = db.get_or_create_active_partner()
    if not partner:
        flash("No partner has been set up for this system yet. An Admin needs to set it up first.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        batch = db.get_or_create_draft_batch(partner["id"])
        data = agent_form_data(request, partner)
        data["status"] = "submitted"
        data["added_by"] = "public"
        data["session_token"] = get_public_token()
        data["submitted_partner_name"] = session.get("pending_partner_name", "")
        db.add_agent(batch["id"], data)
        flash(f"{data['first_name']} {data['surname']}'s details were received successfully!", "success")
        return redirect(url_for("submit_status"))

    return render_template("submit_agent.html", partner=partner,
                            partner_name=session.get("pending_partner_name"))


@app.route("/submit/status")
def submit_status():
    token = get_public_token()
    my_agents = db.get_agents_by_session(token)
    return render_template("submit_status.html", my_agents=my_agents)


# ----------------------------------------------------------------- login ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        user = db.find_user_by_password(password)
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            session["company_id"] = user["company_id"]
            db.touch_login(user["id"])
            db.log_action(user["name"], user["role"], "Logged in")
            if user["role"] == "root":
                return redirect(url_for("root_dashboard"))
            elif user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("receiver_dashboard"))
        else:
            flash("Incorrect password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if session.get("name"):
        db.log_action(session.get("name"), session.get("role"), "Logged out")
    session.clear()
    return redirect(url_for("home"))


# ----------------------------------------------------------- admin routes ----
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    partner = db.get_partner(session.get("company_id"))
    if not partner:
        return redirect(url_for("partner_setup"))
    batch = db.get_or_create_draft_batch(partner["id"])
    agents = db.get_batch_agents(batch["id"])
    all_batches = db.list_batches(partner["id"])
    return render_template("index.html", partner=partner, batch=batch, agents=agents,
                            min_batch_size=MIN_BATCH_SIZE, all_batches=all_batches, role="admin")


@app.route("/admin/partner/setup", methods=["GET", "POST"])
@login_required("admin")
def partner_setup():
    existing = db.get_partner(session.get("company_id"))
    if request.method == "POST":
        license_file = save_upload(request.files.get("ncc_license_file"), "photos", "license")
        ceo_sig = save_upload(request.files.get("ceo_signature_file"), "signatures", "ceo_sig")
        if existing:
            fields = dict(
                name=request.form["name"], dealer_code=request.form["dealer_code"],
                region=request.form.get("region", "NORTHEAST"), state=request.form.get("state", "TARABA"),
                lga=request.form.get("lga", "TAKUM"), address=request.form.get("address", ""),
                ncc_license_no=request.form.get("ncc_license_no", ""),
                stdm_name=request.form.get("stdm_name", ""), ceo_name=request.form.get("ceo_name", ""),
            )
            if license_file:
                fields["ncc_license_file"] = license_file
            if ceo_sig:
                fields["ceo_signature_file"] = ceo_sig
            db.update_partner(existing["id"], **fields)
            flash("Partner profile updated successfully!", "success")
        else:
            new_company = db.create_blank_company(request.form["name"])
            db.update_partner(new_company["id"],
                dealer_code=request.form["dealer_code"],
                region=request.form.get("region", "NORTHEAST"), state=request.form.get("state", "TARABA"),
                lga=request.form.get("lga", "TAKUM"), address=request.form.get("address", ""),
                ncc_license_no=request.form.get("ncc_license_no", ""), ncc_license_file=license_file,
                stdm_name=request.form.get("stdm_name", ""), ceo_name=request.form.get("ceo_name", ""),
                ceo_signature_file=ceo_sig,
            )
            session["company_id"] = new_company["id"]
            flash("Partner profile created successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("partner_setup.html", partner=existing)


@app.route("/admin/agent/add", methods=["GET", "POST"])
@login_required("admin")
def add_agent():
    partner = db.get_partner(session.get("company_id"))
    batch = db.get_or_create_draft_batch(partner["id"])
    if request.method == "POST":
        data = agent_form_data(request, partner)
        data["status"] = "confirmed"
        data["added_by"] = "admin"
        db.add_agent(batch["id"], data)
        flash(f"Agent {data['first_name']} {data['surname']} added to the batch!", "success")
        if request.form.get("action") == "add_another":
            return redirect(url_for("add_agent"))
        return redirect(url_for("admin_dashboard"))
    return render_template("add_agent.html", partner=partner, form_action=url_for("add_agent"),
                            cancel_url=url_for("admin_dashboard"))


@app.route("/admin/agent/<int:agent_id>", methods=["GET", "POST"])
@login_required("admin")
def agent_detail(agent_id):
    return _agent_detail_view(agent_id, "admin_dashboard")


@app.route("/admin/agent/<int:agent_id>/delete", methods=["POST"])
@login_required("admin")
def delete_agent(agent_id):
    guard = _forbid_cross_company(db.agent_company_id(agent_id), "admin_dashboard")
    if guard:
        return guard
    db.delete_agent(agent_id)
    flash("Agent removed from the batch.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/batch/<int:batch_id>/submit", methods=["POST"])
@login_required("admin")
def submit_batch_to_receiver(batch_id):
    partner = db.get_partner(session.get("company_id"))
    batch = db.get_batch(batch_id)
    guard = _forbid_cross_company(batch["partner_id"] if batch else None, "admin_dashboard")
    if guard:
        return guard
    agents = db.get_batch_agents(batch_id)

    if len(agents) < MIN_BATCH_SIZE:
        flash(f"You need at least {MIN_BATCH_SIZE} agents before you can submit a batch (currently: {len(agents)}).", "error")
        return redirect(url_for("admin_dashboard"))

    date_str = datetime.now().strftime("%d/%m/%Y")
    conn = db.get_conn()
    conn.execute("UPDATE batches SET date_authorized=? WHERE id=?", (date_str, batch_id))
    conn.commit()
    conn.close()
    batch = db.get_batch(batch_id)

    zip_path = generate_batch_package(partner, batch, agents)
    output_dir = os.path.join(os.path.dirname(zip_path), f"batch_{batch_id}")
    db.mark_batch_sent_to_receiver(batch_id, zip_path, output_dir)
    flash("Batch submitted to the Receiver Dashboard successfully!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/batch/<int:batch_id>/download")
@login_required("admin")
def download_batch(batch_id):
    batch = db.get_batch(batch_id)
    guard = _forbid_cross_company(batch["partner_id"] if batch else None, "admin_dashboard")
    if guard:
        return guard
    if not batch["output_zip"] or not os.path.exists(batch["output_zip"]):
        flash("File not found yet.", "error")
        return redirect(url_for("admin_dashboard"))
    return send_file(batch["output_zip"], as_attachment=True)


# -------------------------------------------------------- receiver routes ----
@app.route("/receiver")
@login_required("receiver_admin")
def receiver_dashboard():
    partner = db.get_partner(session.get("company_id"))
    batch = db.get_or_create_draft_batch(partner["id"]) if partner else None
    agents = db.get_batch_agents(batch["id"]) if batch else []
    incoming_batches = db.list_batches_for_receiver(session.get("company_id"))
    return render_template("receiver_dashboard.html", partner=partner, batch=batch, agents=agents,
                            min_batch_size=MIN_BATCH_SIZE, incoming_batches=incoming_batches, role="receiver_admin")


@app.route("/receiver/agent/add", methods=["GET", "POST"])
@login_required("receiver_admin")
def receiver_add_agent():
    partner = db.get_partner(session.get("company_id"))
    batch = db.get_or_create_draft_batch(partner["id"])
    if request.method == "POST":
        data = agent_form_data(request, partner)
        data["status"] = "confirmed"
        data["added_by"] = "receiver_admin"
        db.add_agent(batch["id"], data)
        flash(f"Agent {data['first_name']} {data['surname']} added to the batch!", "success")
        if request.form.get("action") == "add_another":
            return redirect(url_for("receiver_add_agent"))
        return redirect(url_for("receiver_dashboard"))
    return render_template("add_agent.html", partner=partner, form_action=url_for("receiver_add_agent"),
                            cancel_url=url_for("receiver_dashboard"))


@app.route("/receiver/agent/<int:agent_id>", methods=["GET", "POST"])
@login_required("receiver_admin")
def receiver_agent_detail(agent_id):
    return _agent_detail_view(agent_id, "receiver_dashboard")


@app.route("/receiver/agent/<int:agent_id>/delete", methods=["POST"])
@login_required("receiver_admin")
def receiver_delete_agent(agent_id):
    guard = _forbid_cross_company(db.agent_company_id(agent_id), "receiver_dashboard")
    if guard:
        return guard
    db.delete_agent(agent_id)
    flash("Agent removed from the batch.", "info")
    return redirect(url_for("receiver_dashboard"))


@app.route("/receiver/batch/<int:batch_id>/send_email", methods=["POST"])
@login_required("receiver_admin")
def receiver_send_email(batch_id):
    batch = db.get_batch(batch_id)
    guard = _forbid_cross_company(batch["partner_id"] if batch else None, "receiver_dashboard")
    if guard:
        return guard
    partner = db.get_partner(session.get("company_id"))
    to_email = request.form.get("to_email", "").strip()
    if not batch["output_dir"] or not os.path.exists(batch["output_dir"]):
        flash("Couldn't find the files for this batch.", "error")
        return redirect(url_for("receiver_dashboard"))
    if not to_email:
        flash("Please enter a recipient email address.", "error")
        return redirect(url_for("receiver_dashboard"))

    ok, message = send_batch_pdfs(to_email, partner["name"], batch_id, batch["output_dir"])
    if ok:
        db.mark_batch_emailed(batch_id, to_email)
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("receiver_dashboard"))


# -------------------------------------------------------------- root routes ----
@app.route("/root")
@login_required("root")
def root_dashboard():
    counts = db.system_counts()
    activity = db.recent_activity(15)
    admins = db.list_users("admin")
    receivers = db.list_users("receiver_admin")
    companies = db.list_companies()
    return render_template("root_dashboard.html", counts=counts, activity=activity,
                            admins=admins, receivers=receivers, companies=companies, role="root")


@app.route("/root/users/create", methods=["GET", "POST"])
@login_required("root")
def root_create_user():
    companies = db.list_companies()
    if request.method == "POST":
        name = request.form["name"].strip()
        role = request.form["role"]
        password = request.form.get("password", "").strip()
        new_company_name = request.form.get("new_company_name", "").strip()
        company_id = request.form.get("company_id") or None

        if new_company_name:
            company = db.create_blank_company(new_company_name)
            company_id = company["id"]

        if not company_id:
            flash("Please choose or create a company for this account.", "error")
            return redirect(url_for("root_create_user"))

        if not password:
            password = uuid.uuid4().hex[:10]

        db.create_user(name, password, role, company_id, status="enabled")
        db.log_action(session.get("name"), "root", f"Created {role} account for {name}")
        flash(f"Account for {name} created successfully. Password: {password} (write it down or send it to them now — it won't be shown again).", "success")
        return redirect(url_for("root_dashboard"))

    return render_template("root_create_user.html", companies=companies)


@app.route("/root/users/<int:user_id>/status", methods=["POST"])
@login_required("root")
def root_set_user_status(user_id):
    new_status = request.form.get("status")
    if new_status not in ("enabled", "active", "disabled", "revoked"):
        flash("invalid status.", "error")
        return redirect(url_for("root_dashboard"))
    target = db.get_user(user_id)
    if not target:
        flash("Couldn't find that user.", "error")
        return redirect(url_for("root_dashboard"))
    db.set_user_status(user_id, new_status)
    db.log_action(session.get("name"), "root", f"Set {target['name']}'s status to {new_status}")
    flash(f"{target['name']}'s status has been updated to {new_status}.", "success")
    return redirect(url_for("root_dashboard"))


# ---------------------------------------------------------- shared helper ----
def _agent_detail_view(agent_id, back_endpoint):
    agent = db.get_agent(agent_id)
    if not agent:
        flash("Couldn't find that agent.", "error")
        return redirect(url_for(back_endpoint))
    guard = _forbid_cross_company(db.agent_company_id(agent_id), back_endpoint)
    if guard:
        return guard

    if request.method == "POST":
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
            device_tag_id=request.form["device_tag_id"],
            device_imei=request.form.get("device_imei", ""),
            outlet_name=request.form.get("outlet_name", ""),
            outlet_address=request.form.get("outlet_address", ""),
            outlet_type=request.form.get("outlet_type", "CCR OUTLET"),
            lga=request.form.get("lga", ""),
            territory=request.form.get("territory", ""),
            cluster=request.form.get("cluster", ""),
            state=request.form.get("state", ""),
            latitude=request.form.get("latitude", ""),
            longitude=request.form.get("longitude", ""),
            ncc_region=request.form.get("ncc_region", ""),
        )
        new_photo = save_upload(request.files.get("photo"), "photos", "photo")
        if new_photo:
            data["photo_path"] = new_photo
        new_sig = save_base64_signature(request.form.get("signature_data"), "signatures", "sig")
        if new_sig:
            data["signature_path"] = new_sig
        db.update_agent(agent_id, data)
        flash("Agent info updated.", "success")
        return redirect(url_for(back_endpoint))

    if agent["status"] == "submitted":
        db.set_agent_status(agent_id, "in_review")
        agent = db.get_agent(agent_id)

    return render_template("agent_detail.html", agent=agent, back_endpoint=back_endpoint)


if __name__ == "__main__":
    # SECURITY: debug mode must never be hardcoded True — Flask's debug
    # mode exposes the interactive Werkzeug debugger, which allows
    # arbitrary code execution from the browser if it's ever reachable in
    # a real deployment. Defaults to off; opt in explicitly for local
    # testing with FLASK_DEBUG=1.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode, use_reloader=False)
