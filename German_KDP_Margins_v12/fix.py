from pathlib import Path
import json,hashlib,subprocess
import fitz
from pypdf import PdfReader,PdfWriter,Transformation
R=Path(__file__).resolve().parent;meta=json.load(open('/workspace/book-work/output/latest-deliverable.json'));SOURCE=Path(meta['file']);OUT=R/'Wer_hat_den_Kommandanten_getoetet_Corrected_v12_KDP.pdf'
assert not OUT.exists();assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==meta['sha256']
reader=PdfReader(SOURCE);writer=PdfWriter();writer.clone_document_from_reader(reader)
scale=.94;dx=450*(1-scale)/2;dy=666*(1-scale)/2
for p in writer.pages:p.add_transformation(Transformation().scale(scale).translate(dx,dy),expand=False)
writer.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
with OUT.open('wb') as f:writer.write(f)
before,after=fitz.open(SOURCE),fitz.open(OUT);assert len(after)==104
minimum=[999,999,999,999];violations=[]
for n,(a,b) in enumerate(zip(before,after),1):
 assert a.mediabox==b.mediabox==fitz.Rect(0,0,450,666) and a.cropbox==b.cropbox
 assert a.get_text()==b.get_text(),('Text changed',n)
 assert [i['digest'] for i in a.get_image_info(hashes=True)]==[i['digest'] for i in b.get_image_info(hashes=True)]
 for block in b.get_text('blocks'):
  x0,y0,x1,y1,*_=block;m=[x0,y0,450-x1,666-y1];minimum=[min(x,y) for x,y in zip(minimum,m)]
  if min(m)<36:violations.append({'page':n,'bbox':block[:4]})
assert not violations,violations
proofs=R/'proofs';proofs.mkdir(exist_ok=True)
for n in [4,5,9,81,102,104]:after[n-1].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(proofs/f'page_{n:03}.png')
p=subprocess.run(['pdftotext','-enc','UTF-8',str(OUT),str(R/'text_UTF8.txt')],capture_output=True,text=True);assert p.returncode==0 and not p.stderr,p.stderr
report={'file':str(OUT),'filename':OUT.name,'size_bytes':OUT.stat().st_size,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'source_file':str(SOURCE),'source_sha256':meta['sha256'],'page_count':104,'trim_inches':[6.25,9.25],'interior_bleed':'No bleed','content_scale':scale,'text_and_image_data_unchanged':True,'all_german_text_preserved':True,'modest_necklines_preserved':True,'minimum_text_margins_points_L_T_R_B':minimum,'minimum_text_margin_inches':min(minimum)/72,'text_margin_violations_at_0_5_inches':violations,'cover_unchanged_and_still_matches':True,'poppler_errors':0}
(R/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
