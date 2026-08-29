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
        output_zip TEXT
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
    """)
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
