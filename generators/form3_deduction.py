from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG = os.path.join(BASE, "assets", "form3_bg.png")
FONT_PATH = os.path.join(BASE, "assets", "fonts", "Poppins-Bold.ttf")

PAGE_W, PAGE_H = 595, 842
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

FIELD_ROWS = [
    ("First Name:", 1068, "first_name"),
    ("Surname:", 1133, "surname"),
    ("Device Tag ID:", 1195, "device_tag"),
    ("MoMo Number:", 1256, "momo_number"),
    ("LGA:", 1318, "lga"),
    ("State:", 1378, "state"),
]

def generate_form3_multi(output_path, agents):
    """agents: list of dicts with keys first_name, surname, device_tag, momo_number,
       lga, state, signature_path (optional)"""
    _ensure_font()
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    for a in agents:
        c.drawImage(BG, 0, 0, width=PAGE_W, height=PAGE_H)
        c.setFillColorRGB(0.15,0.15,0.17)
        for label, y_px, key in FIELD_ROWS:
            c.setFont('Poppins-Bold', 13)
            x,y = xy(197, y_px); c.drawString(x, y, label)
            label_width_pts = c.stringWidth(label, 'Poppins-Bold', 13)
            value_x_px = 197 + (label_width_pts / PX) + 14
            c.setFont('Helvetica', 13)
            x,y = xy(value_x_px, y_px); c.drawString(x, y, str(a.get(key, '')))
        c.setFont('Poppins-Bold', 13)
        x,y = xy(197,1440); c.drawString(x,y,"Signature:")
        sig = a.get('signature_path')
        if sig and os.path.exists(sig):
            img = ImageReader(sig)
            iw, ih = img.getSize()
            tw = 110
            th = tw*ih/iw
            x,y = xy(410,1450)
            c.drawImage(img, x, y, width=tw, height=th, mask='auto')
        c.showPage()
    c.save()
