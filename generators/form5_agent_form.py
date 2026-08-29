"""
Form 5 - SIM Registration Agent & Outlet Recruitment Form (3 pages/agent)
NOTE: Unlike Forms 1-3 (which reuse the exact original background asset),
this version is built as a clean recreation of the data layout using reportlab.
Pixel-level visual calibration against the original scanned form (matching
fonts/positions exactly like Forms 1-3) is the next polish step - the same
"erase + overlay" method demonstrated for Forms 1-3 applies here, it just
needs the same measurement pass repeated for this form's 3 pages.
"""
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
import os

def generate_form5_multi(output_path, agents, partner_name, dealer_code, region,
                          state, ceo_name, ceo_signature_path, date_str):
    """agents: list of dicts with keys full_name, phone_number, kyc_username,
       qualification, outlet_address, outlet_type, cluster, lga, territory,
       device_id, device_imei, photo_path, signature_path"""
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             leftMargin=36, rightMargin=36, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=styles['Title'], fontSize=14)
    body = styles['Normal']
    elements = []

    for a in agents:
        elements.append(Paragraph("SIM REGISTRATION AGENT &amp; OUTLET RECRUITMENT FORM", h1))
        elements.append(Spacer(1,10))

        details = [
            ["FULL NAME (as on NIN)", a['full_name']],
            ["PHONE NUMBER", a['phone_number']],
            ["KYC USERNAME", a.get('kyc_username','')],
            ["EDUCATIONAL QUALIFICATION", a.get('qualification','SSCE')],
            ["OUTLET ADDRESS", a['outlet_address']],
            ["OUTLET TYPE", a.get('outlet_type','CCR OUTLET')],
            ["CLUSTER", a.get('cluster','')],
            ["LGA", a.get('lga','')],
            ["TERRITORY", a.get('territory','')],
            ["STATE", state],
            ["REGION", region],
            ["PARTNER'S NAME", partner_name],
            ["PARTNER'S DEALER CODE", dealer_code],
            ["DEVICE ID", a.get('device_id','')],
            ["DEVICE IMEI", a.get('device_imei','')],
        ]
        t = Table(details, colWidths=[160, 340])
        t.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.5,colors.grey),
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#F2F2F2')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        elements.append(t)
        elements.append(Spacer(1,14))

        checklist = ["Statutory ID on display","SIM Reg signage on outlet","MTN logo on outlet",
                     "Environment properly lit","White background","SIM Reg certificate present",
                     "Dealer NCC licence on display"]
        cl_data = [["S/N","OUTLET CHECKLIST","YES/NO"]]
        for i,item in enumerate(checklist,1):
            cl_data.append([str(i), item, "YES"])
        t2 = Table(cl_data, colWidths=[30,380,90])
        t2.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.5,colors.grey),
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#F5A623')),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8.5),
            ('ALIGN',(0,0),(0,-1),'CENTER'),
            ('ALIGN',(2,0),(2,-1),'CENTER'),
        ]))
        elements.append(t2)
        elements.append(Spacer(1, 20))

        # Attestation page
        elements.append(Paragraph("Agent's Attestation", styles['Heading2']))
        elements.append(Paragraph(
            f"I, <b>{a['full_name']}</b>, of {a['outlet_address']}, a SIM registration agent hereby "
            f"state that I have duly completed the Outlet Registration Form and that all information "
            f"provided is true, complete and accurate, and consent to the collection of my personal "
            f"data by MTN Nigeria Communications PLC.", body))
        elements.append(Spacer(1,10))
        elements.append(Paragraph(f"Dated this {date_str}", body))
        if a.get('signature_path') and os.path.exists(a['signature_path']):
            elements.append(RLImage(a['signature_path'], width=90, height=40))
        elements.append(Paragraph(f"Full Name: {a['full_name']}", body))
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("Partner's Authorization", styles['Heading2']))
        elements.append(Paragraph(
            f"I, <b>{partner_name}</b> (Deal Code: {dealer_code}), an authorized Partner of MTN "
            f"Nigeria Communications PLC, hereby authorize and approve the onboarding of "
            f"<b>{a['full_name']}</b> as a duly recognized agent operating within my assigned "
            f"territory under the MTN agent network.", body))
        elements.append(Spacer(1,10))
        elements.append(Paragraph(f"Dated this {date_str}", body))
        if ceo_signature_path and os.path.exists(ceo_signature_path):
            elements.append(RLImage(ceo_signature_path, width=90, height=40))
        elements.append(Paragraph(f"CEO/MD Full Name: {ceo_name}", body))

        elements.append(Spacer(1, 30))

    doc.build(elements)
