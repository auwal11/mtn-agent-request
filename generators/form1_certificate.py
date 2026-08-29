from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG = os.path.join(BASE, "assets", "form1_bg.png")
FONT_PATH = os.path.join(BASE, "assets", "fonts", "Poppins-Bold.ttf")

PAGE_W, PAGE_H = 842, 595
PX = 72/200.0

_registered = False
def _ensure_font():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont('Poppins-Bold', FONT_PATH))
        _registered = True

def xy(x_px, y_px_top):
    return x_px*PX, PAGE_H-(y_px_top*PX)

def generate_form1_multi(output_path, agents, partner_name, region, course_title,
                          position="CUSTOMER CARE REPRESENTATIVE"):
    """agents: list of dicts with keys full_name, cert_id"""
    _ensure_font()
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    for a in agents:
        c.drawImage(BG, 0, 0, width=PAGE_W, height=PAGE_H)
        c.setFillColorRGB(0.16,0.16,0.18)
        c.setFont('Poppins-Bold', 17)
        x,y = xy(1170,555); c.drawCentredString(x,y,a['full_name'])
        c.setFont('Poppins-Bold', 12.5)
        x,y = xy(600,705); c.drawString(x,y,position)
        x,y = xy(1465,705); c.drawString(x,y,f"ID:{a['cert_id']}")
        c.setFont('Poppins-Bold', 10.5)
        x,y = xy(870,1015); c.drawString(x,y,course_title)
        c.setFont('Poppins-Bold', 12.5)
        x,y = xy(355,1345); c.drawString(x,y,region)
        x,y = xy(1560,1345); c.drawString(x,y,partner_name)
        c.showPage()
    c.save()
