# Page 16 · Figure 1

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Both employees and employers indicate strong interest in paid family**
Region ID: `page-016-region-0206ea67`
Region type: `figure`
Embedded font evidence: EYInterstate-Bold, EYInterstate-LightBold, EYInterstate-Regular

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

- Normalized box: x1=3.962, y1=672.172, x2=972.963, y2=920.884
- Bar mapping status: ambiguous. Do not treat the extracted percentages as a sequence or assign them to bars.
- Positioned percentage tokens for visual verification only: 92% at (117.815, 646.511), 38% at (306.141, 646.511), 46% at (493.59, 646.511)
- Native text:

```text
Both employees and employers indicate strong interest in paid family
or medical leave.
92% 38% 46%
of employees would be of small employers (10–99 of employers are considering
interested in paid family or employees) are considering offering company-sponsored paid
medical leave. offering absence management. family/medical leave.
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
