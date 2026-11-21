import json, pymupdf

d = json.load(open("2rows-boxes.json"))
doc = pymupdf.open("bill-of-lading.pdf")
page = doc[0]
red = (1, 0, 0)

for x0, y0, x1, y1 in d["all_ruled_cells_pt"]:
    if x1 - x0 < 100 and y1 - y0 < 100 and y0 < 120:   # skip the logo square
        continue
    page.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=red, width=3)

for s in d["separators"]:
    x0, y, x1, _ = s["line_pt"]
    page.draw_line((x0, y), (x1, y), color=red, width=3)

doc.save("2rows_recreated.pdf")
