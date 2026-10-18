# Page 5 · Figure 2

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Worker participation in the gig economy is**
Region ID: `page-005-region-4c8ed247`
Region type: `figure`
Embedded font evidence: EYInterstate-Bold, EYInterstate-Regular, EYInterstate-Light

## Ordered reconstruction strategy

1. Start with the shared horizontal baseline and place the 2023 and 2025 labels beneath their respective bars.
2. Load the PDF's embedded font families and lock the observed title, question, percentages, years, and legend text before chart construction.
3. Construct the 2023 vertical bar from exactly two stacked segments using one common total height: 66% gray above 34% yellow.
4. Construct the 2025 vertical bar at the same total height: 77% gray above 23% yellow.
5. Place 66% and 77% centered in their gray segments, and 34% and 23% centered in their yellow segments.
6. Preserve the thin connector between the two yellow/gray boundaries, the baseline, bar widths, spacing, background, and legend color mapping.
7. Include an accessible semantic table containing the two years and their gray/yellow values without changing the visible layout.
8. Render at the authoritative crop's exact pixel dimensions and perform a side-by-side check for clipping, overlap, scale, spacing, text, and data relationships.

## Locked evidence

- Normalized box: x1=32.199, y1=507.04, x2=498.124, y2=899.77
- Geometry-derived bar mapping (not PDF text order):
  - 2023: top to bottom = 66% #747480, 34% #ffe600; displayed sum = 100.0%.
  - 2025: top to bottom = 77% #747480, 23% #ffe600; displayed sum = 100.0%.
- Native text:

```text
Figure 2
Worker participation in the gig economy is
trending downward.
QUESTION: Instead of (or in addition to) working for a
traditional employer (also known as being a W-2 employee),
some workers pursue freelance or “gig” work. Which of the
following best describes your current work arrangement?
66%
77%
34%
23%
2023 2025
Do not freelance or have a gig job(s) Freelance (full or part time)
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
