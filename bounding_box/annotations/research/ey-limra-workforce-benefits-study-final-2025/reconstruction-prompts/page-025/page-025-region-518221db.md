# Page 25 · Figure 1

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Based on a recent EY-Parthenon workforce benefits GenAI survey**
Region ID: `page-025-region-518221db`
Region type: `figure`
Embedded font evidence: EYInterstate-Bold, EYInterstate-LightBold, EYInterstate-Regular, EYInterstate-Light

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

- Normalized box: x1=5.873, y1=208.695, x2=997.656, y2=702.971
- Bar mapping status: ambiguous. Do not treat the extracted percentages as a sequence or assign them to bars.
- Positioned percentage tokens for visual verification only: 92% at (118.998, 226.85), 46% at (306.242, 226.85), 62% at (493.885, 226.85)
- Native text:

```text
Based on a recent EY-Parthenon workforce benefits GenAI survey
92% 46% 62%
of group benefits carriers of carriers expect AI/GenAI to of group carriers are
surveyed stated they have drive 5%–10% revenue uplift. deliberately targeting distinct
dedicated and/or mobilized portions of the value chain to
teams to focus on GenAI drive value.
initiatives.
Source: EY-Parthenon 2024 Group Benefits GenAI Carrier Survey.
Majority of brokers believe AI will drive disruption, but in targeted areas
Service
Sales and Underwriting Implementation Enrollment Eligibility Billing and Claims
distribution payments
None/less relevant Highly relevant
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
