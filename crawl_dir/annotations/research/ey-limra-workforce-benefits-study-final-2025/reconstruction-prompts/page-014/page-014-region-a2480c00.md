# Page 14 · Figure 9

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Employer opinions are mixed about primary responsibility for education and awareness that**
Region ID: `page-014-region-a2480c00`
Region type: `figure`
Embedded font evidence: EYInterstate-Light, EYInterstate-Bold, EYInterstate-LightBold

## Ordered reconstruction strategy

1. Start with the lowest shared structural anchor: baseline, axis, table edge, or aligned row beneath the data marks.
2. Place the category labels and sublabels into aligned groups before drawing any bars, points, or shapes.
3. Load the PDF's embedded font families and lock the observed text hierarchy before chart construction; do not run a font-guessing loop.
4. Construct one complete category or series at a time. Treat every displayed percentage as locked evidence.
5. For stacked marks, calculate segment dimensions from the displayed percentages using one common total size; preserve stacking order and color relationships.
6. Add change annotations, years, leader lines, legends, and footnotes only after the primary series is aligned.
7. Repeat the same measured construction for the remaining categories or series.
8. Include an accessible semantic table or structured description without changing the visible layout.
9. Render at the authoritative crop's exact pixel dimensions and perform a side-by-side check for clipping, overlap, scale, spacing, text, and data relationships.

## Locked evidence

- Normalized box: x1=16.071, y1=569.878, x2=978.767, y2=923.482
- Geometry-derived horizontal bar mapping (not PDF text order):
  - My company: left to right = 24% #c4c4cd, 33% None; displayed sum = 57.0%.
  - Insurance carrier(s): left to right = 26% #c4c4cd, 26% #c4c4cd; displayed sum = 52.0%.
  - Broker/benefits advisor: left to right = 23% #c4c4cd, 33% None; displayed sum = 56.0%.
  - Benefits technology platform: left to right = 12% #c4c4cd, 14% #c4c4cd; displayed sum = 26.0%.
  - No preference: left to right = 4% #c4c4cd, 6% #c4c4cd; displayed sum = 10.0%.
- Native text:

```text
Figure 9
Employer opinions are mixed about primary responsibility for education and awareness that
employees need to make confident enrollment decisions.
QUESTION: Who do you think should be primarily accountable for providing the education and awareness needed for employees to
make confident enrollment decisions?
33% My company
24%
26% Insurance carrier(s) 26%
23% Broker/benefits advisor 33%
14% Benefits technology platform
12%
2025 2023
4% No preference 6%
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
