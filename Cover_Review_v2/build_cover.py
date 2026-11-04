"""Editable, dimensioned review cover. Interior remains untouched."""
from pathlib import Path
import hashlib
import json
import math
import shutil

import fitz

ROOT = Path(__file__).resolve().parent
GENERATED = Path('/workspace/generated_images/exec-40af6286-96f4-4a18-9b4d-2f638b51f76f.png')
ART = ROOT / 'Cover_Illustration_v2.png'
OUT = ROOT / 'Wer_hat_den_Kommandanten_Cover_REVIEW_v2.pdf'
FONT_ROOT = Path('/usr/share/fonts/truetype/liberation')
FONT_FILES = {
    'Display': FONT_ROOT/'LiberationSerif-Bold.ttf',
    'Body': FONT_ROOT/'LiberationSerif-Regular.ttf',
    'Italic': FONT_ROOT/'LiberationSerif-Italic.ttf',
    'Sans': FONT_ROOT/'LiberationSans-Regular.ttf',
    'SansBold': FONT_ROOT/'LiberationSans-Bold.ttf',
}
FONTS = {key: fitz.Font(fontfile=str(path)) for key, path in FONT_FILES.items()}
GOLD = (0.91, 0.73, 0.42)
CREAM = (0.99, 0.94, 0.82)
QUIET = (0.86, 0.82, 0.74)
NAVY = (0.035, 0.055, 0.085)

PAGE_COUNT = 104
TRIM_W, TRIM_H, BLEED = 450.0, 666.0, 9.0
SPINE_IN = PAGE_COUNT * 0.002252
SPINE = SPINE_IN * 72
WIDTH, HEIGHT = 2*TRIM_W + SPINE + 2*BLEED, TRIM_H + 2*BLEED
BACK = fitz.Rect(BLEED, BLEED, BLEED+TRIM_W, BLEED+TRIM_H)
SPINE_RECT = fitz.Rect(BACK.x1, BLEED, BACK.x1+SPINE, BLEED+TRIM_H)
FRONT = fitz.Rect(SPINE_RECT.x1, BLEED, SPINE_RECT.x1+TRIM_W, BLEED+TRIM_H)
PLACED = []


def register(page):
    for key, path in FONT_FILES.items():
        page.insert_font(fontname=key, fontfile=str(path))


def line(page, text, x, baseline, size, font='Body', color=CREAM, align='left', width=0):
    measured = FONTS[font].text_length(text, fontsize=size)
    if align == 'center':
        x += (width-measured)/2
    assert width <= 0 or measured <= width+0.01, ('Text too wide', text, measured, width)
    page.insert_text((x, baseline), text, fontsize=size, fontname=font, color=color)
    PLACED.append({'text': text, 'font': font, 'size': size, 'baseline': [x, baseline], 'width': measured})


def tracked(page, text, x, baseline, size, tracking, width, color=GOLD):
    measured = FONTS['SansBold'].text_length(text, fontsize=size)+tracking*(len(text)-1)
    assert measured <= width
    x += (width-measured)/2
    for ch in text:
        page.insert_text((x, baseline), ch, fontsize=size, fontname='SansBold', color=color)
        x += FONTS['SansBold'].text_length(ch, fontsize=size)+tracking


def paragraph(page, text, x, baseline, width, size=12.0, leading=17.0, font='Body', color=CREAM):
    words = text.split()
    current = ''
    for word in words:
        candidate = current+' '+word if current else word
        if current and FONTS[font].text_length(candidate, fontsize=size) > width:
            line(page, current, x, baseline, size, font, color, width=width)
            baseline += leading
            current = word
        else:
            current = candidate
    if current:
        line(page, current, x, baseline, size, font, color, width=width)
        baseline += leading
    return baseline


def build():
    ROOT.mkdir(exist_ok=True)
    if ART.exists() and GENERATED.exists():
        assert ART.read_bytes() == GENERATED.read_bytes()
    elif not ART.exists():
        shutil.copy2(GENERATED, ART)
    doc = fitz.open()
    page = doc.new_page(width=WIDTH, height=HEIGHT)
    register(page)
    # The generated spread already has the correct panel arrangement and ratio.
    page.insert_image(page.rect, filename=str(ART), keep_proportion=False)

    # Front: live, embedded Unicode typography over the quiet title sky.
    fx, fw = FRONT.x0+28, FRONT.width-56
    tracked(page, 'ELIZABETH ERIN', fx, 35, 10.5, 2.6, fw, CREAM)
    line(page, 'WER HAT DEN', fx, 71, 26, 'Display', CREAM, 'center', fw)
    line(page, 'KOMMANDANTEN', fx, 112, 38, 'Display', CREAM, 'center', fw)
    line(page, 'GETÖTET?', fx, 166, 51, 'Display', GOLD, 'center', fw)
    tracked(page, 'LZ VIKTORIA · 1934', fx, 190, 9.2, 1.6, fw, CREAM)
    page.draw_line((FRONT.x0+100, 203), (FRONT.x1-100, 203), color=GOLD, width=0.7)
    # Keep the character faces unobstructed; the lower band covers only the
    # intentionally dark painted edge, well below all faces and clue details.
    page.draw_rect(fitz.Rect(FRONT.x0, 621, WIDTH, HEIGHT), color=None,
                   fill=(0.12, 0.035, 0.045), fill_opacity=0.82)
    page.draw_line((FRONT.x0+30, 621), (FRONT.x1-30, 621), color=GOLD, width=0.7)
    line(page, '18 KRIMINALFÄLLE ZUM SELBERLÖSEN', fx, 643, 13, 'Display', CREAM, 'center', fw)
    line(page, 'Das interaktive Krimi-Rätselbuch über den Wolken', fx, 660, 9.2, 'Sans', QUIET, 'center', fw)

    # Back: all sales copy is spoiler-free and agrees with the actual interior.
    bx, bw = BACK.x0+33, BACK.width-66
    line(page, 'EIN LUFTSCHIFF. 18 FÄLLE.', bx, 46, 9.5, 'SansBold', GOLD, width=bw)
    line(page, 'ÜBER DEM ATLANTIK', bx, 86, 26, 'Display', CREAM, width=bw)
    line(page, 'GIBT ES KEIN', bx, 117, 26, 'Display', CREAM, width=bw)
    line(page, 'ENTKOMMEN.', bx, 154, 34, 'Display', GOLD, width=bw)
    page.draw_line((bx, 174), (bx+bw, 174), color=GOLD, width=.7)
    y = paragraph(page,
        'Oktober 1934. Das Luxusluftschiff LZ Viktoria nimmt Kurs auf New York. '
        'Doch an Bord häufen sich Diebstähle, Erpressungen und Sabotageakte. '
        'In der dritten Nacht wird der Kommandant ermordet.', bx, 204, bw)
    y += 12
    y = paragraph(page, 'Sie sind an Bord. Und Sie ermitteln.', bx, y, bw, font='Display')
    y += 12
    y = paragraph(page,
        'Prüfen Sie Alibis, entdecken Sie verräterische Details in den Illustrationen '
        'und verbinden Sie die Spuren aus 18 Kriminalfällen. Am Ende zählt Ihre '
        'Antwort auf eine einzige Frage:', bx, y, bw)
    y += 9
    y = paragraph(page, 'Wer hat den Kommandanten getötet?', bx, y, bw,
                  size=14, leading=19, font='Display', color=GOLD)
    assert y < 465, ('Back blurb overrun', y)
    page.draw_line((bx, 468), (bx+bw, 468), color=GOLD, width=.5)
    line(page, 'GENAU HINSEHEN. LÜGEN ENTLARVEN.', bx, 490, 9.5, 'SansBold', CREAM, width=bw)
    line(page, 'DEN FALL SELBST LÖSEN.', bx, 505, 9.5, 'SansBold', CREAM, width=bw)
    line(page, 'Mit illustrierten Beweisen, Hinweisen und Lösungen.', bx, 526, 10, 'Italic', QUIET, width=bw)

    # KDP supplies the real barcode. No invented ISBN, price or fake bars.
    barcode = fitz.Rect(BACK.x1-18-144, BACK.y1-18-86.4, BACK.x1-18, BACK.y1-18)
    page.draw_rect(barcode, color=None, fill=(1, 1, 1))

    # The 104-page spine supports text. Keep ink at least 0.0625 in from
    # both folds. The complete title uses a 7 pt embedded serif face.
    page.draw_rect(fitz.Rect(SPINE_RECT.x0, 0, SPINE_RECT.x1, HEIGHT), color=None, fill=NAVY)
    title_spine = 'WER HAT DEN KOMMANDANTEN GETÖTET?'
    # Direct placement uses the actual ascent/descent bounds; text boxes add
    # unused line spacing which is inappropriate on this thin 104-page spine.
    font = FONTS['Display']
    spine_baseline_x = (SPINE_RECT.x0+SPINE_RECT.x1)/2-(font.ascender+font.descender)*7/2
    for wording, top, bottom, color in [(title_spine,80,470,GOLD), ('ELIZABETH ERIN',490,627,CREAM)]:
        length = font.text_length(wording,fontsize=7)
        assert length < bottom-top
        baseline_y = (top+bottom-length)/2
        page.insert_text((spine_baseline_x,baseline_y),wording,fontsize=7,fontname='Display',color=color,rotate=270)

    doc.set_metadata({'title': 'Wer hat den Kommandanten getötet? — Cover Review v2',
                       'author': 'Elizabeth Erin', 'subject': 'KDP standard colour paperback, 104 pages, 6.25 × 9.25 in',
                       'keywords': 'Review draft; artwork approval and print preflight pending'})
    doc.save(OUT, deflate=True, garbage=4)
    doc.close()
    validate(barcode)


def validate(barcode):
    doc = fitz.open(OUT)
    page = doc[0]
    assert len(doc) == 1
    assert abs(page.rect.width-WIDTH) < .001 and page.rect.height == HEIGHT
    text = page.get_text()
    assert 'GETÖTET?' in text and 'KRIMINALFÄLLE' in text
    assert '\ufffd' not in text and '\x00' not in text
    fonts = page.get_fonts(full=True)
    assert all(doc.extract_font(f[0])[3] for f in fonts)
    # No textual area may run across the folds except intentionally rotated
    # spine lettering. Authoring positions are also saved for later edits.
    spine_spans = []
    for block in page.get_text('dict')['blocks']:
        for row in block.get('lines', []):
            for span in row['spans']:
                rect = fitz.Rect(span['bbox'])
                assert page.rect.contains(rect), ('Text outside cover', span['text'])
                if row['dir'] == (0.0, 1.0):
                    assert rect.x0 >= SPINE_RECT.x0+4.5-.03 and rect.x1 <= SPINE_RECT.x1-4.5+.03, ('Spine safety', span)
                    spine_spans.append({'text': span['text'], 'bbox': list(rect)})
    assert len(spine_spans) == 2
    proofs = ROOT/'proofs'
    proofs.mkdir(exist_ok=True)
    for filename, clip, scale in [
        ('Cover_Full_Wrap_REVIEW.png', page.rect, 1.6),
        ('Cover_Front_REVIEW.png', FRONT, 2.0),
        ('Cover_Back_REVIEW.png', BACK, 2.0),
    ]:
        page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip).save(proofs/filename)
    # A separate guide sheet carries the trim/fold labels; the cover itself
    # contains no crop marks, registration marks, instructions or fake barcode.
    guide = fitz.open()
    gp = guide.new_page(width=WIDTH+80, height=HEIGHT+100)
    gp.insert_text((40, 26), 'COVER REVIEW — back | spine | front', fontsize=13)
    dest = fitz.Rect(40, 45, 40+WIDTH, 45+HEIGHT)
    gp.show_pdf_page(dest, doc, 0)
    for x in (BACK.x0, BACK.x1, SPINE_RECT.x1, FRONT.x1):
        gp.draw_line((40+x, 45), (40+x, 45+HEIGHT), color=(0,.65,.85), width=.6, dashes='[3 3]')
    for y in (BLEED, HEIGHT-BLEED):
        gp.draw_line((40, 45+y), (40+WIDTH, 45+y), color=(0,.65,.85), width=.6, dashes='[3 3]')
    gp.insert_text((40, HEIGHT+70),
        f'Trim 6.25 x 9.25 in | 104 pages | spine {SPINE_IN:.6f} in | wrap {WIDTH/72:.6f} x {HEIGHT/72:.2f} in', fontsize=10)
    gp.insert_text((40, HEIGHT+87), 'REVIEW DRAFT: art approval and final image-resolution preflight pending. White box is reserved for the KDP barcode.', fontsize=9)
    guide.save(ROOT/'Cover_Dimensions_REVIEW.pdf', deflate=True, garbage=4)
    gp.get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(proofs/'Cover_Dimensions_REVIEW.png')
    pixels = fitz.Pixmap(str(ART))
    spec = {
        'status': 'Review design; not print-final. User approval and image-resolution preflight pending.',
        'title': 'Wer hat den Kommandanten getötet?', 'author': 'Elizabeth Erin',
        'printer': 'Amazon KDP', 'binding': 'paperback', 'interior_print': 'standard colour, white paper',
        'interior_pages': PAGE_COUNT, 'trim_inches': [TRIM_W/72, TRIM_H/72],
        'bleed_inches': BLEED/72, 'spine_formula': '104 pages × 0.002252 inches/page',
        'spine_inches': SPINE_IN, 'spine_mm': SPINE_IN*25.4,
        'full_cover_inches': [WIDTH/72, HEIGHT/72], 'full_cover_mm': [WIDTH/72*25.4, HEIGHT/72*25.4],
        'pdf_dimensions_points': [WIDTH, HEIGHT], 'back_trim_rect_points': list(BACK),
        'spine_rect_points': list(SPINE_RECT), 'front_trim_rect_points': list(FRONT),
        'barcode_reserved_rect_points': list(barcode), 'barcode_reserved_inches': [2,1.2],
        'native_artwork_pixels': [pixels.width, pixels.height],
        'effective_artwork_ppi': min(pixels.width/(WIDTH/72),pixels.height/(HEIGHT/72)),
        'artwork_resolution_note': 'Generated review art is below the 300 ppi print target. Do not relabel it as native 300 ppi. Resolve high-resolution production artwork before print-final delivery.',
        'live_text_embedded_fonts': True, 'spine_text': spine_spans,
        'interior_modified': False, 'artwork_approval': 'pending',
        'artwork_sha256': hashlib.sha256(ART.read_bytes()).hexdigest(),
        'review_pdf': str(OUT), 'review_pdf_sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(),
        'required_300ppi_full_wrap_pixels_minimum': [math.ceil(WIDTH/72*300), math.ceil(HEIGHT/72*300)],
    }
    (ROOT/'cover-specifications.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2))
    (ROOT/'editable-type-layout.json').write_text(json.dumps(PLACED, ensure_ascii=False, indent=2))
    print(json.dumps(spec, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
