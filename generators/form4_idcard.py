from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RC_LOGO = os.path.join(BASE, "assets", "rc_logo.png")
MTN_LOGO = os.path.join(BASE, "assets", "mtn_logo_box.png")
FONT_BOLD = os.path.join(BASE, "assets", "fonts", "Poppins-Bold.ttf")
FONT_REG = os.path.join(BASE, "assets", "fonts", "Poppins-Regular.ttf")

W, H = 1653, 2339
YELLOW = (238, 193, 12)
PAGE_W, PAGE_H = 595, 842

def _render_card_image(photo_path, first_name, surname, position, division):
    card = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, W-1, H-1], outline=(0,0,0), width=3)

    rc = Image.open(RC_LOGO).convert("RGBA"); rc.thumbnail((420,320))
    card.paste(rc, (40,30), rc)
    mtn = Image.open(MTN_LOGO).convert("RGBA"); mtn.thumbnail((380,240))
    card.paste(mtn, (W-40-mtn.width, 90), mtn)

    box = (150,340,1500,1660)
    bw, bh = box[2]-box[0], box[3]-box[1]
    if photo_path and os.path.exists(photo_path):
        photo = Image.open(photo_path).convert("RGB")
    else:
        photo = Image.new("RGB", (bw,bh), (220,220,220))
    pw, ph = photo.size
    scale = max(bw/pw, bh/ph)
    photo = photo.resize((max(1,int(pw*scale)), max(1,int(ph*scale))))
    px, py = photo.size
    left = max(0,(px-bw)//2); top = max(0,(py-bh)//2)
    photo = photo.crop((left, top, left+bw, top+bh))
    card.paste(photo, (box[0], box[1]))

    draw.rounded_rectangle((0,1660,W,H), radius=60, fill=YELLOW)
    draw.rectangle((0,1660,W,1720), fill=YELLOW)

    f_big = ImageFont.truetype(FONT_BOLD, 78)
    f_small = ImageFont.truetype(FONT_BOLD, 56)
    f_pos = ImageFont.truetype(FONT_REG, 42)
    f_div = ImageFont.truetype(FONT_BOLD, 40)

    def center_text(text, y, font, fill=(35,35,40)):
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2]-bbox[0]
        draw.text(((W-tw)/2, y), text, font=font, fill=fill)

    center_text(first_name.upper(), 1745, f_big)
    center_text(surname.capitalize(), 1840, f_small)
    center_text(position.upper(), 2040, f_pos)
    center_text(division.upper(), 2110, f_div)
    return card

def generate_form4_multi(output_path, agents,
                          position="CUSTOMER CARE REPRESENTATIVE",
                          division="SALES AND DISTRIBUTION"):
    """agents: list of dicts with keys first_name, surname, photo_path"""
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))
    for a in agents:
        card = _render_card_image(a.get('photo_path'), a['first_name'], a['surname'],
                                   position, division)
        c.drawImage(ImageReader(card), 0, 0, width=PAGE_W, height=PAGE_H)
        c.showPage()
    c.save()
