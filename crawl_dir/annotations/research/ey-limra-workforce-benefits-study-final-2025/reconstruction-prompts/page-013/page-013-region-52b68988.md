# Page 13 · Figure 1

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Percent of employers and the data they seek**
Region ID: `page-013-region-52b68988`
Region type: `figure`
Embedded font evidence: EYInterstate-LightItalic, EYInterstate-Bold, EYInterstate-LightBold

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

- Normalized box: x1=13.979, y1=518.402, x2=976.855, y2=885.632
- Bar mapping status: ambiguous. Do not treat the extracted percentages as a sequence or assign them to bars.
- Positioned percentage tokens for visual verification only: 71% at (117.815, 487.757), 43% at (117.815, 592.597), 61% at (306.141, 487.757), 36% at (306.141, 592.597), 59% at (493.873, 487.757), 30% at (493.873, 592.597)
- Native text:

```text
Percent of employers and the data they seek
71% 61% 59%
Information on what Cost trends Participation rates
employees want
43% 36% 30%
Utilization rates Employee demographics What similar companies offer
Represents the percent of employers ranking items among their top three most important types of data
considered when making decisions about the design of benefits programs.
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
