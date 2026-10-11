# Page 22 · Figure 16

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Third-party vendors are best positioned to provide benefits technology.**
Region ID: `page-022-region-b54bef16`
Region type: `figure`
Embedded font evidence: EYInterstate-Bold, EYInterstate-LightBold, EYInterstate-Light

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

- Normalized box: x1=13.463, y1=622.227, x2=989.516, y2=913.337
- Geometry-derived vertical bar mapping (not PDF text order):
  - bar_at_x_81.4: top to bottom = 4% None, 24% #2e2e38, 31% #747480, 41% #ffe500; displayed sum = 100.0%.
  - bar_at_x_222.8: top to bottom = 10% #c3c4cc, 21% #2e2e37, 27% #747480, 42% #ffe500; displayed sum = 100.0%.
  - bar_at_x_363.2: top to bottom = 7% #c3c4cc, 25% #2e2e37, 32% #747480, 36% #ffe500; displayed sum = 100.0%.
- Native text:

```text
Figure 16
Third-party vendors are best positioned to provide benefits technology.
QUESTION: Which of the following do you feel is best positioned to provide the most important benefits technology for your company’s
insurance benefits program?
4%
10% 7%
24% 21% 25%
31% 27% Platform built-house 32%
Broker/benefits advisor
Insurance carrier(s)
Third-party vendor
41% 42% 36%
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
