"""Detect ruled PDF tables, export crops, and animate the recorded detections.

Usage: python work/render_table_detection_apng.py [--pdf /path/to/source.pdf]
Requires: pillow pdfplumber pypdfium2. No OCR or language model is used.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
W, H = 1440, 900
INK, MUTED, RED, BLUE = '#17202d', '#657184', '#ed2f3c', '#263f68'
FONT_DIR = Path('/System/Library/Fonts/Supplemental')

def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR/('Arial Bold.ttf' if bold else 'Arial.ttf')), size)

def wrapped(draw, text, xy, max_width, size=18, fill=INK):
    f = font(size)
    x, y = xy
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = f'{line} {word}'.strip()
            if line and draw.textlength(candidate, font=f)>max_width:
                draw.text((x,y),line,font=f,fill=fill)
                y += size+7
                line = word
            else:
                line = candidate
        draw.text((x,y),line,font=f,fill=fill)
        y += size+7
    return y

def detect(page):
    # Table borders in these PDFs are skinny filled rectangles; exclude fills
    # behind words, which otherwise introduce false cell boundaries.
    vertical=[e for r in page.rects if r['width']<1.5 and r['height']>3
              for e in pdfplumber.utils.rect_to_edges(r) if e['orientation']=='v']
    horizontal=[e for r in page.rects if r['height']<1.5 and r['width']>8
                for e in pdfplumber.utils.rect_to_edges(r) if e['orientation']=='h']
    if len(vertical)<2 or len(horizontal)<2:
        return []
    tables=page.find_tables({'vertical_strategy':'explicit','horizontal_strategy':'explicit',
                            'explicit_vertical_lines':vertical,'explicit_horizontal_lines':horizontal})
    return sorted([t for t in tables if len(t.columns)>=2 and len(t.rows)>=2],key=lambda t:t.bbox[1])

def paste_fit(canvas, image, box):
    x,y,w,h=box
    fitted=ImageOps.contain(image,(w,h),Image.Resampling.LANCZOS)
    left,top=x+(w-fitted.width)//2,y+(h-fitted.height)//2
    canvas.paste(fitted,(left,top))
    return left,top,fitted.width,fitted.height

def frame(record, page_image, crop, phase, index, total, source):
    canvas=Image.new('RGB',(W,H),'#eef1f5')
    d=ImageDraw.Draw(canvas)
    d.rectangle((0,0,W,62),fill='white')
    d.ellipse((24,23,36,35),fill=RED)
    d.text((48,17),'Table detection and capture',font=font(24,True),fill=INK)
    d.text((W-24,23),f'TABLE {index+1} OF {total}  /  PAGE {record["page"]}',font=font(15),fill=MUTED,anchor='ra')
    d.rectangle((0,59,W,63),fill='#d9dee7')
    d.rectangle((0,59,W*(index*3+phase+1)/(total*3),63),fill=RED)
    px,py,pw,ph=paste_fit(canvas,page_image,(25,86,585,760))
    d.rectangle((px-1,py-1,px+pw,py+ph),outline='#bac2cd')
    x0,y0,x1,y1=record['bbox_points']
    page_w,page_h=record['page_size_points']
    box=(px+x0/page_w*pw,py+y0/page_h*ph,px+x1/page_w*pw,py+y1/page_h*ph)
    d.rectangle(box,outline=RED,width=4)
    label=f'TABLE {index+1}'
    d.rectangle((box[0],box[1]-24,box[0]+104,box[1]),fill=RED)
    d.text((box[0]+8,box[1]-21),label,font=font(15,True),fill='white')
    d.rectangle((635,64,W,H),fill='white')
    titles=['Detect the table grid','Capture the table region','Export the screenshot']
    details=[
        'Locate horizontal and vertical borders in the PDF. Use their intersections to preserve rows and columns.',
        'Render the source page at 216 DPI, then crop around the detected table with a 4-point margin.',
        'Save a lossless PNG plus the extracted cell text, source page, and bounding-box coordinates.',
    ]
    d.text((670,96),f'PHASE {phase+1} / 3',font=font(15,True),fill=RED)
    d.text((670,131),titles[phase],font=font(32,True),fill=INK)
    wrapped(d,details[phase],(670,184),720,size=18,fill=MUTED)
    d.rounded_rectangle((670,268,1400,578),radius=10,fill='#f6f8fb',outline='#d9dee7')
    if phase:
        paste_fit(canvas,crop,(682,280,706,286))
    else:
        # Draw the measured table grid, not fabricated boxes.
        sx,sy,sw,sh=692,293,684,257
        for cell in record['cells_points']:
            cx0,cy0,cx1,cy1=cell
            mapped=(sx+(cx0-x0)/(x1-x0)*sw,sy+(cy0-y0)/(y1-y0)*sh,
                    sx+(cx1-x0)/(x1-x0)*sw,sy+(cy1-y0)/(y1-y0)*sh)
            d.rectangle(mapped,outline=BLUE,width=2)
    d.text((670,603),f'{record["rows_including_header"]} rows (including header)  ×  {record["columns"]} columns',font=font(22,True),fill=INK)
    d.text((670,645),'BOUNDING BOX / PDF POINTS',font=font(13,True),fill=MUTED)
    d.text((670,670),'  '.join(f'{v:.2f}' for v in record['bbox_points']),font=font(18),fill=INK)
    d.text((670,715),'OUTPUT FILE',font=font(13,True),fill=MUTED)
    wrapped(d,record['screenshot'],(670,739),720,size=16)
    d.text((670,839),'Recorded detections • embedded PDF text • no OCR',font=font(15),fill=MUTED)
    d.text((25,870),source.name,font=font(14),fill=MUTED)
    return canvas

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdf',type=Path,default=ROOT.parent/'downloads/coverage-policies/geha-coverage-policy-bendamustine.pdf')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs')
    args=parser.parse_args()
    source=args.pdf.resolve()
    output=args.output_dir
    crop_dir=output/'table-screenshots'/source.stem
    crop_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    previews=[]
    renderer=pdfium.PdfDocument(source)
    with pdfplumber.open(source) as pdf:
        for page_no,page in enumerate(pdf.pages,1):
            tables=detect(page)
            if not tables:
                continue
            raster_page=renderer[page_no-1]
            bitmap=raster_page.render(scale=3)
            page_image=bitmap.to_pil().convert('RGB')
            bitmap.close(); raster_page.close()
            for table_no,table in enumerate(tables,1):
                bbox=list(table.bbox)
                sx,sy=page_image.width/page.width,page_image.height/page.height
                crop_box=(max(0,math.floor((bbox[0]-4)*sx)),max(0,math.floor((bbox[1]-4)*sy)),
                          min(page_image.width,math.ceil((bbox[2]+4)*sx)),min(page_image.height,math.ceil((bbox[3]+4)*sy)))
                crop=page_image.crop(crop_box)
                path=crop_dir/f'page-{page_no:02d}-table-{table_no:02d}.png'
                crop.save(path,dpi=(216,216))
                rows=[[re.sub(r'\s+',' ',c or '').strip() for c in r] for r in table.extract()]
                record={'page':page_no,'table_on_page':table_no,'bbox_points':bbox,'page_size_points':[page.width,page.height],
                        'cells_points':table.cells,'rows_including_header':len(rows),'columns':len(table.columns),'rows':rows,
                        'screenshot':str(path.relative_to(output)),'crop_pixels':crop_box,'size_pixels':list(crop.size),
                        'screenshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                records.append(record); previews.append((page_image.copy(),crop))
    renderer.close()
    if not records:
        raise SystemExit('No supported bordered tables detected. Borderless/scanned tables need another detector.')
    manifest={'source_pdf':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'method':'embedded thin-rectangle borders; pdfplumber cells; PDFium rasterization',
              'coordinate_system':'PDF points, top-left origin','render_dpi':216,'tables':records}
    (crop_dir/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    md=[]
    for r in records:
        md.append(f'## Page {r["page"]}, table {r["table_on_page"]}\n')
        rows=r['rows']
        lines=['| '+' | '.join(c.replace('|','\\|') for c in row)+' |' for row in rows]
        lines.insert(1,'| '+' | '.join(['---']*r['columns'])+' |')
        md.append('\n'.join(lines))
    (crop_dir/'tables.md').write_text('\n\n'.join(md)+'\n')
    frames=[frame(r,*previews[i],phase,i,len(records),source) for i,r in enumerate(records) for phase in range(3)]
    animation=output/'table-detection-analysis.png'
    frames[0].save(animation,format='PNG',save_all=True,append_images=frames[1:],duration=[1400,1700,2200]*len(records),loop=0,disposal=1,blend=0)
    frames[1].save(output/'table-detection-preview.png')
    with Image.open(animation) as check:
        assert check.n_frames==len(frames)
    for r in records:
        with Image.open(output/r['screenshot']) as check:
            assert list(check.size)==r['size_pixels']
        assert all(len(row)==r['columns'] for row in r['rows'])
    print(json.dumps({'animation':str(animation),'tables':len(records),'frames':len(frames),'manifest':str(crop_dir/'manifest.json')},indent=2))

if __name__=='__main__': main()
