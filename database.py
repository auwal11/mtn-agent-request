import sqlite3
import os
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR can be pointed at a persistent volume/disk on hosting platforms
# (e.g. Render/Fly.io persistent disk mount, PythonAnywhere home dir) via env var.
DATA_DIR = os.environ.get("DATA_DIR", BASE)
DB_PATH = os.path.join(DATA_DIR, "dashboard.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        dealer_code TEXT NOT NULL,
        region TEXT DEFAULT 'NORTHEAST',
        state TEXT DEFAULT 'TARABA',
        lga TEXT DEFAULT 'TAKUM',
        address TEXT,
        ncc_license_no TEXT,
        ncc_license_file TEXT,
        stdm_name TEXT,
        ceo_name TEXT,
        ceo_signature_file TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        partner_id INTEGER REFERENCES partners(id),
        status TEXT DEFAULT 'draft',
        date_authorized TEXT,
        created_at TEXT,
        generated_at TEXT,
        output_zip TEXT,
        output_dir TEXT,
        emailed_at TEXT,
        emailed_to TEXT
    );

    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER REFERENCES batches(id),
        sequence_no INTEGER,
        surname TEXT NOT NULL,
        first_name TEXT NOT NULL,
        other_name TEXT,
        nin TEXT NOT NULL,
        gender TEXT,
        qualification TEXT DEFAULT 'SSCE',
        phone_number TEXT NOT NULL,
        momo_number TEXT,
        email TEXT,
        kyc_username TEXT,
        position TEXT DEFAULT 'CUSTOMER CARE REPRESENTATIVE',
        division TEXT DEFAULT 'SALES AND DISTRIBUTION',
        photo_path TEXT,
        signature_path TEXT,
        device_tag_id TEXT NOT NULL,
        device_imei TEXT,
        outlet_name TEXT,
        outlet_address TEXT,
        outlet_type TEXT DEFAULT 'CCR OUTLET',
        lga TEXT,
        territory TEXT,
        cluster TEXT,
        state TEXT,
        latitude TEXT,
        longitude TEXT,
        ncc_region TEXT,
        status TEXT DEFAULT 'submitted',
        added_by TEXT DEFAULT 'admin',
        session_token TEXT,
        submitted_partner_name TEXT,
        properly_lit_outlet INTEGER DEFAULT 1,
        plain_white_background INTEGER DEFAULT 1,
        permanent_structure INTEGER DEFAULT 1,
        mtn_logo_displayed INTEGER DEFAULT 1,
        sim_reg_centre_signage INTEGER DEFAULT 1,
        agent_trained INTEGER DEFAULT 1,
        cert_training_issued INTEGER DEFAULT 1,
        sim_reg_auth_certificate INTEGER DEFAULT 1,
        ncc_certificate_from_partner INTEGER DEFAULT 1,
        mtn_id_cards_issued INTEGER DEFAULT 1,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        company_id INTEGER REFERENCES partners(id),
        status TEXT DEFAULT 'enabled',
        created_at TEXT,
        last_login_at TEXT
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_name TEXT,
        actor_role TEXT,
        action TEXT,
        created_at TEXT
    );
    """)
    conn.commit()

    # --- Safe migration: add any newly-introduced columns to an existing DB file ---
    def ensure_columns(table, columns):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for col_name, col_def in columns:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
        conn.commit()

    ensure_columns("agents", [
        ("status", "TEXT DEFAULT 'submitted'"),
        ("added_by", "TEXT DEFAULT 'admin'"),
        ("session_token", "TEXT"),
        ("submitted_partner_name", "TEXT"),
    ])
    ensure_columns("batches", [
        ("output_dir", "TEXT"),
        ("emailed_at", "TEXT"),
        ("emailed_to", "TEXT"),
    ])

    # --- Seed the one Root/CEO account on first run ---
    from werkzeug.security import generate_password_hash
    root_exists = conn.execute("SELECT 1 FROM users WHERE role='root' LIMIT 1").fetchone()
    if not root_exists:
        root_name = os.environ.get("ROOT_NAME", "Auwal")
        root_password = os.environ.get("ROOT_PASSWORD", "AuwalControl")
        conn.execute("""INSERT INTO users (name,password_hash,role,company_id,status,created_at)
                         VALUES (?,?,?,?,?,?)""",
                     (root_name, generate_password_hash(root_password), "root", None,
                      "active", datetime.now().isoformat()))
        conn.commit()
    conn.close()

def get_or_create_active_partner():
    conn = get_conn()
    row = conn.execute("SELECT * FROM partners ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return row

def create_partner(name, dealer_code, region, state, lga, address, ncc_license_no,
                    ncc_license_file, stdm_name, ceo_name, ceo_signature_file):
    conn = get_conn()
    conn.execute("""INSERT INTO partners
        (name,dealer_code,region,state,lga,address,ncc_license_no,ncc_license_file,
         stdm_name,ceo_name,ceo_signature_file,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (name,dealer_code,region,state,lga,address,ncc_license_no,ncc_license_file,
         stdm_name,ceo_name,ceo_signature_file,datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_or_create_draft_batch(partner_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM batches WHERE partner_id=? AND status='draft' ORDER BY id DESC LIMIT 1",
        (partner_id,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO batches (partner_id,status,created_at) VALUES (?,?,?)",
                      (partner_id, 'draft', datetime.now().isoformat()))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM batches WHERE partner_id=? AND status='draft' ORDER BY id DESC LIMIT 1",
            (partner_id,)).fetchone()
    conn.close()
    return row

def add_agent(batch_id, data):
    conn = get_conn()
    seq = conn.execute("SELECT COUNT(*) c FROM agents WHERE batch_id=?", (batch_id,)).fetchone()['c'] + 1
    fields = list(data.keys())
    placeholders = ",".join(["?"]*len(fields))
    cols = ",".join(fields) + ",batch_id,sequence_no,created_at"
    vals = list(data.values()) + [batch_id, seq, datetime.now().isoformat()]
    placeholders += ",?,?,?"
    conn.execute(f"INSERT INTO agents ({cols}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()

def get_batch_agents(batch_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM agents WHERE batch_id=? ORDER BY id", (batch_id,)).fetchall()
    conn.close()
    return rows

def get_batch(batch_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    conn.close()
    return row

def get_partner(partner_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()
    conn.close()
    return row

def mark_batch_generated(batch_id, output_zip):
    conn = get_conn()
    conn.execute("UPDATE batches SET status='generated', generated_at=?, output_zip=? WHERE id=?",
                 (datetime.now().isoformat(), output_zip, batch_id))
    conn.commit()
    conn.close()

def mark_batch_sent_to_receiver(batch_id, output_zip, output_dir):
    conn = get_conn()
    conn.execute("""UPDATE batches SET status='sent_to_receiver', generated_at=?,
                     output_zip=?, output_dir=? WHERE id=?""",
                 (datetime.now().isoformat(), output_zip, output_dir, batch_id))
    conn.execute("UPDATE agents SET status='confirmed' WHERE batch_id=?", (batch_id,))
    conn.commit()
    conn.close()

def mark_batch_emailed(batch_id, to_email):
    conn = get_conn()
    conn.execute("UPDATE batches SET emailed_at=?, emailed_to=? WHERE id=?",
                 (datetime.now().isoformat(), to_email, batch_id))
    conn.commit()
    conn.close()

def list_batches_for_receiver(company_id=None):
    conn = get_conn()
    if company_id:
        rows = conn.execute("""SELECT * FROM batches WHERE status='sent_to_receiver'
                                AND partner_id=? ORDER BY id DESC""", (company_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM batches WHERE status='sent_to_receiver' ORDER BY id DESC").fetchall()
    conn.close()
    return rows


# --------------------------------------------------------- users / root ----
def log_action(actor_name, actor_role, action):
    conn = get_conn()
    conn.execute("INSERT INTO audit_log (actor_name,actor_role,action,created_at) VALUES (?,?,?,?)",
                 (actor_name, actor_role, action, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def recent_activity(limit=15):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows


def find_user_by_password(password):
    from werkzeug.security import check_password_hash
    conn = get_conn()
    candidates = conn.execute(
        "SELECT * FROM users WHERE status IN ('enabled','active')").fetchall()
    conn.close()
    for u in candidates:
        if check_password_hash(u["password_hash"], password):
            return u
    return None


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row


def touch_login(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET last_login_at=?, status='active' WHERE id=?",
                 (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


def list_users(role=None):
    conn = get_conn()
    q = """SELECT users.*, partners.name as company_name FROM users
           LEFT JOIN partners ON users.company_id = partners.id"""
    if role:
        rows = conn.execute(q + " WHERE users.role=? ORDER BY users.id DESC", (role,)).fetchall()
    else:
        rows = conn.execute(q + " WHERE users.role!='root' ORDER BY users.id DESC").fetchall()
    conn.close()
    return rows


def create_user(name, password, role, company_id, status="enabled"):
    from werkzeug.security import generate_password_hash
    conn = get_conn()
    conn.execute("""INSERT INTO users (name,password_hash,role,company_id,status,created_at)
                     VALUES (?,?,?,?,?,?)""",
                 (name, generate_password_hash(password), role, company_id, status,
                  datetime.now().isoformat()))
    conn.commit()
    conn.close()


def set_user_status(user_id, status):
    conn = get_conn()
    conn.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
    conn.commit()
    conn.close()


def list_companies():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM partners ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def create_blank_company(name):
    conn = get_conn()
    conn.execute("""INSERT INTO partners (name,dealer_code,created_at) VALUES (?,?,?)""",
                 (name, "", datetime.now().isoformat()))
    conn.commit()
    row = conn.execute("SELECT * FROM partners WHERE name=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
    conn.close()
    return row


def system_counts():
    conn = get_conn()
    companies = conn.execute("SELECT COUNT(*) c FROM partners").fetchone()["c"]
    admins = conn.execute("SELECT COUNT(*) c FROM users WHERE role='admin'").fetchone()["c"]
    receivers = conn.execute("SELECT COUNT(*) c FROM users WHERE role='receiver_admin'").fetchone()["c"]
    agents = conn.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) c FROM agents WHERE status IN ('submitted','in_review')").fetchone()["c"]
    active_sessions = conn.execute("SELECT COUNT(*) c FROM users WHERE status='active'").fetchone()["c"]
    conn.close()
    return dict(companies=companies, admins=admins, receivers=receivers, agents=agents,
                pending=pending, active_sessions=active_sessions)

def delete_agent(agent_id):
    conn = get_conn()
    conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    conn.commit()
    conn.close()

def list_batches(partner_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM batches WHERE partner_id=? ORDER BY id DESC", (partner_id,)).fetchall()
    conn.close()
    return rows

def get_agent(agent_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    conn.close()
    return row

def agent_company_id(agent_id):
    """Returns the partner/company id that owns this agent (via its batch),
    or None if the agent does not exist. Used to enforce that an Admin/
    Receiver Admin can only view/edit/delete agents belonging to their own
    company (session['company_id']) — see _forbid_cross_company in app.py."""
    conn = get_conn()
    row = conn.execute("""SELECT batches.partner_id as partner_id FROM agents
                           JOIN batches ON agents.batch_id = batches.id
                           WHERE agents.id=?""", (agent_id,)).fetchone()
    conn.close()
    return row["partner_id"] if row else None

def get_agents_by_session(session_token):
    conn = get_conn()
    rows = conn.execute("""SELECT agents.*, batches.status as batch_status FROM agents
                            JOIN batches ON agents.batch_id = batches.id
                            WHERE agents.session_token=? ORDER BY agents.id DESC""",
                         (session_token,)).fetchall()
    conn.close()
    return rows

def set_agent_status(agent_id, status):
    conn = get_conn()
    conn.execute("UPDATE agents SET status=? WHERE id=?", (status, agent_id))
    conn.commit()
    conn.close()

def update_agent(agent_id, data):
    conn = get_conn()
    sets = ",".join([f"{k}=?" for k in data.keys()])
    conn.execute(f"UPDATE agents SET {sets} WHERE id=?", list(data.values()) + [agent_id])
    conn.commit()
    conn.close()

def update_partner(partner_id, **fields):
    conn = get_conn()
    sets = ",".join([f"{k}=?" for k in fields.keys()])
    conn.execute(f"UPDATE partners SET {sets} WHERE id=?", list(fields.values()) + [partner_id])
    conn.commit()
    conn.close()
