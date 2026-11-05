from pathlib import Path
from datetime import datetime,timezone
import fitz,json,hashlib,subprocess
from PIL import Image,ImageChops
R=Path(__file__).resolve().parent
O=Path('/workspace/book-work/output');ART=Path('/workspace/book-work/english-edition/modest-art')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 sources={k:json.loads((O/n).read_text()) for k,n in [('interior','latest-deliverable.json'),('cover','latest-cover-deliverable.json')]}
 for m in sources.values():assert sha(m['file'])==m['sha256']
 auth={'user_instruction':'give me the german version but only making the woman cover her chest as engilsh versoin ok , i think you can just change images no need for much right also for the cover ok','method':'Reuse the exact existing English-edition neckline artwork; replace images only; keep all German text and layout','recorded_at_utc':datetime.now(timezone.utc).isoformat(),'approved_assets':{n:sha(ART/n) for n in ['cover_modest.png','page_006_modest.png','page_081_modest.png']}}
 (R/'authorization.json').write_text(json.dumps(auth,indent=2))
 outputs={}
 for kind,meta in sources.items():
  src=Path(meta['file']);doc=fitz.open(src)
  filename='Wer_hat_den_Kommandanten_getoetet_Corrected_v11.pdf' if kind=='interior' else 'Wer_hat_den_Kommandanten_getoetet_Cover_KDP_FINAL_v5.pdf'
  out=R/filename;assert not out.exists(),'Preserve existing output'
  if kind=='interior':
   assert len(doc)==104
   for n in [6,81]:
    images=doc[n-1].get_image_info(xrefs=True);assert len(images)==1
    doc[n-1].replace_image(images[0]['xref'],stream=(ART/f'page_{n:03}_modest.png').read_bytes())
  else:
   english=fitz.open('/workspace/book-work/english-edition/cover-final-modest/Who_Killed_the_Commander_English_Cover.pdf')
   bg=fitz.Pixmap(english,english[0].get_images()[0][0]);old=fitz.Pixmap(doc,doc[0].get_images()[0][0])
   diff=ImageChops.difference(Image.frombytes('RGB',(old.width,old.height),old.samples),Image.frombytes('RGB',(bg.width,bg.height),bg.samples)).getbbox()
   assert diff==(2306,2025,3063,2596),diff
   doc[0].replace_image(doc[0].get_images()[0][0],stream=bg.tobytes('png'))
  doc.save(out,deflate=True,garbage=4);doc.close()
  before,after=fitz.open(src),fitz.open(out);changed=[]
  for n,(a,b) in enumerate(zip(before,after),1):
   assert a.rect==b.rect and a.mediabox==b.mediabox and a.cropbox==b.cropbox
   assert a.get_text(sort=True)==b.get_text(sort=True),('German text changed',kind,n)
   assert [x['bbox'] for x in a.get_image_info()]==[x['bbox'] for x in b.get_image_info()]
   if a.get_pixmap().samples!=b.get_pixmap().samples:changed.append(n)
  assert changed==([6,81] if kind=='interior' else [1])
  assert len(after)==(104 if kind=='interior' else 1)
  p=subprocess.run(['pdftotext','-enc','UTF-8',str(out),str(R/(kind+'_text_UTF8.txt'))],capture_output=True,text=True)
  assert p.returncode==0 and not p.stderr,p.stderr
  proofs=R/'proofs';proofs.mkdir(exist_ok=True)
  for n in ([6,81] if kind=='interior' else [1]):after[n-1].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(proofs/f'{kind}_page_{n:03}.png')
  outputs[kind]={'file':str(out),'filename':filename,'size_bytes':out.stat().st_size,'sha256':sha(out),'source_sha256':meta['sha256'],'page_count':len(after),'changed_pages':changed,'all_german_text_unchanged':True,'all_page_geometry_and_image_positions_unchanged':True,'other_pages_pixel_identical':True,'poppler_warnings_errors':0}
 report={'edition':'German','change':'Only Clara neckline images from English edition','interior':outputs['interior'],'cover':outputs['cover'],'german_text_unchanged':True,'interior_pages':104,'trim_inches':[6.25,9.25],'spine_mm':5.9488832,'cover_mm':[329.7988832,241.3],'old_files_preserved':True,'new_artwork_generated':False}
 (R/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':build()
