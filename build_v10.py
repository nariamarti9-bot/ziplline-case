"""Export v10 without reintroducing issues already repaired in the delivered PDF."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

ROOT = Path('/workspace/book-work/revision-10')
SOURCE = Path('/workspace/book-work/output/Wer_hat_den_Kommandanten_getoetet_Corrected_v9.pdf')
V3 = Path('/workspace/book-work/output/Wer_hat_den_Kommandanten_getoetet_Corrected_v3.pdf')
OUT = Path('/workspace/book-work/output/Wer_hat_den_Kommandanten_getoetet_Corrected_v10.pdf')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(text):
    return re.sub(r'\s+', '', text)


def build():
    assert sha(SOURCE) == '1ea72a262a5e5cc0d9e2164a1214f726ab7199641ded00812dd20517ecd501ec'
    assert sha(V3) == '23000633ef3d17326075a109876df65b49ec7a02919a7422f81eedee36b458b9'
    if OUT.exists():
        raise FileExistsError('Preserve existing v10; do not overwrite it')
    authorization = {
        'page14_decision': 'Keep the v9 restoration',
        'user_answer': 'Keep the v9 restoration',
        'result': 'Necklace edge and compact-mirror reflection both retained unchanged',
        'page4_source': str(V3),
        'new_artwork_generated': False,
        'page36_decision': 'Keep the existing torn lower stroke and matching scrap; verified by rendering',
    }
    (ROOT / 'decisions.json').write_text(json.dumps(authorization, ensure_ascii=False, indent=2))

    reader = PdfReader(SOURCE)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    # Decode the complete v3 page-4 illustration, then embed those exact RGB
    # samples losslessly. Do not import old fonts, OCR, clipping or page streams.
    old = fitz.open(V3)
    images = old[3].get_images(full=True)
    assert len(images) == 1
    pix = fitz.Pixmap(old, images[0][0])
    assert not pix.alpha and pix.colorspace.n == 3
    original_sample_hash = hashlib.sha256(pix.samples).hexdigest()
    image = DecodedStreamObject()
    image.set_data(pix.samples)
    image.update({
        NameObject('/Type'): NameObject('/XObject'),
        NameObject('/Subtype'): NameObject('/Image'),
        NameObject('/Width'): NumberObject(pix.width),
        NameObject('/Height'): NumberObject(pix.height),
        NameObject('/BitsPerComponent'): NumberObject(8),
        NameObject('/ColorSpace'): NameObject('/DeviceRGB'),
    })
    page = writer.pages[3]
    resources = DictionaryObject(dict(page['/Resources'].get_object()))
    xobjects = DictionaryObject(dict(resources['/XObject'].get_object()))
    image_names = [key for key, ref in xobjects.items()
                   if ref.get_object().get('/Subtype') == '/Image']
    assert len(image_names) == 1
    xobjects[image_names[0]] = writer._add_object(image.flate_encode())
    resources[NameObject('/XObject')] = xobjects
    page[NameObject('/Resources')] = resources

    # Explicitly clear only the tiny top-left corner above the page-35 header.
    page = writer.pages[34]
    data = page.get_contents().get_data()
    data += b'\nq 1 1 1 rg 0 649 50 17 re f Q\n'
    stream = DecodedStreamObject()
    stream.set_data(data)
    page[NameObject('/Contents')] = writer._add_object(stream.flate_encode())

    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    with OUT.open('wb') as handle:
        writer.write(handle)
    validate(original_sample_hash, [pix.width, pix.height])


def validate(original_sample_hash, image_dimensions):
    before, after, old = fitz.open(SOURCE), fitz.open(OUT), fitz.open(V3)
    assert len(before) == len(after) == 104 and not after.is_repaired
    visual_changes = []
    for number, (a, b) in enumerate(zip(before, after), 1):
        assert a.mediabox == b.mediabox == fitz.Rect(0, 0, 450, 666)
        assert a.cropbox == b.cropbox and a.bleedbox == b.bleedbox
        assert a.rotation == b.rotation
        assert a.get_text(sort=True) == b.get_text(sort=True), ('Text changed', number)
        if a.get_pixmap().samples != b.get_pixmap().samples:
            visual_changes.append(number)
        if number not in (4, 35):
            assert number not in visual_changes, ('Unexpected visual change', number)
            assert [(i['digest'], i['bbox']) for i in a.get_image_info(hashes=True)] == [
                (i['digest'], i['bbox']) for i in b.get_image_info(hashes=True)]
    # MuPDF scales JPEG and Flate streams through different sampling paths.
    # Identical decoded source pixels can therefore produce small differences
    # at page scale. Only page 4 is permitted to differ from the v9 rendering.
    assert set(visual_changes) <= {4}, ('Unexpected visual difference', visual_changes)
    p4images = after[3].get_images(full=True)
    assert len(p4images) == 1
    restored = fitz.Pixmap(after, p4images[0][0])
    assert hashlib.sha256(restored.samples).hexdigest() == original_sample_hash
    assert [restored.width, restored.height] == image_dimensions
    assert after[3].get_image_info(hashes=True)[0]['bbox'] == old[3].get_image_info(hashes=True)[0]['bbox']
    native = PdfReader(OUT)
    obj = next(x.get_object() for x in native.pages[3]['/Resources']['/XObject'].values()
               if x.get_object().get('/Subtype') == '/Image')
    assert obj['/ColorSpace'] == '/DeviceRGB' and obj['/Filter'] == '/FlateDecode'

    prior = json.loads(Path('/workspace/book-work/revision-9/validation-final.json').read_text())
    unique = sorted({(x['page'], x['target']) for x in prior['phrase_checks']})
    checks = []
    for number, target in unique:
        assert compact(target) in compact(after[number-1].get_text(sort=True))
        assert compact(target) in compact(native.pages[number-1].extract_text())
        checks.append({'page': number, 'target': target, 'present': True})
    text_path = ROOT / 'Verified_v10_text_UTF8.txt'
    result = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-layout', str(OUT), str(text_path)],
                            text=True, capture_output=True)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr)
    pages = text_path.read_text().split('\f')
    for number, target in unique:
        assert compact(target) in compact(pages[number-1])
    ascii_quotes, latex = [], []
    for n, page in enumerate(after, 1):
        text = page.get_text()
        if '"' in text:
            ascii_quotes.append(n)
        if any(token in text for token in ('\\prime', '$7^', 'GET TET', 'Schraubenschl ssel', 'abgerissenen  rmelknopf')):
            latex.append(n)
    assert not ascii_quotes and not latex
    corner = after[34].get_pixmap(matrix=fitz.Matrix(3, 3), clip=fitz.Rect(0, 0, 50, 17))
    assert set(corner.samples) == {255}

    proofs = ROOT / 'page-proofs'
    proofs.mkdir(exist_ok=True)
    for number in (4, 14, 35, 36, 94):
        after[number-1].get_pixmap(matrix=fitz.Matrix(1.7, 1.7)).save(proofs / f'v10_page_{number:03}.png')
    after[35].get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(47, 190, 285, 292)).save(proofs / 'v10_torn_47_closeup.png')
    after[13].get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(232, 177, 404, 431)).save(proofs / 'v10_necklace_preserved.png')
    after[93].get_pixmap(matrix=fitz.Matrix(3, 3), clip=fitz.Rect(32, 190, 416, 245)).save(proofs / 'v10_page94_sentence.png')
    run = subprocess.run(['pdftoppm', '-f', '4', '-l', '4', '-scale-to', '1500', '-png',
                          '-singlefile', str(OUT), str(proofs / 'v10_page004_poppler')],
                         capture_output=True, text=True)
    assert run.returncode == 0 and not run.stderr, (run.returncode, run.stderr)
    report = {
        'pdf': str(OUT), 'size_bytes': OUT.stat().st_size, 'sha256': sha(OUT),
        'source_pdf': str(SOURCE), 'source_sha256': sha(SOURCE), 'source_preserved': True,
        'page_count': 104, 'trim_points': [450, 666], 'bleed_and_crop_preserved': True,
        'structurally_modified_pages': [4, 35], 'visually_changed_pages': visual_changes,
        'other_103_pages_pixel_identical_to_v9_in_mupdf': True,
        'all_native_text_unchanged': True,
        'page4_complete_v3_image_reembedded': True,
        'page4_image_dimensions': image_dimensions,
        'page4_decoded_rgb_sha256': original_sample_hash,
        'page4_exact_v3_rgb_samples_preserved': True,
        'page4_encoding': 'DeviceRGB, lossless FlateDecode',
        'page35_top_left_corner_explicitly_cleared': True,
        'page14_v9_restoration_preserved_as_user_requested': True,
        'page36_torn_digit_and_matching_scrap_preserved': True,
        'page94_exact_requested_sentence_verified': True,
        'ascii_double_quote_pages': ascii_quotes, 'raw_latex_or_known_broken_umlaut_pages': latex,
        'checked_phrases': len(unique), 'reader_phrase_checks_passed': 3 * len(unique),
        'missing_required_text_or_umlaut_sequence_count': 0,
        'poppler_warnings_errors': 0, 'new_artwork_generated': False,
        'scope_note': 'v9 already rendered the full blueprint, torn 7 and corrected text. v10 re-embeds the blueprint losslessly and explicitly clears the corner; no repeated text/art edits were needed.',
        'phrase_checks': checks,
    }
    (ROOT / 'validation-final.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (ROOT / 'build-final.json').write_text(json.dumps({k: v for k, v in report.items() if k != 'phrase_checks'}, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'phrase_checks'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
