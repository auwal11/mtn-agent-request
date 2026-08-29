"""
Form 6 - Approved Request (Self-Certified)
Form 7 - SSP Username Creation Request
Both are TABLE-style forms listing every user in the batch as a row.
Built from scratch with reportlab tables (no background image needed).
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

HEADER_BG = colors.HexColor("#F5A623")   # orange/yellow header like originals
HEADER_BG2 = colors.HexColor("#4CAF50")  # green header variant (Form7 dealer section)

def _table(data, col_widths, header_color=HEADER_BG):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), header_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#FBFBFB")]),
    ]))
    return t

def generate_form6(output_path, agents, partner_name, region, state):
    """
    agents: list of dicts with keys:
      surname, first_name, other_name, nin, qualification, gender,
      phone_number, lga, address, longitude, latitude, device_tag,
      store_name, ncc_region, checklist(dict of 10 booleans)
    """
    doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                             leftMargin=15, rightMargin=15, topMargin=15, bottomMargin=15)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Approved Request (Self-Certified)", styles['Title']), Spacer(1,8)]

    header = ["S/N","SURNAME","FIRST NAME","OTHER NAME","NIN","QUALIFICATION","GENDER",
              "PHONE NUMBER","PARTNER NAME","REGION","STATE","LGA"]
    rows = [header]
    for i,a in enumerate(agents,1):
        rows.append([str(i), a['surname'], a['first_name'], a.get('other_name',''),
                     a['nin'], a.get('qualification','SSCE'), a['gender'],
                     a['phone_number'], partner_name, region, state, a['lga']])
    elements.append(_table(rows, [25,60,60,55,60,55,45,65,90,55,45,45]))
    elements.append(Spacer(1,14))

    header2 = ["S/N","CURRENT ADDRESS","LONGITUDE","LATITUDE","DEVICE TAG ID","STORENAME","NCC REGION"]
    rows2 = [header2]
    for i,a in enumerate(agents,1):
        rows2.append([str(i), a['address'], str(a.get('longitude','')), str(a.get('latitude','')),
                      a['device_tag'], a['store_name'], a.get('ncc_region', region)])
    elements.append(_table(rows2, [25,200,60,60,110,110,70]))
    elements.append(Spacer(1,14))

    checklist_fields = ['properly_lit_outlet','plain_white_background','permanent_structure',
                         'mtn_logo_displayed','sim_reg_centre_signage','agent_trained',
                         'cert_training_issued','sim_reg_auth_certificate',
                         'ncc_certificate_from_partner','mtn_id_cards_issued']
    header3 = ["S/N"] + [f.replace('_',' ').upper() for f in checklist_fields]
    rows3 = [header3]
    for i,a in enumerate(agents,1):
        cl = a.get('checklist', {})
        rows3.append([str(i)] + ["YES" if cl.get(f, True) else "NO" for f in checklist_fields])
    elements.append(_table(rows3, [25]+[68]*10))

    doc.build(elements)

def generate_form7(output_path, agents, partner_name, region, state, area="ADAMAWA"):
    doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                             leftMargin=15, rightMargin=15, topMargin=15, bottomMargin=15)
    styles = getSampleStyleSheet()
    elements = [Paragraph("SSP Username Creation Request", styles['Title']), Spacer(1,8)]

    header = ["S/N","DEALERNAME","REGION","AREA","STATE","LGA","TERRITORY","CLUSTER"]
    rows = [header]
    for i,a in enumerate(agents,1):
        rows.append([str(i), partner_name, region, area, state, a['lga'],
                     a.get('territory',''), a.get('cluster','')])
    elements.append(_table(rows, [25,110,60,70,50,50,70,70], header_color=HEADER_BG2))
    elements.append(Spacer(1,14))

    header2 = ["OUTLET","ADDRESS","DIVISION","SURNAME","FIRST NAME","OTHER NAME","NIN"]
    rows2 = [header2]
    for a in agents:
        rows2.append([a['store_name'], a['address'], a.get('division','SALES AND DISTRIBUTION'),
                      a['surname'], a['first_name'], a.get('other_name',''), a['nin']])
    elements.append(_table(rows2, [90,150,90,65,65,60,70]))
    elements.append(Spacer(1,14))

    header3 = ["PHONE NUMBER","EMAIL","DEVICE TAG","FEEDBACK"]
    rows3 = [header3]
    for a in agents:
        rows3.append([a['phone_number'], a.get('email',''), a['device_tag'], ''])
    elements.append(_table(rows3, [80,150,150,150]))
    elements.append(Spacer(1,14))

    checklist_fields = ['properly_lit_outlet','white_background','permanent_structure',
                         'mtn_logo_displayed','marked_as_sim_centre','agent_trained',
                         'cert_training_issued','sim_reg_auth_cert','ncc_cert_from_partner',
                         'mtn_id_cards_issued']
    header4 = [f.replace('_',' ').upper() for f in checklist_fields]
    rows4 = [header4]
    for a in agents:
        cl = a.get('checklist', {})
        rows4.append(["YES" if cl.get(f, True) else "NO" for f in checklist_fields])
    elements.append(_table(rows4, [63]*10, header_color=HEADER_BG2))

    doc.build(elements)

if __name__ == "__main__":
    sample_agents = [
        dict(surname="MUSTAPHA", first_name="ZAINAB", other_name="", nin="12345678901",
             qualification="SSCE", gender="FEMALE", phone_number="08012345678",
             lga="TAKUM", address="NEW MARKET ROAD TAKUM TARABA STATE",
             longitude="11.27", latitude="9.20", device_tag="MTN0299999",
             store_name="ZAINAB COMMUNICATION", ncc_region="NORTHEAST",
             territory="WUKARI", cluster="TAKUM", email="zainab@example.com",
             division="SALES AND DISTRIBUTION", checklist={}),
    ] * 12  # simulate 12 users for a valid batch (>=10)
    generate_form6("Form6_TEST_output.pdf", sample_agents, "RACU INTERNATIONAL LTD", "NORTHEAST", "TARABA")
    generate_form7("Form7_TEST_output.pdf", sample_agents, "RACU INTERNATIONAL LTD", "NORTHEAST", "TARABA")
    print("done")
