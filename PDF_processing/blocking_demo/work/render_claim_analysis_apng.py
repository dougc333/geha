from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "claim-blocking-analysis.png"

WIDTH, HEIGHT = 1200, 720
BG = "#eef1f5"
PANEL = "#ffffff"
PAPER = "#fffefb"
INK = "#17202d"
MUTED = "#657184"
LINE = "#d9dee7"
RED = "#ed2f3c"
GREEN = "#19a66a"
BLUE = "#3978f6"

REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


F10 = font(10)
F11 = font(11)
F12 = font(12)
F13 = font(13)
F14 = font(14)
F16 = font(16, True)
F18 = font(18, True)
F22 = font(22, True)
F28 = font(28, True)


STEPS = [
    {
        "box": (0.05, 0.04, 0.90, 0.10),
        "label": "DETECTING LAYOUT",
        "title": "Detecting page layout",
        "detail": "Locating stable regions before OCR and duplicate comparison.",
        "text": "Document boundary · 1 page · upright orientation",
        "metrics": (0, 0, 0),
        "verdict": "Building evidence…",
        "score": None,
    },
    {
        "box": (0.05, 0.14, 0.90, 0.17),
        "label": "PATIENT BLOCK",
        "title": "Matching patient identity",
        "detail": "OCR values are normalized, then compared with candidate claim M-3001.",
        "text": "Member P300 · DOB 04/18/1978 · DOS 08/22/2026",
        "metrics": (98, 94, 99),
        "verdict": "Identity fields agree",
        "score": 27,
    },
    {
        "box": (0.05, 0.32, 0.90, 0.15),
        "label": "PROVIDER BLOCK",
        "title": "Resolving billing provider",
        "detail": "NPI and normalized organization name agree with the candidate claim.",
        "text": "Example Family Medicine · NPI300 · Los Angeles, CA",
        "metrics": (97, 91, 98),
        "verdict": "Provider fields agree",
        "score": 45,
    },
    {
        "box": (0.05, 0.48, 0.90, 0.21),
        "label": "SERVICE LINES",
        "title": "Comparing service lines",
        "detail": "Codes match; descriptions are compared line-by-line despite changed order and wording.",
        "text": "99213 ↔ established-patient visit\n80048 ↔ chemistry panel",
        "metrics": (96, 82, 96),
        "verdict": "Two matching service lines",
        "score": 72,
    },
    {
        "box": (0.52, 0.70, 0.43, 0.11),
        "label": "TOTALS BLOCK",
        "title": "Checking amount variance",
        "detail": "The corrected submission differs by $5.00, within the review tolerance.",
        "text": "Prior total $240.00 · current total $245.00 · Δ $5.00",
        "metrics": (99, 86, 94),
        "verdict": "Small corrected amount variance",
        "score": 81,
    },
    {
        "box": (0.05, 0.82, 0.90, 0.13),
        "label": "NARRATIVE BLOCK",
        "title": "Reading supporting narrative",
        "detail": "The narrative identifies a corrected submission and preserves the same meaning.",
        "text": "“Corrected submission … high blood pressure follow-up … chemistry panel”",
        "metrics": (94, 77, 97),
        "verdict": "Correction context confirmed",
        "score": 94,
    },
    {
        "box": (0.04, 0.13, 0.92, 0.82),
        "label": "ANALYSIS COMPLETE",
        "title": "Duplicate candidate found",
        "detail": "Identifiers, service-line transport, OCR, and semantics support review as a corrected duplicate.",
        "text": "Candidate M-3001 · no critical field conflicts",
        "metrics": (97, 86, 97),
        "verdict": "Likely duplicate · route to review",
        "score": 96,
    },
]


def text_lines(draw, xy, text, chars, fill, selected_font, spacing=4):
    x, y = xy
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(wrap(paragraph, width=chars) or [""])
    draw.multiline_text(
        (x, y), "\n".join(lines), font=selected_font, fill=fill, spacing=spacing
    )


def draw_document(draw):
    px, py, pw, ph = 55, 62, 500, 610
    draw.rounded_rectangle(
        (px + 8, py + 12, px + pw + 8, py + ph + 12), radius=3, fill="#cdd3dc"
    )
    draw.rectangle((px, py, px + pw, py + ph), fill=PAPER, outline="#d7d3c9", width=1)

    ix, iy = px + 30, py + 28
    draw.text((ix, iy), "HEALTH CLAIM", font=F22, fill="#263f68")
    draw.multiline_text(
        (px + pw - 130, iy),
        "SYNTHETIC SAMPLE\nCLAIM M-3002",
        font=F10,
        fill="#657184",
        align="right",
        spacing=3,
    )
    draw.line((ix, iy + 36, px + pw - 30, iy + 36), fill="#26354b", width=2)

    y = iy + 58
    draw.text((ix, y), "PATIENT INFORMATION", font=F11, fill="#36517c")
    draw.text((ix, y + 22), "MEMBER ID\nP300", font=F10, fill="#455266", spacing=2)
    draw.text(
        (ix + 190, y + 22),
        "DATE OF BIRTH\n04/18/1978",
        font=F10,
        fill="#455266",
        spacing=2,
    )
    draw.text((ix, y + 59), "NAME\nSample Patient", font=F10, fill="#455266", spacing=2)
    draw.text(
        (ix + 190, y + 59),
        "SERVICE DATE\n08/22/2026",
        font=F10,
        fill="#455266",
        spacing=2,
    )

    y += 112
    draw.text((ix, y), "BILLING PROVIDER", font=F11, fill="#36517c")
    draw.text(
        (ix, y + 22),
        "PROVIDER\nExample Family Medicine",
        font=F10,
        fill="#455266",
        spacing=2,
    )
    draw.text((ix + 220, y + 22), "NPI\nNPI300", font=F10, fill="#455266", spacing=2)
    draw.text(
        (ix, y + 59), "LOCATION\nLos Angeles, CA", font=F10, fill="#455266", spacing=2
    )
    draw.text(
        (ix + 220, y + 59), "TAX ID\nXX-XXX0300", font=F10, fill="#455266", spacing=2
    )

    y += 112
    draw.text((ix, y), "SERVICES", font=F11, fill="#36517c")
    table = (ix, y + 20, px + pw - 30, y + 116)
    draw.rectangle(table, outline="#b9c1cc", width=1)
    draw.rectangle((table[0], table[1], table[2], table[1] + 27), fill="#e9edf3")
    cols = [table[0], table[0] + 75, table[0] + 135, table[0] + 365, table[2]]
    for cx in cols[1:-1]:
        draw.line((cx, table[1], cx, table[3]), fill="#b9c1cc")
    draw.line((table[0], table[1] + 27, table[2], table[1] + 27), fill="#b9c1cc")
    draw.line((table[0], table[1] + 61, table[2], table[1] + 61), fill="#b9c1cc")
    headers = ["Date", "Code", "Description", "Charge"]
    for i, heading in enumerate(headers):
        draw.text((cols[i] + 5, table[1] + 8), heading, font=F10, fill="#35435a")
    rows = [
        ("08/22/26", "99213", "Est. patient visit — HTN follow-up", "$165.00"),
        ("08/22/26", "80048", "Basic metabolic panel", "$80.00"),
    ]
    for row_index, row in enumerate(rows):
        ry = table[1] + 36 + row_index * 34
        for i, value in enumerate(row):
            draw.text((cols[i] + 5, ry), value, font=F10, fill="#293443")

    draw.text((px + 320, y + 133), "Total charge", font=F10, fill="#455266")
    draw.text((px + 430, y + 133), "$245.00", font=F10, fill="#17202d", anchor="ra")
    draw.text((px + 320, y + 154), "Lines", font=F10, fill="#455266")
    draw.text((px + 430, y + 154), "2", font=F10, fill="#17202d", anchor="ra")

    ny = y + 188
    draw.rectangle((ix, ny, px + pw - 30, ny + 70), outline="#c8ced6")
    draw.text((ix + 8, ny + 7), "SUPPORTING NARRATIVE", font=F10, fill="#455266")
    text_lines(
        draw,
        (ix + 8, ny + 25),
        "Corrected submission. Established-patient evaluation for high blood pressure follow-up; basic blood chemistry panel performed.",
        70,
        "#455266",
        F10,
        spacing=2,
    )
    return px, py, pw, ph


def draw_metric(draw, y, label, value, color):
    x, width = 625, 515
    draw.text((x, y), label, font=F12, fill=MUTED)
    draw.text(
        (x + width, y),
        "—" if value == 0 else f"{value}%",
        font=F12,
        fill=INK,
        anchor="ra",
    )
    draw.rounded_rectangle((x, y + 22, x + width, y + 29), radius=4, fill=LINE)
    if value:
        draw.rounded_rectangle(
            (x, y + 22, x + width * value / 100, y + 29), radius=4, fill=color
        )


def draw_frame(step_index):
    step = STEPS[step_index]
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 48), fill=PANEL)
    draw.ellipse((18, 19, 28, 29), fill=RED)
    draw.text((38, 17), "Claim blocking analysis", font=F14, fill=INK)
    draw.rectangle((0, 47, WIDTH, 50), fill=LINE)
    draw.rectangle((0, 47, WIDTH * (step_index + 1) / len(STEPS), 50), fill=RED)

    px, py, pw, ph = draw_document(draw)
    bx, by, bw, bh = step["box"]
    box = (px + bx * pw, py + by * ph, px + (bx + bw) * pw, py + (by + bh) * ph)
    draw.rectangle(box, outline=RED, width=4)
    label_width = draw.textlength(step["label"], font=F10) + 14
    label_y = max(py, box[1] - 20)
    draw.rectangle((box[0], label_y, box[0] + label_width, label_y + 18), fill=RED)
    draw.text((box[0] + 7, label_y + 4), step["label"], font=F10, fill="white")

    draw.rectangle((585, 50, WIDTH, HEIGHT), fill=PANEL)
    draw.text((625, 80), f"STEP {step_index + 1} OF {len(STEPS)}", font=F11, fill=RED)
    draw.text((625, 108), step["title"], font=F28, fill=INK)
    text_lines(draw, (625, 151), step["detail"], 57, MUTED, F14, spacing=4)

    draw.rounded_rectangle(
        (625, 220, 1140, 322), radius=10, fill="#f6f8fb", outline=LINE
    )
    draw.text((642, 236), "EXTRACTED BLOCK", font=F10, fill=MUTED)
    text_lines(draw, (642, 261), step["text"], 58, INK, F13, spacing=4)

    ocr, pixel, semantic = step["metrics"]
    draw_metric(draw, 360, "OCR confidence", ocr, BLUE)
    draw_metric(draw, 415, "Pixel similarity", pixel, BLUE)
    draw_metric(draw, 470, "Semantic similarity", semantic, GREEN)

    draw.line((625, 565, 1140, 565), fill=LINE)
    draw.text((625, 590), "CURRENT DECISION", font=F10, fill=MUTED)
    text_lines(draw, (625, 612), step["verdict"], 43, INK, F16, spacing=3)
    score = "—" if step["score"] is None else f"{step['score']}%"
    draw.text((1140, 602), score, font=F28, fill=GREEN, anchor="ra")
    draw.text(
        (625, 680), "Synthetic data · candidate review only", font=F10, fill=MUTED
    )
    return image


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
frames = [draw_frame(i) for i in range(len(STEPS))]
durations = [1400, 1400, 1400, 1700, 1400, 1700, 2600]
frames[0].save(
    OUTPUT,
    format="PNG",
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    disposal=1,
    blend=0,
    optimize=True,
)

print(OUTPUT)
