#!/usr/bin/env python3
"""Reissue the requested Zipline text using fresh, complete Unicode fonts.

Dependencies: pymupdf, fonttools, pypdf. No artwork is rasterized or modified.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import unicodedata

import fitz
from fontTools.ttLib import TTFont
from pypdf import PdfReader

QUOTE_CHECKS = {
 9:['Schraubenschlüssel „K-7“.'],
 24:['Rückseite ist „16. Oktober 1934“ notiert.'],
 25:['Fabrikantensohn Pohl: „Ich wollte'],
 30:['Das Namensschild lautet „Kroll“.'],
 50:['Maschinist Greve: „Ich habe'],
 54:['Kommandant von Berg: „Ich hatte'],
 61:['kleinen „e“ fehlt'],
 64:['Kleinbuchstaben „e“ der untere','makelloses „e“,'],
 69:['Takler Holm: „Ich war'],
 75:['Warum „23:38“ vor „23:32“ gestempelt'],
 80:['Papierrest „Treffpunkt Kartenraum: 23:40 Uhr“; Rückseite: „16. Oktober 1934“.',
     'Der Stempel „23:38 Uhr - Schlüssel 2“'],
 81:['lautet „Der Albatros“.','steckt in „ALBATROS-SAND 1931“,','Mörder („Der Albatros“),'],
 83:['Mörders („Der Albatros“):'],
 87:['noch immer „4,2 Bar Normaldruck“'],
 88:['Decknamen „DER ALBATROS“','Seegebiet „Albatros-Sand 1931“?'],
 91:['Buchstaben „e“'],
 95:['Kaliber „6,35 mm“.'],
 97:['starr auf „4,2 Bar Normaldruck“,'],
 98:['Herzgift „Akonitin“'],
 99:['Buchstaben „e“)','Steck-Typenkopf „e“ ab'],
 100:['um „23:38 Uhr“ eingestempelt','(„23:38 Uhr - Schlüssel 2“)',
      'deshalb „23:38 Uhr“.','Stechuhr-Alibi „23:38 Uhr“'],
}
CANONICAL = {
 101:['WER HAT DEN KOMMANDANTEN GETÖTET?'],
 102:[
  'WER HAT DEN KOMMANDANTEN GETÖTET?',
  'Die lückenlose Beweiskette gegen Viktor Krantz („Der Albatros“)',
  'Alle 18 Fälle dieses Buches fügen sich zu einem einzigen großen Mosaik zusammen:',
  '1. Die Sabotage & Ablenkung (Fälle 1, 8, 11): Mit dem entwendeten Schraubenschlüssel „K-7“ und bestochenen Mechanikern sorgte Krantz für technische Zwischenfälle, um den Kommandanten und den Sonderermittler in Atem zu halten.',
  '2. Das Erpressernetz (Fälle 2, 3, 7, 9, 10, 14): Um seine Flucht nach Südamerika zu finanzieren und Zeugen von 1931 mundtot zu machen, ließ Krantz („V. K.“) durch die Sekretärin Fräulein Mercier Erpresserbriefe mit dem defekten „e“ tippen, durch Steward Marek die Konstruktionsverträge von Bankier Vance stehlen (wobei Marek einen Manschettenknopf „V. K.“ verlor) und durch Frau Blum die alten Reederei-Pfandbriefe von 1931 rauben.',
  '3. Die Vertuschung (Fälle 4 & 12): Als Scotland Yard per Funk vor dem „Albatros“ warnte, ließ Krantz das Telegramm durch den erpressbaren Navigator Sorge vernichten und brach selbst mit seiner Goldfeder den Archivschrank auf, um die Logbuchseite vom 18. November 1931 zu stehlen.',
 ],
 103:['WER HAT DEN KOMMANDANTEN GETÖTET?','abgerissenen Ärmelknopf'],
 104:[
  'Hiermit wird feierlich bestätigt, dass',
  '(Name des Sonderermittlers / der Sonderermittlerin)',
  'an Bord des Transatlantik-Luftschiffs LZ Viktoria (1934) sämtliche 18 Kriminalfälle mit unbestechlicher Schärfe gelöst, das Netz der Lügen und Sabotageakte durchbrochen und den Mörder des Kommandanten („Der Albatros“) vor der Landung in Lakehurst überführt hat.',
 ],
 94:['mit der unteren Hälfte einer roten Ziffer „7“.'],
}
PAGES=sorted(set(QUOTE_CHECKS)|set(CANONICAL)|{35})
BAD=['GET TET','l ckenlose','Flle','Schraubenschl ssel','Frulein',
     'abgerissenen  rmelknopf','besttigt','M rder',r'$7^{\prime\prime}$']
GERMAN='äöüÄÖÜß„“'
compact=lambda t:re.sub(r'\s+','',unicodedata.normalize('NFC',t))

def style(font):
 bold='Bold' in font
 italic='Italic' in font or 'Oblique' in font
 return 'bi' if bold and italic else 'b' if bold else 'i' if italic else 'r'

def prepare_fonts(folder):
 folder.mkdir(exist_ok=True)
 result={}
 for code,suffix,label in [('r','','Regular'),('b','-Bold','Bold'),('i','-Italic','Italic'),('bi','-BoldItalic','BoldItalic')]:
  source=Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSerif'+suffix+'.ttf')
  font=TTFont(source)
  names={1:'ZiplineV6Serif',2:label,
         3:'ZiplineV6Serif-'+label+'-Full',
         4:'ZiplineV6Serif-'+label,
         6:'ZiplineV6Serif-'+label,
         16:'ZiplineV6Serif',17:label}
  for entry in font['name'].names:
   if entry.nameID in names:entry.string=names[entry.nameID].encode(entry.getEncoding())
  path=folder/('ZiplineUnicodeV6-'+label+'.ttf')
  font.save(path)
  cmap=font.getBestCmap()
  assert all(ord(c) in cmap for c in GERMAN)
  result[code]={'path':path,'font':fitz.Font(fontfile=str(path)),
                'resource':'ZiplineUnicodeV6'+code,'xrefs':set(),'used':Counter()}
 return result

def ordered_segments(page):
 """Merge spatially adjacent spans, including old appended quote objects."""
 rows=[]
 for block in page.get_text('rawdict')['blocks']:
  if 'lines' not in block:continue
  for line in block['lines']:
   for span in line['spans']:
    for c in span['chars']:
     y=c['origin'][1]
     row=next((r for r in rows if abs(r['y']-y)<.14),None)
     if row is None:row={'y':y,'chars':[]};rows.append(row)
     row['chars'].append({'c':unicodedata.normalize('NFC',c['c']),
        'x':c['origin'][0],'bbox':list(c['bbox']),
        'size':float(span['size']),'style':style(span['font']),
        'color':int(span['color'])})
 result=[]
 for row in sorted(rows,key=lambda r:r['y']):
  chars=sorted(row['chars'],key=lambda c:c['x'])
  groups=[];current=[]
  for c in chars:
   if current and c['x']-current[-1]['bbox'][2]>max(8,1.2*c['size']):
    groups.append(current);current=[]
   current.append(c)
  if current:groups.append(current)
  for chars in groups:
   # Remove spacing artifacts around quotation marks and punctuation that
   # originated in individually positioned legacy quote objects.
   chars=[c for k,c in enumerate(chars) if not (
    c['c'].isspace() and (
     (k+1<len(chars) and chars[k+1]['c'] in '“.,;:!?)]') or
     (k>0 and chars[k-1]['c']=='„')))]
   if not chars:continue
   value=''.join(c['c'] for c in chars)
   if page.number==34 and row['y']<20 and chars[0]['x']<60 and value.strip()=='op':continue
   # The prior export had separately transformed closing quotes. Give those
   # glyphs the surrounding line's actual type size in the new text stream.
   sizes=Counter(round(c['size'],2) for c in chars if c['c'] not in '„“ ')
   dominant=sizes.most_common(1)[0][0] if sizes else chars[0]['size']
   for c in chars:
    if c['c'] in '„“' and abs(c['size']-dominant)<1:c['size']=dominant
   result.append({'y':row['y'],'left':chars[0]['x'],
     'right':max(c['bbox'][2] for c in chars),'chars':chars})
 return result

def canonicalize(segments,page):
 atoms=[c for row in segments for c in row['chars'] if not c['c'].isspace()]
 def flat():return ''.join(c['c'] for c in atoms)
 # Honor the exact stamp punctuation and place-name case supplied by the user.
 substitutions=[]
 if page in [80,100]:substitutions.append(('„23:38Uhr–Schlüssel2“','„23:38Uhr-Schlüssel2“'))
 if page==88:substitutions.append(('„ALBATROS-SAND1931“','„Albatros-Sand1931“'))
 for old,new in substitutions:
  while old in flat():
   start=flat().index(old);assert len(old)==len(new)
   for c,char in zip(atoms[start:start+len(old)],new):c['c']=char
 checks=CANONICAL.get(page,[])+QUOTE_CHECKS.get(page,[])
 reissued=[]
 for target in checks:
  needle=compact(target)
  # Every requested clean phrase is supplied explicitly, not recovered from
  # a possibly broken font decoder at export time.
  assert needle in flat(),('Canonical text not located for safe replacement',page,target)
  start=flat().index(needle)
  for atom,char in zip(atoms[start:start+len(needle)],needle):atom['c']=char
  reissued.append(target)
 return reissued

def write_segment(page,row,fonts):
 runs=[]
 for c in row['chars']:
  key=(c['style'],round(c['size'],3),c['color'])
  if runs and runs[-1]['key']==key:runs[-1]['text']+=c['c']
  else:runs.append({'key':key,'text':c['c']})
 natural=sum(fonts[s]['font'].text_length(r['text'],fontsize=z) for r in runs for s,z,_ in [r['key']])
 # A short ragged line can use the remaining body margin; its old right edge
 # must not force natural quotation marks into the old ASCII glyph width.
 available=max(row['right']-row['left'],415-row['left'])
 scale=min(1.0,(available+.12)/natural) if natural else 1.0
 assert scale>.94,('Excessive horizontal fit',page.number+1,scale,''.join(r['text'] for r in runs))
 x=row['left']
 if row['left']>50 and abs((row['left']+row['right'])/2-225)<2:
  x=225-natural*scale/2
 for run in runs:
  s,z,color=run['key'];f=fonts[s]
  assert all(f['font'].has_glyph(ord(c)) for c in run['text'] if not c.isspace()),run['text']
  f['used'].update(ord(c) for c in run['text'])
  rgb=((color>>16&255)/255,(color>>8&255)/255,(color&255)/255)
  origin=fitz.Point(x,row['y'])
  page.insert_text(origin,run['text'],fontname=f['resource'],fontsize=z,color=rgb,
                   morph=(origin,fitz.Matrix(scale,1)))
  x+=f['font'].text_length(run['text'],fontsize=z)*scale
 return scale

def private_font_resources(doc,page,refs):
 kind,value=doc.xref_get_key(page.xref,'Resources')
 assert kind in ['dict','xref'],(kind,value)
 resource=doc.xref_object(int(value.split()[0])) if kind=='xref' else value
 xref=doc.get_new_xref();doc.update_object(xref,resource)
 doc.xref_set_key(xref,'Font','<< '+' '.join('/'+name+' '+str(ref)+' 0 R' for name,ref in refs.items())+' >>')
 doc.xref_set_key(page.xref,'Resources',str(xref)+' 0 R')

def install_valid_unicode_maps(doc,fonts):
 for code,f in fonts.items():
  ttf=TTFont(f['path']);cmap=ttf.getBestCmap();by_gid={}
  for cp,name in sorted(cmap.items()):by_gid.setdefault(ttf.getGlyphID(name),cp)
  for cp,count in sorted(f['used'].items(),key=lambda item:item[1]):
   assert cp in cmap
   gid=ttf.getGlyphID(cmap[cp]);assert gid==f['font'].has_glyph(cp)
   by_gid[gid]=cp
  mappings=[f'<{gid:04X}> <{chr(cp).encode("utf-16-be").hex().upper()}>' for gid,cp in sorted(by_gid.items()) if gid]
  lines=['/CIDInit /ProcSet findresource begin','12 dict begin','begincmap',
    '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
    '/CMapName /ZiplineV6-'+code+'-UCS def','/CMapType 2 def',
    '1 begincodespacerange','<0000> <FFFF>','endcodespacerange']
  for i in range(0,len(mappings),100):
   block=mappings[i:i+100]
   lines += [str(len(block))+' beginbfchar',*block,'endbfchar']
  lines+=['endcmap','CMapName currentdict /CMap defineresource pop','end','end']
  data=('\n'.join(lines)+'\n').encode('ascii')
  for ref in f['xrefs']:
   key,value=doc.xref_get_key(ref,'ToUnicode');assert key=='xref'
   doc.update_stream(int(value.split()[0]),data,compress=True)
   kind,descendants=doc.xref_get_key(ref,'DescendantFonts');assert kind=='array'
   descendant=int(re.search(r'(\d+)\s+0\s+R',descendants).group(1))
   doc.xref_set_key(descendant,'CIDToGIDMap','/Identity')

def repair_legacy_unicode_maps(doc):
 seen=set();repaired=[]
 for p in doc:
  for font in p.get_fonts():
   kind,value=doc.xref_get_key(font[0],'ToUnicode')
   if kind!='xref':continue
   ref=int(value.split()[0])
   if ref in seen:continue
   seen.add(ref);data=doc.xref_stream(ref);count=[0]
   def fix(match):
    value=int(match[1],16)
    if value>0x10ffff:return match[0]
    count[0]+=1
    return b'<'+chr(value).encode('utf-16-be').hex().upper().encode('ascii')+b'>'
   updated=re.sub(rb'<([0-9A-Fa-f]{5,6})>',fix,data)
   if count[0]:
    doc.update_stream(ref,updated,compress=True)
    repaired.append({'map_xref':ref,'destinations_corrected':count[0]})
 return repaired

def repair(source,output,work):
 work.mkdir(parents=True,exist_ok=True)
 if output.exists():raise FileExistsError('Preserve existing output before rebuilding: '+str(output))
 original=fitz.open(source)
 assert len(original)==104
 doc=fitz.open(source)
 fonts=prepare_fonts(work/'fonts')
 log=[]
 for n in PAGES:
  p=doc[n-1]
  rows=ordered_segments(original[n-1])
  targets=canonicalize(rows,n)
  p.add_redact_annot(p.rect,fill=None,cross_out=False)
  p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                     graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                     text=fitz.PDF_REDACT_TEXT_REMOVE)
  assert not p.get_text().strip(),('Legacy text was not fully removed',n)
  refs={}
  for f in fonts.values():
   ref=p.insert_font(fontname=f['resource'],fontfile=str(f['path']))
   f['xrefs'].add(ref);refs[f['resource']]=ref
  scales=[write_segment(p,r,fonts) for r in rows]
  if n==35:
   # Explicitly clear the requested top-left stray-text area, above the header.
   p.draw_rect(fitz.Rect(0,0,50,17),color=None,fill=(1,1,1),overlay=True)
  p.clean_contents()
  private_font_resources(doc,p,refs)
  log.append({'page':n,'segments_rebuilt':len(rows),'minimum_horizontal_scale':min(scales),
              'canonical_phrases_written':targets,'native_text_layer_replaced':True})
  print('Rebuilt Unicode text, page',n,flush=True)
 # Write valid UTF-16BE mappings, including surrogate pairs for supplementary
 # Unicode characters. Fix malformed legacy destinations in other font maps.
 install_valid_unicode_maps(doc,fonts)
 legacy=repair_legacy_unicode_maps(doc)
 (work/'unicode-map-repairs.json').write_text(json.dumps(legacy,indent=2))
 # Keep all four complete Unicode fonts; do not subset them again.
 doc.save(output,garbage=4,deflate=True)
 (work/'text-rebuild-log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
 return validate(source,output,work,fonts)

def validate(source,output,work,fonts):
 old=fitz.open(source);new=fitz.open(output)
 alternate=PdfReader(str(output))
 assert len(new)==len(alternate.pages)==104 and not new.is_repaired
 missing=[];checks=[];counts={};dump=[];unicode_maps=set()
 for n,(a,b) in enumerate(zip(old,new),1):
  assert a.mediabox==b.mediabox==fitz.Rect(0,0,450,666)
  assert a.cropbox==b.cropbox and a.bleedbox==b.bleedbox and a.rotation==b.rotation
  assert [(i['digest'],i['bbox']) for i in a.get_image_info(hashes=True)]==[(i['digest'],i['bbox']) for i in b.get_image_info(hashes=True)],('Artwork changed',n)
  text=b.get_text(sort=True)
  assert '\ufffd' not in text and '\0' not in text
  dump.append(f'--- PAGE {n} ---\n{text}')
  if n not in PAGES:assert a.get_text(sort=True)==text
  else:
   expected_rows=ordered_segments(a)
   canonicalize(expected_rows,n)
   expected=''.join(c['c'] for row in expected_rows for c in row['chars'])
   assert compact(expected)==compact(text),('Full page text failed Unicode round-trip',n)
   for char in GERMAN:
    assert a.get_text().count(char)==text.count(char),('German glyph count changed',n,char)
   for word in BAD:assert word not in text,('Corrupted text remains',n,word)
   other=alternate.pages[n-1].extract_text()
   assert compact(expected)==compact(other),('Independent full page text round-trip failed',n)
   for target in CANONICAL.get(n,[])+QUOTE_CHECKS.get(n,[]):
    for reader,value in [('PyMuPDF',text),('pypdf',other)]:
     if compact(target) not in compact(value):missing.append({'page':n,'reader':reader,'text':target})
    checks.append({'page':n,'text':target,'both_readers_found':compact(target) in compact(text) and compact(target) in compact(other)})
   counts[n]={c:text.count(c) for c in GERMAN}
   assert text.count('„')==text.count('“'),('Unbalanced German quotes',n)
   assert all(f[4].startswith('ZiplineUnicodeV6') for f in b.get_fonts()),('Old font resource retained on rebuilt page',n,b.get_fonts())
  if n in [101,102,103]:assert 'WER HAT DEN KOMMANDANTEN GETÖTET?' in text
  assert [repr(x['items']) for x in a.get_drawings() if x['type']=='s']==[repr(x['items']) for x in b.get_drawings() if x['type']=='s'],('Worksheet or page rules changed',n)
  for word in BAD:assert word not in text,('Corrupted text remains in output',n,word)
  for f in b.get_fonts():
   kind,value=new.xref_get_key(f[0],'ToUnicode')
   if kind=='xref':unicode_maps.add(int(value.split()[0]))
 for ref in unicode_maps:
  data=new.xref_stream(ref)
  assert not any(len(value)%2 for value in re.findall(rb'<([0-9A-Fa-f]+)>',data)),('Malformed Unicode map',ref)
 assert not missing,missing
 assert 'op' not in [w[4] for w in new[34].get_text('words') if w[0]<50 and w[1]<20]
 assert '$7' not in new[93].get_text() and '\\prime' not in new[93].get_text()
 for f in new[100].get_fonts():
  embedded=new.extract_font(f[0])[3];assert embedded
  assert new.xref_get_key(f[0],'ToUnicode')[0]=='xref',('No Unicode map',f)
 textfile=work/'Verified_v6_text_UTF8.txt'
 textfile.write_text('\n'.join(dump),encoding='utf-8')
 (work/'rendered').mkdir(exist_ok=True)
 for n in PAGES:new[n-1].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(str(work/'rendered'/f'p{n:03}.png'))
 report={'pdf':str(output),'size_bytes':output.stat().st_size,
  'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
  'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
  'page_count':104,'trim_points':[450,666],'text_pages_rebuilt':PAGES,
  'all_artwork_digests_and_positions_unchanged':True,
  'complete_unicode_fonts_embedded':True,'explicit_ToUnicode_maps':True,
  'unicode_maps_checked':len(unicode_maps),'malformed_unicode_map_entries_remaining':0,
  'full_page_text_roundtrip_in_both_readers':True,
  'worksheet_and_page_rules_preserved':True,
  'missing_required_text_or_umlaut_sequences':missing,
  'missing_required_text_or_umlaut_sequence_count':len(missing),
  'independent_text_readers':['PyMuPDF','pypdf'],
  'checked_phrases':checks,'german_character_counts_by_rebuilt_page':counts,
  'stray_op_in_top_left_of_page35':False,'raw_latex_on_page94':False,
  'utf8_text_export':str(textfile),'source_preserved':True}
 (work/'validation-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k not in ['checked_phrases','german_character_counts_by_rebuilt_page']},indent=2))
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--source',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--work',type=Path,required=True)
 args=parser.parse_args()
 repair(args.source,args.output,args.work)
