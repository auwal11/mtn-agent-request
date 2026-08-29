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

def generate_form3_multi(output_path, agents):
    """agents: list of dicts with keys first_name, surname, device_tag, momo_number,
       lga, state, signature_path (optional)"""
    _ensure_font()
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    for a in agents:
        c.drawImage(BG, 0, 0, width=PAGE_W, height=PAGE_H)
        c.setFillColorRGB(0.15,0.15,0.17)
        c.setFont('Poppins-Bold', 13)
        x,y = xy(280,1068); c.drawString(x,y,a['first_name'])
        x,y = xy(255,1133); c.drawString(x,y,a['surname'])
        x,y = xy(305,1195); c.drawString(x,y,a['device_tag'])
        x,y = xy(365,1256); c.drawString(x,y,a['momo_number'])
        x,y = xy(225,1318); c.drawString(x,y,a['lga'])
        x,y = xy(255,1378); c.drawString(x,y,a['state'])
        sig = a.get('signature_path')
        if sig and os.path.exists(sig):
            img = ImageReader(sig)
            iw, ih = img.getSize()
            tw = 110
            th = tw*ih/iw
            x,y = xy(260,1450)
            c.drawImage(img, x, y, width=tw, height=th, mask='auto')
        c.showPage()
    c.save()
