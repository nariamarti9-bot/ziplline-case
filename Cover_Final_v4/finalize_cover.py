"""Prepare the approved KDP cover, preserving its live Unicode text.

Artwork is conventionally upscaled, not regenerated. Its original resolution
is retained in the production record. The interior and review files are read-only.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import subprocess

import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject

ROOT = Path(__file__).resolve().parent
NAME = 'Wer_hat_den_Kommandanten_getoetet_Cover_KDP_FINAL_v4.pdf'
OUT = ROOT/NAME
W, H = 934.862976, 684.0
FRONT = fitz.Rect(475.862976, 9, 925.862976, 675)
BACK = fitz.Rect(9, 9, 459, 675)
SPINE = fitz.Rect(459, 9, 475.862976, 675)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stream(writer, data):
    obj = DecodedStreamObject()
    obj.set_data(data)
    return writer._add_object(obj.flate_encode())


def rgb_image(writer, width, height, samples):
    obj = DecodedStreamObject()
    obj.set_data(samples)
    obj.update({NameObject('/Type'): NameObject('/XObject'),
                NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(width), NameObject('/Height'): NumberObject(height),
                NameObject('/BitsPerComponent'): NumberObject(8),
                NameObject('/ColorSpace'): NameObject('/DeviceRGB')})
    return writer._add_object(obj.flate_encode())


def encode_ops(ops, pdf):
    content = ContentStream(None, pdf)
    content.operations = ops
    return content.get_data()


def split_graphics_groups(content):
    groups, active, depth = [], [], 0
    for args, op in content.operations:
        if op == b'q':
            depth += 1
        assert depth > 0, ('Unexpected unsaved graphics state', op)
        active.append((args, op))
        if op == b'Q':
            depth -= 1
            if depth == 0:
                groups.append(active)
                active = []
    assert depth == 0 and not active
    texts = [g for g in groups if any(op == b'BT' for args, op in g)]
    graphics = [g for g in groups if not any(op == b'BT' for args, op in g)]
    assert texts and graphics
    assert all(not any(op in (b'gs', b'Do') for args, op in g) for g in texts)
    return texts, graphics


def main(review_root):
    ROOT.mkdir(exist_ok=True)
    if OUT.exists():
        raise FileExistsError('Preserve the existing final cover; use a new version')
    review = review_root/'Wer_hat_den_Kommandanten_Cover_REVIEW_v4.pdf'
    art = review_root/'Cover_Illustration_v4.png'
    assert sha(review) == '2ce3992b6255031a29db5e751b36ca224591c663ba5fd509adefbac90ae2edd9'
    assert sha(art) == 'f04130972a7d522f9b5ab408f82ed327250644ebf4df76ad83de01a3a43662ef'
    approval = {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'authorized barcode placeholder removal and finalization',
        'user_reply': 'remove the barcode white square ok amazon will put it there',
        'reply_context': 'User requested removal of the white barcode rectangle from cover v3. Preserve all lettering, artwork, dimensions and prior print settings.',
        'interpretation': 'Direct authorization to remove the native PDF barcode placeholder; reveal the existing artwork beneath it. Amazon will supply its own barcode.',
        'approved_review_pdf_sha256': sha(review),
        'approved_artwork_sha256': sha(art),
        'author': 'Elizabeth Erin',
        'printer': 'Amazon KDP paperback — standard colour, white paper',
        'new_artwork_generated': False,
    }
    # Record approved assets before placing anything in the final cover.
    (ROOT/'artwork-approval.json').write_text(json.dumps(approval, ensure_ascii=False, indent=2))

    dimensions = (math.ceil(W/72*300), math.ceil(H/72*300))
    original = Image.open(art).convert('RGB')
    assert original.size == (1466, 1073)
    resized = original.resize(dimensions, Image.Resampling.LANCZOS)
    resized.save(ROOT/'Approved_Artwork_Upscaled_300dpi.png', dpi=(300,300))

    reader = PdfReader(review)
    text_groups, graphic_groups = split_graphics_groups(ContentStream(reader.pages[0].get_contents(), reader))
    text_ops = [operation for group in text_groups for operation in group]
    graphic_ops = [operation for group in graphic_groups for operation in group]

    # Rasterize only the approved background and non-text design elements.
    # This flattens the translucent lower band while keeping all text sharp.
    bg = PdfWriter()
    bg.clone_document_from_reader(reader)
    bg_page = bg.pages[0]
    resources = DictionaryObject(dict(bg_page['/Resources'].get_object()))
    xobjects = DictionaryObject(dict(resources['/XObject'].get_object()))
    assert len(xobjects) == 1
    key = next(iter(xobjects))
    xobjects[key] = rgb_image(bg, *resized.size, resized.tobytes())
    resources[NameObject('/XObject')] = xobjects
    bg_page[NameObject('/Resources')] = resources
    # Fill the full bleed rectangle. Review placement left a 0.49 pt margin
    # because of its image aspect ratio; print placement fills all four edges.
    image_group = next(g for g in graphic_groups if any(op == b'Do' for args,op in g))
    assert sum(op == b'cm' for args,op in image_group) == 1
    for index, (args, op) in enumerate(graphic_ops):
        if op == b'cm':
            graphic_ops[index] = ([FloatObject(W),NumberObject(0),NumberObject(0),FloatObject(H),NumberObject(0),NumberObject(0)], b'cm')
            break
    bg_page[NameObject('/Contents')] = stream(bg, encode_ops(graphic_ops, bg))
    bg_path = ROOT/'Background_Flattening_Working.pdf'
    with bg_path.open('wb') as handle:
        bg.write(handle)
    with fitz.open(bg_path) as bg_doc:
        assert not bg_doc[0].get_text().strip()
        pix = bg_doc[0].get_pixmap(dpi=300, alpha=False)
    assert (pix.width,pix.height) == dimensions and pix.n == 3
    pix.save(ROOT/'Cover_Background_Flattened_300dpi.png')

    final = PdfWriter()
    final.clone_document_from_reader(reader)
    page = final.pages[0]
    old_resources = page['/Resources'].get_object()
    resources = DictionaryObject({NameObject('/Font'): old_resources['/Font']})
    image_ref = rgb_image(final, pix.width, pix.height, pix.samples)
    resources[NameObject('/XObject')] = DictionaryObject({NameObject('/PrintBackground'): image_ref})
    page[NameObject('/Resources')] = resources
    if '/Group' in page:
        del page['/Group']
    background_command = f'q {W:.6f} 0 0 {H:.6f} 0 0 cm /PrintBackground Do Q\n'.encode()
    page[NameObject('/Contents')] = stream(final, background_command+encode_ops(text_ops, final))
    final.add_metadata({'/Title': 'Wer hat den Kommandanten getötet? — KDP Cover',
                        '/Author': 'Elizabeth Erin',
                        '/Subject': '104-page standard-colour white-paper paperback; 6.25 × 9.25 inch trim',
                        '/Keywords': 'Approved cover; conventionally upscaled background; live embedded-font text; 300 dpi export'})
    final.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
    with OUT.open('wb') as handle:
        final.write(handle)
    validate(review,art,dimensions,text_groups)


def validate(review,art,dimensions,text_groups):
    before, after = fitz.open(review), fitz.open(OUT)
    assert len(after) == 1 and not after.is_repaired
    page = after[0]
    assert abs(page.rect.width-W) < .001 and page.rect.height == H
    assert page.get_text(sort=True) == before[0].get_text(sort=True), 'Approved wording changed'
    assert len(page.get_images(full=True)) == 1
    image = page.get_image_info()[0]
    assert image['bbox'] == (0.0,0.0,page.rect.width,H)
    assert image['width'] == dimensions[0] and image['height'] == dimensions[1]
    assert not any(key in page.get_text() for key in ('\ufffd','\x00','REVIEW','DRAFT'))
    assert all(after.extract_font(font[0])[3] for font in page.get_fonts(full=True))
    # All text bounds stay within the original safe front/back panels and spine.
    spans = []
    for block in page.get_text('dict')['blocks']:
        for row in block.get('lines',[]):
            for span in row['spans']:
                box = fitz.Rect(span['bbox'])
                assert page.rect.contains(box)
                if row['dir'] == (0.0,1.0):
                    assert box.x0 >= SPINE.x0+4.5-.03 and box.x1 <= SPINE.x1-4.5+.03
                elif box.x1 < SPINE.x0:
                    assert box.x0 >= BACK.x0+9 and box.x1 <= BACK.x1-9
                    assert box.y0 >= BACK.y0+9 and box.y1 <= BACK.y1-9
                else:
                    assert box.x0 >= FRONT.x0+9 and box.x1 <= FRONT.x1-9
                    assert box.y0 >= FRONT.y0+9 and box.y1 <= FRONT.y1-9
                spans.append(span)
    native = PdfReader(OUT)
    assert '/ExtGState' not in native.pages[0]['/Resources']
    assert not native.pages[0].get('/Annots')
    raw_image = next(iter(native.pages[0]['/Resources']['/XObject'].values())).get_object()
    assert '/SMask' not in raw_image and '/Mask' not in raw_image
    assert '/OCProperties' not in native.trailer['/Root']
    assert native.pages[0].extract_text() == PdfReader(review).pages[0].extract_text()
    textfile = ROOT/'Cover_text_UTF8.txt'
    result = subprocess.run(['pdftotext','-enc','UTF-8','-layout',str(OUT),str(textfile)],capture_output=True,text=True)
    assert result.returncode == 0 and not result.stderr, result.stderr
    compact = lambda s: ''.join(s.split())
    for expected in ('GETÖTET?','ELIZABETH ERIN','18 KRIMINALFÄLLE ZUM SELBERLÖSEN',
                     'ÜBER DEM ATLANTIK','Sie sind an Bord. Und Sie ermitteln.',
                     'Wer hat den Kommandanten getötet?'):
        assert compact(expected) in compact(textfile.read_text())
    proofs = ROOT/'proofs'
    proofs.mkdir(exist_ok=True)
    for filename,clip,scale in [('Cover_Full_Wrap_FINAL.png',page.rect,1.6),
                                ('Cover_Front_FINAL.png',FRONT,2),('Cover_Back_FINAL.png',BACK,2)]:
        page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=clip).save(proofs/filename)
    result = subprocess.run(['pdftoppm','-scale-to','1800','-singlefile','-png',str(OUT),str(proofs/'Cover_Poppler_FINAL')],capture_output=True,text=True)
    assert result.returncode == 0 and not result.stderr, result.stderr
    record = {
        'status':'Barcode placeholder removed from v3; existing artwork restored underneath',
        'pdf':str(OUT),'size_bytes':OUT.stat().st_size,'sha256':sha(OUT),
        'author':'Elizabeth Erin','title':'Wer hat den Kommandanten getötet?',
        'printer':'Amazon KDP','binding':'paperback','interior_colour':'standard colour, white paper',
        'interior_page_count':104,'trim_inches':[6.25,9.25],'bleed_inches':.125,
        'spine_inches':104*.002252,'spine_mm':104*.002252*25.4,
        'full_cover_inches':[W/72,H/72],'full_cover_mm':[W/72*25.4,H/72*25.4],
        'pdf_dimensions_points':[W,H],'cover_page_count':1,
        'background_pixels':list(dimensions),'effective_background_ppi':[dimensions[0]/(W/72),dimensions[1]/(H/72)],
        'original_artwork_pixels':[1466,1073],'original_artwork_ppi':112.90638597286795,
        'resampling':'Pillow Lanczos conventional resizing followed by 300-dpi background flattening',
        'resolution_disclosure':'The background is upscaled from the approved 1466 × 1073 px artwork. The export does not create original image detail. All cover text remains vector text.',
        'all_approved_text_identical':True,'all_fonts_embedded':True,'unicode_checks_passed':True,
        'background_opaque':True,'transparency_flattened':True,'full_bleed_background':True,
        'text_safe_margins_verified':True,'barcode_rectangle_removed':True,
        'barcode_placeholder_drawn':False,'fake_isbn_or_barcode_created':False,
        'native_text_groups_preserved':len(text_groups),'poppler_warnings_errors':0,
        'new_artwork_generated':False,'artwork_approval_record':'artwork-approval.json',
        'review_pdf_preserved_sha256':sha(review),'original_artwork_preserved_sha256':sha(art),
        'interior_modified':False,
    }
    (ROOT/'production-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print(json.dumps(record,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--review-root',type=Path,default=Path('/workspace/book-work/cover-v4'))
    main(parser.parse_args().review_root)
