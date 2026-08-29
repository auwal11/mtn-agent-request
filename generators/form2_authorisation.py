from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG = os.path.join(BASE, "assets", "form2_bg.png")
FONT_PATH = os.path.join(BASE, "assets", "fonts", "Poppins-Bold.ttf")

PAGE_W, PAGE_H = 842, 595
PX = 72/200.0

_registered = False
def _ensure_font():
    global _registered
    if not _registered:
        try:
            pdfmetrics.registerFont(TTFont('Poppins-Bold', FONT_PATH))
        except Exception:
            pass
        _registered = True

def xy(x_px, y_px_top):
    return x_px*PX, PAGE_H-(y_px_top*PX)

def generate_form2_multi(output_path, agents, partner_name, region, day, month, year):
    """agents: list of dicts with keys full_name, location, kit_no"""
    _ensure_font()
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    for a in agents:
        c.drawImage(BG, 0, 0, width=PAGE_W, height=PAGE_H)
        c.setFillColorRGB(0.16,0.16,0.18)
        c.setFont('Poppins-Bold', 12.5)
        x,y = xy(975,505); c.drawString(x,y,a['full_name'])
        c.setFont('Poppins-Bold', 11)
        x,y = xy(685,600); c.drawString(x,y,a['location'])
        c.setFont('Poppins-Bold', 12.5)
        x,y = xy(1290,715); c.drawCentredString(x,y,a['kit_no'])
        c.setFont('Poppins-Bold', 11.5)
        x,y = xy(815,820); c.drawString(x,y,partner_name)
        c.setFont('Poppins-Bold', 12.5)
        x,y = xy(780,955); c.drawCentredString(x,y,day)
        x,y = xy(1230,955); c.drawCentredString(x,y,month)
        x,y = xy(1610,955); c.drawCentredString(x,y,year)
        x,y = xy(275,1345); c.drawString(x,y,region)
        c.setFont('Poppins-Bold', 11)
        x,y = xy(635,1345); c.drawString(x,y,partner_name)
        c.showPage()
    c.save()
