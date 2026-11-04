"""Remove the PDF-drawn white rectangle; reveal the existing cover artwork."""
from pathlib import Path
import hashlib,json,shutil
import fitz
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ContentStream,DecodedStreamObject,NameObject

ROOT=Path(__file__).resolve().parent
SOURCE=Path('/workspace/book-work/cover-v3/Wer_hat_den_Kommandanten_Cover_REVIEW_v3.pdf')
OUT=ROOT/'Wer_hat_den_Kommandanten_Cover_REVIEW_v4.pdf'
ART=Path('/workspace/book-work/cover-v3/Cover_Illustration_v3.png')

def main():
 ROOT.mkdir(exist_ok=True)
 assert not OUT.exists(),'Preserve existing v4 source'
 assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='ec618ef9d522975ef83cfd92bd417b94bc73e6128c89373e09ad4a108ddb9a13'
 reader=PdfReader(SOURCE);content=ContentStream(reader.pages[0].get_contents(),reader)
 depth=0;start=None;matches=[]
 for index,(args,op) in enumerate(content.operations):
  if op==b'q':
   if depth==0:start=index
   depth+=1
  elif op==b'Q':
   depth-=1
   if depth==0:
    group=content.operations[start:index+1]
    rectangles=[list(map(float,a)) for a,o in group if o==b're']
    white=any(o==b'rg' and list(map(float,a))==[1,1,1] for a,o in group)
    target=[297,27,144,86.4]
    if white and len(rectangles)==1 and all(abs(a-b)<.02 for a,b in zip(rectangles[0],target)):
     assert not any(o in (b'BT',b'Do') for a,o in group)
     assert any(o==b'f' for a,o in group)
     matches.append((start,index))
 assert depth==0 and len(matches)==1,matches
 start,end=matches[0]
 content.operations=content.operations[:start]+content.operations[end+1:]
 writer=PdfWriter();writer.clone_document_from_reader(reader)
 stream=DecodedStreamObject();stream.set_data(content.get_data())
 writer.pages[0][NameObject('/Contents')]=writer._add_object(stream.flate_encode())
 writer.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
 with OUT.open('wb') as handle:writer.write(handle)
 shutil.copy2(ART,ROOT/'Cover_Illustration_v4.png')
 before,after=fitz.open(SOURCE),fitz.open(OUT)
 assert before[0].rect==after[0].rect
 assert before[0].get_text(sort=True)==after[0].get_text(sort=True)
 assert before[0].get_image_info(hashes=True)[0]['digest']==after[0].get_image_info(hashes=True)[0]['digest']
 report={'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
         'pdf':str(OUT),'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
         'artwork_sha256':hashlib.sha256(ART.read_bytes()).hexdigest(),
         'removed_graphics_groups':1,'removed_pdf_rectangle':[297,27,144,86.4],
         'all_native_text_unchanged':True,'original_artwork_unchanged':True,
         'new_artwork_generated':False,'method':'Delete the native PDF rectangle and re-export the existing artwork'}
 (ROOT/'source-removal-verification.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
