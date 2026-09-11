import os
import uuid
import time
import base64
import secrets
import threading
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, session
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import database as db
from batch_engine import generate_batch_package
from email_sender import send_batch_pdfs

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE)
UPLOADS = os.path.join(DATA_DIR, "uploads")
os.makedirs(os.path.join(UPLOADS, "photos"), exist_ok=True)
os.makedirs(os.path.join(UPLOADS, "signatures"), exist_ok=True)

app = Flask(__name__)
# SECURITY: never hardcode a usable secret. If SECRET_KEY is missing we generate
# an ephemeral one so the older default ("change-this-secret-key-in-production")
# can never be used to forge sessions. Sessions will reset every restart until a
# stable SECRET_KEY env var is configured.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
# Trust the proxy-inserted client IP / scheme headers (PythonAnywhere, Render).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# SECURITY: secure session cookies (HTTPS-only + SameSite=Lax). Override with
# SESSION_COOKIE_SECURE=0 only for local http testing.
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "1") == "1",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PREFERRED_URL_SCHEME="https",
)
# SECURITY: cap the whole request body (covers photo/signature uploads) and
# separately validate each uploaded file's type/size (see save_upload).
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB per request

# SECURITY: CSRF protection on every POST (must add {{ csrf_token() }} to forms).
# WTF_CSRF_SSL_STRICT is disabled because we set Referrer-Policy: no-referrer
# (a stricter default than the referrer-origin check), and it would otherwise
# reject every legitimate form submission from a browser. SameSite=Lax cookies
# plus the enforced HTTPS redirect cover the same anti-CSRF ground.
app.config.update(WTF_CSRF_SSL_STRICT=False)
csrf = CSRFProtect(app)

MIN_BATCH_SIZE = 10


# ------------------------------------------------------ request middleware ----
@app.before_request
def enforce_https():
    if app.config.get("SESSION_COOKIE_SECURE") and not request.is_secure:
        # Only enforce when the request actually came in over plain http.
        if request.environ.get("wsgi.url_scheme") != "https" and \
                request.headers.get("X-Forwarded-Proto") != "https":
            https_url = request.url.replace("http://", "https://", 1)
            code = 307 if request.method == "POST" else 301
            return redirect(https_url, code=code)


@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    if (request.path.startswith(("/admin", "/receiver", "/root", "/uploads-preview"))
            or request.endpoint in ("login",)):
        resp.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    return resp


@app.errorhandler(413)
def request_too_large(e):
    flash("File is too large (max 4 MB per request).", "error")
    referrer = request.referrer or url_for("home")
    return redirect(referrer)


db.init_db()


# ------------------------------------------------------- security helpers ----
def _client_ip():
    return getattr(request, "remote_addr", None) or "unknown"


# In-memory sliding rate limiter. PythonAnywhere serves a single app process,
# so this is safe here; document that multi-worker deploys need an external store.
_RL_LOCK = threading.Lock()
_RL_HITS = {}  # key -> list of monotonic timestamps


def _rate_limit(key, limit, window_seconds):
    now = time.monotonic()
    with _RL_LOCK:
        hits = [t for t in _RL_HITS.get(key, []) if now - t < window_seconds]
        if len(hits) >= limit:
            _RL_HITS[key] = hits
            return False
        hits.append(now)
        _RL_HITS[key] = hits
        return True


def _is_safe_staff_ip(remote_ip):
    return remote_ip in ("127.0.0.1", "::1")


ALLOWED_UPLOAD_EXT = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB per file


# ---------------------------------------------------------------- helpers ----
def save_upload(file_storage, subfolder, prefix, allow_pdf=False):
    if not file_storage or file_storage.filename == "":
        return None
    ext = (os.path.splitext(file_storage.filename)[1] or ".png").lower().lstrip(".")
    allowed = ALLOWED_UPLOAD_EXT if allow_pdf else (ALLOWED_UPLOAD_EXT - {"pdf"})
    if ext not in allowed:
        raise ValueError(f"File type .{ext} is not allowed.")
    data = file_storage.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File is too large (max {MAX_UPLOAD_BYTES // 1024} KB).")
    if ext == "pdf":
        if not data.startswith(b"%PDF"):
            raise ValueError("File is not a valid PDF.")
    else:
        try:
            from PIL import Image
            import io as _io
            Image.open(_io.BytesIO(data)).verify()
        except Exception:
            raise ValueError("File is not a valid image.")
    fname = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    path = os.path.join(UPLOADS, subfolder, fname)
    with open(path, "wb") as f:
        f.write(data)
    return path


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
def save_base64_signature(data_url, subfolder, prefix):
    if not data_url or "," not in data_url:
        return None
    header, encoded = data_url.split(",", 1)
    raw = base64.b64decode(encoded)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Signature image is too large.")
    fname = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
    path = os.path.join(UPLOADS, subfolder, fname)
    with open(path, "wb") as f:
        f.write(raw)
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
    # SECURITY: root sees everything (system-wide admin). Admin/Receiver must
    # only reach files that belong to their own company.
    role = session.get("role")
    company_id = session.get("company_id")
    if role != "root" and not db.file_owned_by_company(safe_name, company_id):
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
    if not _rate_limit(f"submit_start:{_client_ip()}", 60, 3600):
        flash("Too many submission sessions from this device. Please try again later.", "error")
        return redirect(url_for("home"))
    session["pending_partner_name"] = request.form.get("partner_name", "").strip()
    return redirect(url_for("submit_agent"))


@app.route("/submit", methods=["GET", "POST"])
def submit_agent():
    if not session.get("pending_partner_name"):
        return redirect(url_for("home"))
    if request.method == "POST" and not _rate_limit(f"submit:{_client_ip()}", 30, 3600):
        flash("Too many agent submissions from this device. Please try again later.", "error")
        return redirect(url_for("submit_status"))

    # SECURITY: resolve the company from the name the user typed instead of
    # always routing public submissions to the first partner in the database.
    partner = db.find_partner_by_name(session.get("pending_partner_name"))
    if not partner:
        flash("We couldn't find that partner/company. Please check the name or contact your Admin.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        try:
            data = agent_form_data(request, partner)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("submit_agent.html", partner=partner,
                                    partner_name=session.get("pending_partner_name"))
        batch = db.get_or_create_draft_batch(partner["id"])
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
        ip = _client_ip()
        if not _rate_limit(f"login:{ip}", 10, 900):
            flash("Too many login attempts. Please wait 15 minutes and try again.", "error")
            return render_template("login.html")
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
        try:
            license_file = save_upload(request.files.get("ncc_license_file"), "photos", "license", allow_pdf=True)
            ceo_sig = save_upload(request.files.get("ceo_signature_file"), "signatures", "ceo_sig")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("partner_setup.html", partner=existing)
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
        try:
            data = agent_form_data(request, partner)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("add_agent.html", partner=partner, form_action=url_for("add_agent"),
                                    cancel_url=url_for("admin_dashboard"))
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

@app.route("/admin/batch/<int:batch_id>")
@login_required("admin")
def batch_detail(batch_id):
    batch = db.get_batch(batch_id)
    guard = _forbid_cross_company(batch["partner_id"] if batch else None, "admin_dashboard")
    if guard:
        return guard
    agents = db.get_batch_agents(batch_id)
    return render_template("batch_detail.html", batch=batch, agents=agents,
                            min_batch_size=MIN_BATCH_SIZE)


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
        try:
            data = agent_form_data(request, partner)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("add_agent.html", partner=partner, form_action=url_for("receiver_add_agent"),
                                    cancel_url=url_for("receiver_dashboard"))
        data["status"] = "confirmed"
        data["added_by"] = "receiver_admin"
        db.add_agent(batch["id"], data)
        flash(f"Agent {data['first_name']} {data['surname']} added to the batch!", "success")
        if request.form.get("action") == "add_another":
            return redirect(url_for("receiver_add_agent"))
        return redirect(url_for("receiver_dashboard"))
    return render_template("add_agent.html", partner=partner, form_action=url_for("receiver_add_agent"),
                            cancel_url=url_for("receiver_dashboard"))


@app.route("/receiver/batch/<int:batch_id>")
@login_required("receiver_admin")
def receiver_batch_detail(batch_id):
    batch = db.get_batch(batch_id)
    guard = _forbid_cross_company(batch["partner_id"] if batch else None, "receiver_dashboard")
    if guard:
        return guard
    if not batch:
        flash("Couldn't find that batch.", "error")
        return redirect(url_for("receiver_dashboard"))
    agents = db.get_batch_agents(batch_id)
    partner = db.get_partner(batch["partner_id"])
    return render_template("receiver_batch_detail.html", batch=batch, agents=agents,
                            partner=partner, min_batch_size=MIN_BATCH_SIZE)


@app.route("/receiver/agent/<int:agent_id>")
@login_required("receiver_admin")
def receiver_agent_detail(agent_id):
    agent = db.get_agent(agent_id)
    if not agent:
        flash("Couldn't find that candidate.", "error")
        return redirect(url_for("receiver_dashboard"))
    guard = _forbid_cross_company(db.agent_company_id(agent_id), "receiver_dashboard")
    if guard:
        return guard
    batch = db.get_batch(agent["batch_id"])
    if not batch:
        flash("Couldn't find the batch for this candidate.", "error")
        return redirect(url_for("receiver_dashboard"))
    agents = db.get_batch_agents(batch["id"])
    idx = 0
    for i, a in enumerate(agents):
        if a["id"] == agent_id:
            idx = i
            break
    prev_agent = agents[idx - 1]["id"] if idx > 0 else None
    next_agent = agents[idx + 1]["id"] if idx < len(agents) - 1 else None
    partner = db.get_partner(batch["partner_id"])
    return render_template("receiver_agent_detail.html", agent=agent, batch=batch,
                            partner=partner, prev_agent=prev_agent, next_agent=next_agent,
                            position=idx + 1, total=len(agents))


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
    received_batches = []
    for b in db.list_batches_for_receiver(None):
        item = dict(b)
        partner = db.get_partner(b["partner_id"])
        item["company_name"] = partner["name"] if partner else f"Partner #{b['partner_id']}"
        received_batches.append(item)
    return render_template("root_dashboard.html", counts=counts, activity=activity,
                            admins=admins, receivers=receivers, companies=companies,
                            received_batches=received_batches, role="root")


@app.route("/root/system/reset", methods=["POST"])
@login_required("root")
def root_system_reset():
    # SECURITY: Root-only route. Reverses Admin⇄Receiver activity silently —
    # no email/notification is sent to either side; the reset is logged to the
    # internal audit trail (visible only on the Root dashboard).
    batch_id = request.form.get("batch_id", type=int)
    action = request.form.get("action", "")
    batch = db.get_batch(batch_id) if batch_id else None
    if not batch or batch["status"] != "sent_to_receiver":
        flash("That batch cannot be reset right now.", "error")
        return redirect(url_for("root_dashboard"))
    partner = db.get_partner(batch["partner_id"])
    where = partner["name"] if partner else f"Partner #{batch['partner_id']}"

    if action == "submission":
        db.reset_batch_submission(batch_id)
        db.log_action(session.get("name"), "root",
                      f"SYSTEM RESET: reversed Admin→Receiver submission of Batch #{batch_id} ({where}) back to draft")
        flash(f"Batch #{batch_id} ({where}) submission reset back to draft. It was removed from the Receiver list.", "success")
    elif action == "email":
        db.reset_batch_email(batch_id)
        db.log_action(session.get("name"), "root",
                      f"SYSTEM RESET: cleared emailed status of Batch #{batch_id} ({where})")
        flash(f"Batch #{batch_id} ({where}) email activity cleared. Receiver dashboard returned to pre-send state.", "success")
    else:
        flash("Unknown reset action.", "error")
    return redirect(url_for("root_dashboard"))


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
            password = uuid.uuid4().hex[:12]
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for("root_create_user"))

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
        new_photo = None
        new_sig = None
        try:
            new_photo = save_upload(request.files.get("photo"), "photos", "photo")
            new_sig = save_base64_signature(request.form.get("signature_data"), "signatures", "sig")
        except ValueError as e:
            flash(str(e), "error")
            return render_template("agent_detail.html", agent=agent, back_endpoint=back_endpoint)
        if new_photo:
            data["photo_path"] = new_photo
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
