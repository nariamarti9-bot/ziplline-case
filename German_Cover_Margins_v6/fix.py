from pathlib import Path
import json,hashlib,subprocess
import fitz
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ContentStream,DecodedStreamObject,FloatObject,NameObject
R=Path(__file__).resolve().parent
meta=json.load(open('/workspace/book-work/output/latest-cover-deliverable.json'));src=Path(meta['file']);assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
out=R/'Wer_hat_den_Kommandanten_getoetet_Cover_KDP_FINAL_v6.pdf';assert not out.exists()
r=PdfReader(src);w=PdfWriter();w.clone_document_from_reader(r);p=w.pages[0];cs=ContentStream(p.get_contents(),w)
groups=[];g=[];depth=0
for args,op in cs.operations:
 if op==b'q':depth+=1
 g.append((args,op))
 if op==b'Q':
  depth-=1
  if depth==0:groups.append(g);g=[]
assert not g and not depth
ops=[];changes=[]
for g in groups:
 if not any(op==b'BT' for a,op in g):
  ops.extend(g)
  if any(op==b'Do' for a,op in g):
   # Extend the existing dark lower-front title band upward; no illustration editing.
   ops.extend([([],b'q'),([FloatObject(.09),FloatObject(.025),FloatObject(.035)],b'rg'),([FloatObject(475.862976),FloatObject(0),FloatObject(459),FloatObject(84)],b're'),([],b'f'),([],b'Q')])
  continue
 tm=next(a for a,op in g if op==b'Tm');x=float(tm[4]);y=684-float(tm[5]);matrix=None
 rotated=any(op==b'cm' for a,op in g)
 if not rotated and x>475.862976:
  if y<194:
   # Scale the four-line front title/author block about its horizontal center.
   s=.9;matrix=[s,0,0,s,700.862976*(1-s),684*(1-s)-27]
  elif y>620:matrix=[1,0,0,1,0,20]
 elif not rotated and x<459 and y<180:matrix=[.9,0,0,.9,4.2,684*.1-26]
 if matrix:
  ops.extend([([],b'q'),([FloatObject(z) for z in matrix],b'cm')]);ops.extend(g);ops.append(([],b'Q'));changes.append({'anchor':[x,y],'matrix':matrix})
 else:ops.extend(g)
cs.operations=ops
encoded=DecodedStreamObject();encoded.set_data(cs.get_data());p[NameObject('/Contents')]=w._add_object(encoded.flate_encode())
with out.open('wb') as f:w.write(f)
a=fitz.open(src);b=fitz.open(out);page=b[0];assert page.rect==a[0].rect
assert page.get_text()==a[0].get_text(),'Text content changed'
assert [i['digest'] for i in page.get_image_info(hashes=True)]==[i['digest'] for i in a[0].get_image_info(hashes=True)]
violations=[];measured=[]
for block in page.get_text('dict')['blocks']:
 for line in block.get('lines',[]):
  for span in line['spans']:
   box=fitz.Rect(span['bbox'])
   if line['dir']==(0.,1.):
    safe=fitz.Rect(463.5,36,471.362976,648);panel='spine'
   else:
    safe=fitz.Rect(36,36,432,648) if box.x1<459 else fitz.Rect(502.862976,36,898.862976,648);panel='back' if box.x1<459 else 'front'
   if not safe.contains(box):violations.append({'text':span['text'],'bbox':list(box),'safe':list(safe)})
   measured.append({'panel':panel,'text':span['text'],'bbox':list(box)})
assert not violations,violations
assert all(b.extract_font(font[0])[3] for font in page.get_fonts(full=True))
proof=R/'proofs';proof.mkdir(exist_ok=True)
page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(proof/'cover.png')
# Separate proof contains guides; print PDF does not.
for rect in [fitz.Rect(36,36,432,648),fitz.Rect(502.862976,36,898.862976,648)]:page.draw_rect(rect,color=(0,1,0),width=.8,dashes='[4 3]')
page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(proof/'cover_safety_guides.png')
pop=subprocess.run(['pdftotext',str(out),str(R/'cover_text.txt')],capture_output=True,text=True);assert pop.returncode==0 and not pop.stderr
report={'file':str(out),'filename':out.name,'size_bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_file':str(src),'source_sha256':meta['sha256'],'page_count':1,'interior_pages':104,'trim_inches':[6.25,9.25],'cover_dimensions_points':list(b[0].rect)[2:],'safe_inset_from_panel_trim_inches':.375,'safe_inset_from_outer_pdf_edge_inches':.5,'spine_side_clearance_inches':.0625,'violations':violations,'all_text_preserved':True,'original_artwork_preserved':True,'all_fonts_embedded':True,'text_bounds':measured,'changes':'Inset front title, author, lower subtitles and back top tagline; extend lower front dark band upward. Preserve modest neckline and no barcode placeholder.'}
(R/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));print(json.dumps({k:v for k,v in report.items() if k!='text_bounds'},indent=2))
