import os
import zipfile
from datetime import datetime

from generators.form1_certificate import generate_form1_multi
from generators.form2_authorisation import generate_form2_multi
from generators.form3_deduction import generate_form3_multi
from generators.form4_idcard import generate_form4_multi
from generators.form5_agent_form import generate_form5_multi
from generators.form6_form7_tables import generate_form6, generate_form7

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE)
OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def build_certificate_id(dealer_code, lga, sequence_no):
    lga_code = (lga or "TAK")[:3].upper()
    return f"{dealer_code}-{lga_code}-{sequence_no}"


def generate_batch_package(partner_row, batch_row, agent_rows):
    """
    partner_row / batch_row: sqlite3.Row
    agent_rows: list of sqlite3.Row (agents in the batch)
    Returns path to the generated ZIP file.
    """
    batch_dir = os.path.join(OUTPUTS_DIR, f"batch_{batch_row['id']}")
    os.makedirs(batch_dir, exist_ok=True)

    date_authorized = batch_row['date_authorized'] or datetime.now().strftime("%d/%m/%Y")
    day, month, year = date_authorized.split("/")

    # --- Build common agent dict list ---
    agents_common = []
    for a in agent_rows:
        full_name = f"{a['first_name']} {a['surname']}".strip().upper()
        cert_id = build_certificate_id(partner_row['dealer_code'], a['lga'], a['sequence_no'])
        agents_common.append(dict(
            row=a,
            full_name=full_name,
            cert_id=cert_id,
        ))

    # --- Form 1: Training Certificate ---
    f1_agents = [dict(full_name=x['full_name'], cert_id=x['cert_id']) for x in agents_common]
    generate_form1_multi(
        os.path.join(batch_dir, "Form1_Training_Certificate.pdf"),
        f1_agents,
        partner_name=partner_row['name'],
        region=partner_row['region'],
        course_title="SIMREGISTRATION GUIDLINES, COMPLIANCE AND PROCESSES",
    )

    # --- Form 2: Certificate of Authorisation ---
    f2_agents = [dict(full_name=x['full_name'],
                       location=x['row']['outlet_address'],
                       kit_no=x['row']['device_tag_id']) for x in agents_common]
    generate_form2_multi(
        os.path.join(batch_dir, "Form2_Certificate_of_Authorisation.pdf"),
        f2_agents, partner_name=partner_row['name'], region=partner_row['region'],
        day=day, month=month, year=year, stdm_name=partner_row['stdm_name'] or '',
    )

    # --- Form 3: Authorization for Deduction ---
    f3_agents = [dict(first_name=x['row']['first_name'], surname=x['row']['surname'],
                       device_tag=x['row']['device_tag_id'], momo_number=x['row']['momo_number'],
                       lga=x['row']['lga'], state=x['row']['state'],
                       signature_path=x['row']['signature_path']) for x in agents_common]
    generate_form3_multi(os.path.join(batch_dir, "Form3_Authorization_Deduction.pdf"), f3_agents)

    # --- Form 4: ID Cards ---
    f4_agents = [dict(first_name=x['row']['first_name'], surname=x['row']['surname'],
                       photo_path=x['row']['photo_path']) for x in agents_common]
    generate_form4_multi(os.path.join(batch_dir, "Form4_ID_Cards.pdf"), f4_agents)

    # --- Form 5: SIM Registration Agent & Outlet Recruitment Form ---
    f5_agents = [dict(full_name=x['full_name'], phone_number=x['row']['phone_number'],
                       email=x['row']['email'], qualification=x['row']['qualification'],
                       outlet_address=x['row']['outlet_address'], outlet_type=x['row']['outlet_type'],
                       cluster=x['row']['cluster'], lga=x['row']['lga'], territory=x['row']['territory'],
                       device_id=x['row']['device_tag_id'], device_imei=x['row']['device_imei'],
                       photo_path=x['row']['photo_path'], signature_path=x['row']['signature_path'])
                 for x in agents_common]
    generate_form5_multi(
        os.path.join(batch_dir, "Form5_SIM_Reg_Agent_Outlet_Form.pdf"),
        f5_agents, partner_name=partner_row['name'], dealer_code=partner_row['dealer_code'],
        region=partner_row['region'], state=partner_row['state'],
        ceo_name=partner_row['ceo_name'], ceo_signature_path=partner_row['ceo_signature_file'],
        date_str=date_authorized,
    )

    # --- Form 6 & 7: Table-style forms ---
    checklist_keys = ['properly_lit_outlet','plain_white_background','permanent_structure',
                       'mtn_logo_displayed','sim_reg_centre_signage','agent_trained',
                       'cert_training_issued','sim_reg_auth_certificate',
                       'ncc_certificate_from_partner','mtn_id_cards_issued']
    f67_agents = []
    for x in agents_common:
        r = x['row']
        checklist = {k: bool(r[k]) for k in checklist_keys}
        f67_agents.append(dict(
            surname=r['surname'], first_name=r['first_name'], other_name=r['other_name'] or '',
            nin=r['nin'], qualification=r['qualification'], gender=r['gender'],
            phone_number=r['phone_number'], lga=r['lga'], address=r['outlet_address'],
            longitude=r['longitude'], latitude=r['latitude'], device_tag=r['device_tag_id'],
            store_name=r['outlet_name'], ncc_region=r['ncc_region'], territory=r['territory'],
            cluster=r['cluster'], email=r['email'], division=r['division'], checklist=checklist,
        ))
    generate_form6(os.path.join(batch_dir, "Form6_Approved_Request.pdf"), f67_agents,
                    partner_row['name'], partner_row['region'], partner_row['state'])
    generate_form7(os.path.join(batch_dir, "Form7_SSP_Username_Creation.pdf"), f67_agents,
                    partner_row['name'], partner_row['region'], partner_row['state'])

    # --- Form 8: NCC License (unchanged, attach as-is) ---
    license_src = partner_row['ncc_license_file']
    if license_src and os.path.exists(license_src):
        import shutil
        shutil.copy(license_src, os.path.join(batch_dir, "Form8_NCC_License.pdf"))

    # --- ZIP everything ---
    zip_path = os.path.join(OUTPUTS_DIR, f"Batch_{partner_row['name'].replace(' ','_')}_{batch_row['id']}.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(batch_dir)):
            zf.write(os.path.join(batch_dir, fname), arcname=fname)

    return zip_path
