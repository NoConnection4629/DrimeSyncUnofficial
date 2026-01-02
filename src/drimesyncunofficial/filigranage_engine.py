
import os
import io
import math
import json
import secrets
import random
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
except ImportError:
    qrcode = None
    StyledPilImage = None
    RoundedModuleDrawer = None

try:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color
    from reportlab.lib.utils import ImageReader
except ImportError:
    PdfReader = None
    PdfWriter = None
    canvas = None
    Color = None
    ImageReader = None

class OmegaEngine:
    def __init__(self, log_callback=None):
        self.log = log_callback if log_callback else lambda m, c=None: print(f"[{c}] {m}")

    def generate_qr_code(self, data):
        if not qrcode:
            raise Exception("La librairie 'qrcode' n'est pas installée.")
        
        content = json.dumps(data, separators=(',', ':'))
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=0)
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer()).convert("RGBA")
        
        datas = img.getdata()
        new_data = []
        for item in datas:
            if item[0] > 230: new_data.append((255, 255, 255, 0))
            else: new_data.append((50, 50, 50, 255))
        img.putdata(new_data)
        return img

    def draw_micro_text_border(self, draw, w, h, text):
        try: font = ImageFont.truetype("arial.ttf", 10)
        except: font = ImageFont.load_default()
        
        full_line = (text + "  ///  ") * 50
        fill = (100, 100, 100, 80)
        
        draw.text((10, 5), full_line, font=font, fill=fill)
        draw.text((10, h - 15), full_line, font=font, fill=fill)

    def get_yellow_dots_layer(self, w, h):
        layer = Image.new("RGBA", (w, h), (0,0,0,0))
        pat_w, pat_h = 120, 120
        pattern = Image.new("RGBA", (pat_w, pat_h), (0,0,0,0))
        d_pat = ImageDraw.Draw(pattern)
        fill = (255, 255, 0, 40)
        step = 60
        for y in range(0, pat_h, step):
            for x in range(0, pat_w, step):
                offsets = [(10,10), (30,15), (15,30), (40,35), (25,50)]
                for ox, oy in offsets:
                                                                 
                    jx = random.randint(-20, 20)
                    jy = random.randint(-20, 20)
                    d_pat.ellipse((x+ox+jx, y+oy+jy, x+ox+jx+3, y+oy+jy+3), fill=fill)
        
        for y in range(0, h, pat_h):
            for x in range(0, w, pat_w):
                layer.paste(pattern, (x, y))
        return layer

    def process_image(self, input_path, output_path, data, qr_img, options):
        try:
            with Image.open(input_path) as original:
                base = ImageOps.exif_transpose(original).convert("RGBA")
                max_dim = 2500
                if max(base.size) > max_dim:
                    self.log(f"[PERF] Redimensionnement image ({base.size} -> {max_dim}px)...")
                    base.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                
                w, h = base.size
                overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)

                if options.get("microprint"):
                    self.draw_micro_text_border(draw, w, h, f"HASH:{data['doc_hash']} - ID:{data['uuid']}")
                
                if options.get("anti_copy"):
                    dots_layer = self.get_yellow_dots_layer(w, h)
                    overlay = Image.alpha_composite(overlay, dots_layer)
                    draw = ImageDraw.Draw(overlay)

                if options.get("mesh"):
                    line_color = (150, 150, 150, 40)
                    for y in range(0, h, 120):
                        points = []
                                                     
                        phase_shift = random.uniform(0, math.pi * 2)
                                                       
                        amplitude = random.randint(10, 25)
                        for x in range(0, w, 20):
                            points.append((x, y + math.sin((x/30.0) + phase_shift)*amplitude))
                        if len(points)>1: draw.line(points, fill=line_color, width=1)
                    
                    txt = f"{data['to']} • {data['ts'][:10]} • {data['uuid'][:4]}"
                    font_size = int(w / 50) 
                    try: font = ImageFont.truetype("arial.ttf", font_size)
                    except: font = ImageFont.load_default()
                    
                    bbox = draw.textbbox((0,0), txt, font=font)
                    tile = Image.new('RGBA', (bbox[2] + 40, bbox[3] + 40), (0,0,0,0))
                    dt = ImageDraw.Draw(tile)
                    dt.text((22, 22), txt, font=font, fill=(0,0,0,30))
                    dt.text((20, 20), txt, font=font, fill=(100,100,100,140))
                    
                    rotated_tile = tile.rotate(35, expand=True)
                    rw, rh = rotated_tile.size
                    step_y, step_x = int(rh * 0.8), int(rw * 0.8)
                    for y in range(-rh, h, step_y):
                                                            
                        row_offset = random.randint(0, 150)
                        for x in range(-rw, w, step_x):
                             overlay.paste(rotated_tile, (x + row_offset, y), rotated_tile)

                if options.get("crypto_link"):
                    qr_size = int(w / 12)
                    qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
                    m = int(w / 30)
                    positions = []
                    if options.get("qr_triangulation"):
                        positions = [
                            (w - qr_size - m, m),
                            (m, h - qr_size - m),
                            (w - qr_size - m, h - qr_size - m)
                        ]
                    else:
                        positions = [(w - qr_size - m, h - qr_size - m)]
                    
                    for pos in positions:
                        overlay.paste(qr_resized, pos, qr_resized)

                meta = base.info
                meta["Copyright"] = data.get('author', 'DrimeSync Unofficial')
                meta["Software"] = "DrimeSync Unofficial"
                meta["Description"] = f"Secured for {data['to']} - Hash: {data['doc_hash']}"
                meta["Author"] = data.get('author', 'DrimeSync Unofficial')
                
                final = Image.alpha_composite(base, overlay).convert("RGB")
                self.log(f"[DEBUG] Sauvegarde Image vers {output_path}...")
                
                try:
                    final.save(output_path, "JPEG", quality=100, subsampling=0, exif=base.getexif())
                except Exception as e_exif:
                    self.log(f"[WARN] Erreur EXIF ({e_exif}), sauvegarde sans métadonnées...")
                    final.save(output_path, "JPEG", quality=100, subsampling=0)
                
                if os.path.exists(output_path):
                     self.log(f"[DEBUG] Image sauvegardée avec succès ({os.path.getsize(output_path)} bytes)")
                else:
                     self.log(f"[DEBUG] ERREUR: Image non trouvée après save!", "red")
                     
        except Exception as e:
            self.log(f"Erreur Moteur Image: {str(e)}", "red")
            raise e

    def draw_yellow_dots_pdf(self, c, w, h):
        c.setFillColor(Color(1, 1, 0, alpha=0.2))
        pattern_step = 60
        max_x = int(w)
        max_y = int(h)
        for y in range(0, max_y, pattern_step):
            for x in range(0, max_x, pattern_step):
                offsets = [(10,10), (30,15), (15,30), (40,35), (25,50)]
                for ox, oy in offsets:
                                             
                    jx = random.randint(-20, 20)
                    jy = random.randint(-20, 20)
                    dx, dy = x + ox + jx, y + oy + jy
                    if dx < w and dy < h:
                        c.circle(dx, dy, 1.5, fill=1, stroke=0)

    def process_pdf(self, input_path, output_path, data, qr_img, options):
        try:
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            img_reader = ImageReader(qr_buffer)
            
            target_pdf = PdfReader(input_path)
            writer = PdfWriter()
            
            for page in target_pdf.pages:
                p_width = float(page.mediabox.width)
                p_height = float(page.mediabox.height)
                
                packet = io.BytesIO()
                c = canvas.Canvas(packet, pagesize=(p_width, p_height))
                
                if options.get("microprint"):
                    c.setFillColor(Color(0.4, 0.4, 0.4, alpha=0.3))
                    c.setFont("Helvetica", 5) 
                    micro_text = (f"HASH:{data['doc_hash']} /// ID:{data['uuid']} /// " * 20)
                    c.drawString(10, p_height - 10, micro_text)
                    c.drawString(10, 10, micro_text)
                
                if options.get("anti_copy"):
                    self.draw_yellow_dots_pdf(c, p_width, p_height)

                if options.get("mesh"):
                    c.setFillColor(Color(0.4, 0.4, 0.4, alpha=0.2))
                    c.setFont("Helvetica-Bold", 10)
                    c.saveState()
                    c.translate(p_width/2, p_height/2)
                    c.rotate(45)
                    diag = math.sqrt(p_width**2 + p_height**2)
                    c.translate(-diag/2, -diag/2)
                    full_text = f"SECURISÉ POUR : {data['to']}  ///  {data['ts'][:10]}  ///  ID:{data['uuid'][:4]}"
                    limit = int(diag) + 200
                    for y in range(-200, limit, 40):
                        indent = 60 if (y//40)%2 == 0 else 0
                                                                    
                        jitter_y = random.randint(-25, 25)
                        for x in range(-200, limit, 400):
                            c.drawString(x + indent, y + jitter_y, full_text)
                    c.restoreState()

                if options.get("crypto_link"):
                    q_size = 70; m = 30
                    positions = []
                    if options.get("qr_triangulation"):
                        positions = [
                            (p_width - q_size - m, p_height - q_size - m),
                            (m, m),
                            (p_width - q_size - m, m)
                        ]
                    else:
                        positions = [(p_width - q_size - m, m)] 
                    
                    for (x, y) in positions:
                        c.drawImage(img_reader, x, y, width=q_size, height=q_size, mask='auto')
                
                c.save()
                packet.seek(0)
                page.merge_page(PdfReader(packet).pages[0])
                writer.add_page(page)

            writer.add_metadata({
                '/Producer': data.get('author', 'DrimeSync Unofficial'), 
                '/Keywords': data['doc_hash'],
                '/Title': f"Secured Document for {data['to']}",
                '/Author': data.get('author', 'DrimeSync Unofficial'),
                '/Subject': f"Forensic ID: {data['uuid']}",
                '/Creator': 'Didier50 (discord) - No_Connection_4629 (reddit)'
            })
            
            user_pwd = data.get('user_pwd') or ""
            owner_pwd = secrets.token_urlsafe(64)
            writer.encrypt(user_password=user_pwd, owner_password=owner_pwd, permissions_flag=0b0100, algorithm="AES-256")
            
            self.log(f"[DEBUG] Sauvegarde PDF vers {output_path}...")
            with open(output_path, "wb") as f:
                writer.write(f)
            
            if os.path.exists(output_path):
                 self.log(f"[DEBUG] PDF sauvegardé avec succès ({os.path.getsize(output_path)} bytes)")
            else:
                 self.log(f"[DEBUG] ERREUR: PDF non trouvé après save!", "red")

        except Exception as e:
            self.log(f"Erreur Moteur PDF: {str(e)}", "red")
            raise e
    def read_metadata(self, input_path):
        data = {}
        try:
            path_str = str(input_path)
            ext = path_str.lower().split('.')[-1]
            if ext == 'pdf':
                if PdfReader:
                    try:
                        reader = PdfReader(path_str)
                        info = reader.metadata
                        if info:
                            for k, v in info.items():
                                clean_key = k.replace('/', '')
                                data[clean_key] = v
                    except Exception as e:
                        data["Error"] = f"PDF Read Error: {e}"
                else:
                    data["Error"] = "PyPDF library not available"
            else:
                if Image:
                    try:
                        with Image.open(path_str) as img:
                            data['Format'] = img.format
                            data['Size'] = f"{img.size[0]}x{img.size[1]}"
                            data['Mode'] = img.mode
                            info = img.info
                            if info:
                                for k, v in info.items():
                                    if isinstance(v, (str, int, float)) and k != "exif":
                                        data[k] = v
                    except Exception as e:
                        data["Error"] = f"Image Read Error: {e}"
                else:
                    data["Error"] = "PIL library not available"
        except Exception as e:
            data["Global Error"] = str(e)
        return data
