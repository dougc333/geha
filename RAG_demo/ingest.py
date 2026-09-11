"""Extract embedded text and true table borders, without clipping characters."""
import json
import re
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).parent

def outside_text(page, top, bottom):
    # Filtering by character center avoids crop() leaving tiny letter fragments.
    return page.filter(lambda o: top <= (o.get('top', 0) + o.get('bottom', 0))/2 < bottom).extract_text() or ''

def extract(source, target):
    blocks = [f'# {source.stem}']
    tables_out = []
    with pdfplumber.open(source) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            vertical = [e for r in page.rects if r['width'] < 1.5 and r['height'] > 3 for e in pdfplumber.utils.rect_to_edges(r) if e['orientation']=='v']
            horizontal = [e for r in page.rects if r['height'] < 1.5 and r['width'] > 8 for e in pdfplumber.utils.rect_to_edges(r) if e['orientation']=='h']
            tables = page.find_tables(dict(vertical_strategy='explicit', horizontal_strategy='explicit', explicit_vertical_lines=vertical, explicit_horizontal_lines=horizontal)) if len(vertical)>1 and len(horizontal)>1 else []
            tables = [t for t in tables if len(t.columns)>=2]
            blocks.append(f'## Source page {number}')
            cursor = 0
            for table in sorted(tables, key=lambda t:t.bbox[1]):
                blocks.append(outside_text(page, cursor, table.bbox[1]))
                rows = [[re.sub(r'\s+', ' ', re.sub(r'(?<=\w)-\n(?=\w)', '-', cell or '')).strip() for cell in row] for row in table.extract()]
                if number==3 and 'bevacizumab' in source.name:
                    rows.insert(0, ['Drug Name', 'HCPCS Code', 'Description'])
                    blocks.append('Billing (continued from page 2; headers repeated)')
                tables_out.append({'source':source.name,'page':number,'rows':rows})
                lines=['| '+' | '.join(c.replace('|','\\|') for c in row)+' |' for row in rows]
                lines.insert(1, '| '+' | '.join(['---']*len(rows[0]))+' |')
                blocks.append('\n'.join(lines))
                cursor = table.bbox[3]
            blocks.append(outside_text(page, cursor, page.height))
    target.write_text('\n\n'.join(blocks)+'\n', encoding='utf-8')
    return tables_out

def main():
    target = ROOT/'data/documents'
    target.mkdir(parents=True, exist_ok=True)
    tables = []
    for source in sorted((ROOT/'data/sources').glob('*.pdf')):
        tables += extract(source, target/(source.stem+'.md'))
    (ROOT/'data/tables.json').write_text(json.dumps(tables, indent=2, ensure_ascii=False)+'\n')
    print(f'Extracted {len(tables)} table sections')

if __name__=='__main__':
    main()
