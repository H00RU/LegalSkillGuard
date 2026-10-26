#!/usr/bin/python3
"""Render the source-bound v0.23 bilingual teacher draft using the preserved renderer.

No model, dataset, grader or experiment calls. The manifest checks every source
paragraph and table cell against extracted PDF text and records all figure hashes.
The output directory must be new, preserving earlier review artifacts.
"""
import sys
sys.excepthook=sys.__excepthook__
import collections,html,json,re,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as ET
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,LongTable,TableStyle,Image,KeepTogether
from reportlab.lib.utils import ImageReader
sys.path.insert(0, str(Path.cwd()))
from legal_skill_guard.experiment.storage import RunStore
PROGRAM = Path(__file__).read_text(encoding="utf-8")
root=Path.cwd()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
M=root/"paper/manuscript_v1_20261021.md";D=root/"paper/appendix_experimental_details_20261022.md"
C=root/"paper/figures/method_overview_caption_20261023.md"
assert sha(M)=="208b5acef3b65ea1dc1ac3418f02e7796bdf32c8145882b1d10a102af4426aaf"
assert sha(D)=="67f31516c74e9f7f7077785fbc10ca78f5e78f867229bf38c6c9fea7aaa2d4eb"
source_text={str(p.relative_to(root)):p.read_text() for p in (M,D,C)}
source_hash={str(p.relative_to(root)):sha(p) for p in (M,D,C)}
fonts={"ReviewEN":"/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
 "ReviewENBold":"/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
 "ReviewENItalic":"/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
 "ReviewENBoldItalic":"/usr/share/fonts/truetype/liberation2/LiberationSerif-BoldItalic.ttf",
 "ReviewMono":"/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
 "ReviewCN":"/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"}
assert all(Path(path).is_file() for path in fonts.values()),fonts
for name,path in fonts.items():pdfmetrics.registerFont(TTFont(name,path))
pdfmetrics.registerFontFamily("ReviewEN",normal="ReviewEN",bold="ReviewENBold",italic="ReviewENItalic",boldItalic="ReviewENBoldItalic")
pdfmetrics.registerFontFamily("ReviewCN",normal="ReviewCN",bold="ReviewCN",italic="ReviewCN",boldItalic="ReviewCN")
pdfmetrics.registerFontFamily("ReviewMono",normal="ReviewMono",bold="ReviewMono",italic="ReviewMono",boldItalic="ReviewMono")
cjk=re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]+")
def plain_markup(s):
 escaped=html.escape(s)
 return cjk.sub(lambda m:'<font name="ReviewCN">'+m.group()+'</font>',escaped)
token=re.compile(r"(!?\[[^\]]*\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*\n]+\*|\x60[^\x60]+\x60|\[(?:PENDING|PLANNED|待)[^\]]*\])")
external_links=[]
def inline(s):
 out=[];end=0
 for m in token.finditer(s):
  out.append(plain_markup(s[end:m.start()]));t=m.group()
  if t.startswith("**"):out.append("<b>"+inline(t[2:-2])+"</b>")
  elif t.startswith("*"):out.append("<i>"+inline(t[1:-1])+"</i>")
  elif t.startswith("\x60"):out.append('<font name="ReviewMono" size="8.5">'+plain_markup(t[1:-1])+"</font>")
  elif t.startswith(("[PENDING","[PLANNED","[待")):out.append('<span backColor="#fff0ad">'+plain_markup(t)+"</span>")
  else:
   link=re.fullmatch(r"!?\[([^\]]*)\]\(([^)]+)\)",t);label,url=link.groups()
   if url.startswith(("https://","http://")):
    external_links.append(url);out.append('<link href="'+html.escape(url,quote=True)+'" color="#1d4f8a">'+inline(label)+"</link>")
   elif "appendix_experimental_details_" in url:out.append('<link href="#appendix_d" color="#1d4f8a">'+inline(label)+"</link>")
   elif "method_overview_caption_" in url:out.append('<link href="#method_overview" color="#1d4f8a">'+inline(label)+"</link>")
   else:out.append(inline(label))
  end=m.end()
 out.append(plain_markup(s[end:]));return "".join(out)
def blocks(text):
 lines=text.splitlines();i=0;result=[]
 while i<len(lines):
  if not lines[i].strip():i+=1;continue
  start=i;l=lines[i]
  if l.startswith("\x60\x60\x60"):
   i+=1;code_start=i
   while i<len(lines) and not lines[i].startswith("\x60\x60\x60"):i+=1
   assert i<len(lines),"Unclosed source code fence"
   code_lines=lines[code_start:i];i+=1
   result.append({"kind":"code","raw_lines":lines[start:i],"code_lines":code_lines,"line_start":start+1,"line_end":i});continue
  if l.startswith("|"):
   while i<len(lines) and lines[i].startswith("|"):i+=1
   raw=lines[start:i];rows=[[x.strip() for x in re.split(r"(?<!\\)\|",x.strip().strip("|"))] for x in raw]
   assert len(rows)>=2 and all(re.fullmatch(r":?-{3,}:?",c) for c in rows[1])
   assert len({len(r) for r in rows})==1
   result.append({"kind":"table","raw_lines":raw,"rows":[rows[0]]+rows[2:],"line_start":start+1,"line_end":i});continue
  h=re.match(r"^(#{1,4}) (.*)$",l)
  if h:
   i+=1;result.append({"kind":"heading","level":len(h[1]),"text":h[2],"raw_lines":[l],"line_start":start+1,"line_end":i});continue
  im=re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)",l)
  if im:
   i+=1;result.append({"kind":"image","alt":im[1],"target":im[2],"raw_lines":[l],"line_start":start+1,"line_end":i});continue
  is_item=bool(re.match(r"^(\d+\.|-)\s",l))
  i+=1
  while i<len(lines) and lines[i].strip():
   if lines[i].startswith(("#","|","![")) or re.match(r"^(\d+\.|-)\s",lines[i]):break
   i+=1
  raw=lines[start:i];result.append({"kind":"paragraph","text":" ".join(x.strip() for x in raw),"raw_lines":raw,"line_start":start+1,"line_end":i})
 used={n for b in result for n in range(b["line_start"],b["line_end"]+1) if lines[n-1].strip()}
 assert used=={i+1 for i,l in enumerate(lines) if l.strip()},"All source nonblank lines must be partitioned."
 return result
W,H=A4;margin=45;avail=W-2*margin-12
styles={
 "body":ParagraphStyle("ReviewBody",fontName="ReviewEN",fontSize=9.5,leading=14.2,spaceAfter=7,allowWidows=0,allowOrphans=0,splitLongWords=1),
 "h1":ParagraphStyle("ReviewH1",fontName="ReviewENBold",fontSize=17,leading=22,spaceBefore=8,spaceAfter=12,keepWithNext=1),
 "h2":ParagraphStyle("ReviewH2",fontName="ReviewENBold",fontSize=12.5,leading=17,spaceBefore=12,spaceAfter=8,keepWithNext=1),
 "h3":ParagraphStyle("ReviewH3",fontName="ReviewENBold",fontSize=10.8,leading=15,spaceBefore=10,spaceAfter=6,keepWithNext=1),
 "cell":ParagraphStyle("ReviewCell",fontName="ReviewEN",fontSize=8.1,leading=11.5,spaceAfter=0,splitLongWords=1),
 "cellhead":ParagraphStyle("ReviewCellHead",fontName="ReviewENBold",fontSize=8.1,leading=11.5,spaceAfter=0,splitLongWords=1),
 "code":ParagraphStyle("ReviewCode",fontName="ReviewMono",fontSize=7.3,leading=10.3,spaceAfter=1.5,splitLongWords=1),
 "note":ParagraphStyle("ReviewNote",fontName="ReviewEN",fontSize=8.4,leading=12,spaceAfter=9,backColor=colors.HexColor("#fff5d6"),borderPadding=7)}
units={};draws=[];images=[];source_blocks={};method_inserted=False
class AuditedParagraph(Paragraph):
 def __init__(self,*a,**kw):
  self.audit_id=kw.pop("audit_id",None);super().__init__(*a,**kw)
 def split(self,*a,**kw):
  out=super().split(*a,**kw)
  for c in out:
   if isinstance(c,AuditedParagraph):c.audit_id=self.audit_id
  return out
 def draw(self):
  a,b,c,d,x,y=self.canv._currentMatrix
  assert abs(a-1)<1e-8 and abs(d-1)<1e-8 and abs(b)<1e-8 and abs(c)<1e-8
  draws.append({"id":self.audit_id,"page":self.canv.getPageNumber(),"x":x,"y":y,"width":self.width,"height":self.height,"drawn_text":self.getPlainText()})
  return super().draw()
def para(text,key,kind="body",prefix=""):
 markup=prefix+inline(text);style=styles[kind]
 if cjk.search(text):style=ParagraphStyle(style.name+"CN",parent=style,wordWrap="CJK")
 p=AuditedParagraph(markup,style,audit_id=key)
 assert key not in units
 units[key]={"source_text":text,"plain_text":p.getPlainText(),"kind":kind}
 return p
curve=root/"artifacts/research/learning_curves_20261022/Run03_B1_B8_prequential_final_publications/learning_curve_600dpi.png"
method=root/"artifacts/research/method_overview_20261023/Run03_implemented_information_flow_v03/method_overview_600dpi.png"
assets=[curve,method]
class AuditedImage(Image):
 def draw(self):
  _,_,_,_,x,y=self.canv._currentMatrix
  target=next(m for m in images if m["id"]==self.audit_key)
  target.update({"page":self.canv.getPageNumber(),"x":x,"y":y})
  return super().draw()
def picture(path,key,alt):
 assert path.is_file()
 w,h=ImageReader(str(path)).getSize();height=avail*h/w
 assert height<420
 image=AuditedImage(str(path),width=avail,height=height);image.hAlign="CENTER";image.audit_key=key
 image.keepWithNext=True
 images.append({"id":key,"path":str(path.relative_to(root)),"sha256":sha(path),"pixels":[w,h],"width_points":avail,"height_points":height,"alt":alt})
 return image
story=[]
story.append(para("TEACHER-FACING WORKING DRAFT. Bilingual manuscript v0.23 and Appendix D report completed training, adapted-method comparisons, two granularity controls and the complete eight-condition, 128-source frozen TEST. Independent learning repetitions are user-deferred, not completed. Valuation evolution is supported conditional on the actual banks; continued classification gain is uncertain and finer granularity is not uniformly superior. One ACE timeout has unknown usage. This is an internal scientific draft, not a journal-template submission or a completed replicated study.","render_note_en","note"))
story.append(para("老师审阅初稿：双语v0.23正文及附录D，含完整训练、外部适配比较、两项消融和128来源的完整八条件冻结TEST。独立学习重复仍按用户决定暂缓。估值持续进化有来源条件证据，分类后续收益不确定，细粒度不全面最优；ACE一次超时用量未知。本稿用于审阅实际研究证据，不是期刊模板投稿版或已完成独立重复的研究。","render_note_zh","note"))
method_caption=re.search(r"\n(Experience changes[\s\S]*?)\nAssets:",C.read_text()).group(1).strip()
def add_method():
 global method_inserted
 assert not method_inserted;method_inserted=True
 story.append(para("Implemented method overview / 已实现方法总览（图号待整合）","method_insert_h","h3",prefix='<a name="method_overview"/>'))
 story.append(picture(method,"method_image","Implemented batchwise skill evolution, no empirical performance claim"))
 for k,b in enumerate(blocks(method_caption)):
  assert b["kind"]=="paragraph"
  story.append(para(b["text"],"method_caption_"+str(k)))
for source,prefix in [(M,"M"),(D,"D")]:
 parsed=blocks(source.read_text());source_blocks[str(source.relative_to(root))]=parsed
 if source==D:story.append(PageBreak())
 for k,b in enumerate(parsed):
  key=prefix+"_"+str(k)
  if b["kind"]=="heading":
   anchor='<a name="appendix_d"/>' if source==D and k==0 else ""
   story.append(para(b["text"],key,"h"+str(min(b["level"],3)),prefix=anchor))
  elif b["kind"]=="paragraph":
   story.append(para(b["text"],key))
   if source==M and b["text"].endswith("后续预测只使用实际已发布库。"):add_method()
  elif b["kind"]=="image":
   assert source==M and b["target"].endswith("learning_curve.svg")
   story.append(picture(curve,key,b["alt"]))
  elif b["kind"]=="code":
   for line_index,line in enumerate(b["code_lines"]):
    if not line.strip():story.append(Spacer(1,5));continue
    indentation=len(line)-len(line.lstrip())
    code_paragraph=para(line.lstrip(),key+"_line"+str(line_index),"code")
    code_paragraph.style=ParagraphStyle("CodeIndent"+str(indentation),parent=code_paragraph.style,leftIndent=indentation*4.0)
    story.append(code_paragraph)
  else:
   rows=b["rows"];cols=len(rows[0]);widths=(
    [.20,.23,.23,.12,.22] if cols==5 and rows[0][0]=="Condition" else [.18,.09,.22,.22,.14,.15] if cols==6 and rows[0][0]=="Main minus comparator / endpoint" else [.36,.64] if cols==2 else [.30,.35,.35] if cols==3 else [.25]*4 if cols==4 else ([.20,.10,.24,.24,.22] if source==D else [.08,.23,.23,.27,.19]) if cols==5 else [1/cols]*cols)
   grid=[[para(value,key+"_r"+str(ri)+"c"+str(ci),"cellhead" if ri==0 else "cell") for ci,value in enumerate(row)] for ri,row in enumerate(rows)]
   tab=LongTable(grid,colWidths=[avail*w for w in widths],repeatRows=1,hAlign="LEFT",spaceBefore=5,spaceAfter=10)
   tab.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eaf0f6")),
    ("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor("#5e6c78")),("LINEBELOW",(0,-1),(-1,-1),.4,colors.HexColor("#8d969e")),
    ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
   story.append(tab)
assert method_inserted and len(images)==2

visible="".join(u["plain_text"] for u in units.values())
missing=sorted({ch for ch in visible if not ch.isspace() and ord(ch) not in pdfmetrics.getFont("ReviewCN" if cjk.fullmatch(ch) else "ReviewEN").face.charWidths})
assert not missing,("Uncovered source characters",missing)
outdir=root/"artifacts/research/manuscript_review_20261026/v023_bilingual_teacher_review_v01"
outdir.mkdir(parents=True,exist_ok=False)
pdf=outdir/"legal_skill_evolution_v023_bilingual_teacher_review.pdf"
doc=SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=margin,rightMargin=margin,topMargin=54,bottomMargin=45,
 title="Internal review: "+M.read_text().splitlines()[0].lstrip("# "),author="",
 subject="Working bilingual manuscript v0.23; completed frozen TEST, independent learning repetitions deferred",
 creator="Source-bound internal manuscript renderer; no experiment or scientific-text modification",
 allowSplitting=1,pageCompression=1)
def page_frame(canv,doc):
 canv.saveState();canv.setFont("ReviewEN",7.0);canv.setFillColor(colors.HexColor("#54616d"))
 canv.drawString(margin,H-27,"TEACHER REVIEW | v0.23 | Frozen TEST complete; learning repetitions deferred")
 canv.setStrokeColor(colors.HexColor("#c4cbd2"));canv.line(margin,H-32,W-margin,H-32)
 canv.drawString(margin,25,"Source manuscript "+source_hash[str(M.relative_to(root))][:12]+" | 26 October 2026")
 canv.drawRightString(W-margin,25,"Page "+str(doc.page))
 canv.restoreState()
doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
assert pdf.exists() and pdf.stat().st_size>10000
assert source_hash=={str(x.relative_to(root)):sha(x) for x in (M,D,C)}
seen={d["id"] for d in draws}
assert None not in seen and seen==set(units),("All visible source text must actually draw",sorted(set(units)-seen))
bounds=[d for d in draws if d["x"]<margin-1 or d["x"]+d["width"]>W-margin+1 or d["y"]<43 or d["y"]+d["height"]>H-51]
assert not bounds,("Text block outside review frame",bounds[:3])
normalize=lambda x:"".join(html.unescape(x).replace("\u200b","").split())
# Validate actual PDF text by source unit below; ReportLab getPlainText is empty on internally split fragments.
xml=subprocess.run(["pdftotext","-bbox-layout",str(pdf),"-"],check=True,capture_output=True,text=True).stdout
tree=ET.fromstring(xml);ns={"h":"http://www.w3.org/1999/xhtml"}
pages=tree.findall(".//h:page",ns)
words=[]
for page in pages:
 entries=[]
 for li,line in enumerate(page.findall(".//h:line",ns)):
  for w in line.findall(".//h:word",ns):
   entries.append({"line":li,"x0":float(w.attrib["xMin"]),"x1":float(w.attrib["xMax"]),"y0":float(w.attrib["yMin"]),"y1":float(w.attrib["yMax"]),"text":w.text or ""})
 words.append(entries)
pdf_unit_fragments=collections.defaultdict(list)
for d in draws:
 box=(d["x"]-1.2,H-d["y"]-d["height"]-1.8,d["x"]+d["width"]+1.2,H-d["y"]+1.8)
 matched=[w for w in words[d["page"]-1] if box[0]<=(w["x0"]+w["x1"])/2<=box[2] and box[1]<=(w["y0"]+w["y1"])/2<=box[3]]
 actual="".join(w["text"] for w in sorted(matched,key=lambda w:(w["line"],w["x0"])))
 d["actual_pdf_bbox_text"]=actual
 pdf_unit_fragments[d["id"]].append(actual)
mismatches=[]
for key,u in units.items():
 fragments=pdf_unit_fragments[key];expected=normalize(u["plain_text"]);joined=normalize("".join(fragments))
 if joined!=expected and not all(normalize(f)==expected for f in fragments):
  mismatches.append({"id":key,"pages":[d["page"] for d in draws if d["id"]==key],"expected":u["plain_text"],"actual_fragments":fragments})
plain=subprocess.run(["pdftotext","-layout",str(pdf),"-"],check=True,capture_output=True,text=True).stdout
assert "87.43" in plain and "86.18" in plain and "References" in plain and "Appendix D" in plain and "D.10" in plain
status="text_and_geometry_verified_pending_visual_review" if not mismatches else "needs_render_text_review"
out={"at":now(),"classification":"Source-faithful bilingual teacher review PDF of v0.23 manuscript and AppendixD, completed frozen TEST and preserved TRAIN evidence; independent learning repetitions deferred, not a submission or completed replicated study",
 "status":status,"pdf":{"path":str(pdf.relative_to(root)),"sha256":sha(pdf),"bytes":pdf.stat().st_size,"pages":len(pages)},
 "source_sha256":source_hash,"complete_source_text_snapshots":source_text,"source_block_partitions":source_blocks,
 "visible_text_units":units,"drawn_text_fragments":draws,"all_source_nonblank_lines_partitioned":True,
 "every_visible_source_paragraph_heading_table_cell_drew":True,"all_text_inside_frame":True,
 "PDF_bbox_extraction_mismatches":mismatches,"all_source_glyphs_covered":True,
 "source_method_caption_original_paragraphs_only":method_caption,"images":images,
 "existing_source_figure_values_not_changed":True,
 "font_sha256":{n:{"path":v,"sha256":sha(Path(v))} for n,v in fonts.items()},
 "renderer":{"interpreter":"/usr/bin/python3","reportlab":reportlab.Version,"new_dependency_installation":False},
 "external_clickable_links":sorted(set(external_links)),
 "renderer_does_not_modify_scientific_sources_or_results":True,
 "no_model_teacher_tokenizer_TEST_or_training_source_access_change":True,
 "target_journal_and_author_metadata_still_pending":True,"recomputation_program":PROGRAM}
manifest=outdir/"render_manifest_and_text_QA.json";RunStore.immutable_json(manifest,out)
print(json.dumps({"pdf":str(pdf.relative_to(root)),"pages":len(pages),"bytes":pdf.stat().st_size,
 "visible_text_units":len(units),"draw_fragments":len(draws),"tables_main_appendix":sum(b["kind"]=="table" for bs in source_blocks.values() for b in bs),
 "images":images,"bbox_text_mismatches":len(mismatches),"examples":mismatches[:3],
 "status":status,"manifest":str(manifest.relative_to(root))},ensure_ascii=False))
