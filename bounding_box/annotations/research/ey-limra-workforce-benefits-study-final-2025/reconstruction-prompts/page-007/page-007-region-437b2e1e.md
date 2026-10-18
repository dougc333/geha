# Page 7 · Figure 1

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **As of 2024, Gen Z workers outnumber baby boomers, with**
Region ID: `page-007-region-437b2e1e`
Region type: `figure`
Embedded font evidence: EYInterstate-Bold, EYInterstate-Light

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

- Normalized box: x1=5.818, y1=349.992, x2=1000.0, y2=788.092
- Bar mapping status: ambiguous. Do not treat the extracted percentages as a sequence or assign them to bars.
- Positioned percentage tokens for visual verification only: 30% at (530.107, 370.074), 36% at (77.709, 504.757), 31% at (192.214, 504.757), 18% at (303.696, 504.757), 15% at (420.68, 504.757), 1% at (531.046, 504.757)
- Native text:

```text
As of 2024, Gen Z workers outnumber baby boomers, with
millennials representing the largest generational cohort in the
workforce. By 2030, Gen Z workers will account for more than 30%
of the workforce, according to the U.S. Bureau of Labor Statistics.
Share of the U.S. labor force, by generation
36% 31% 18% 15% 1%
Millennials Gen X Gen Z Baby boomers Silent Generation
Source: “Changes in the U.S. Labor Supply,” Trendlines, U.S. Department of Labor, Employment and Training Administration, August 2024.
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
