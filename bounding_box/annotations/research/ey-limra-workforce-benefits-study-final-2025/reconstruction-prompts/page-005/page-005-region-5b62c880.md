# Page 5 · Figure 3

Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.

Likely figure heading: **Employers expect to use**
Region ID: `page-005-region-5b62c880`
Region type: `figure`
Embedded font evidence: EYInterstate-Bold, EYInterstate-Regular, EYInterstate-Light

## Ordered reconstruction strategy

1. Start with the shared horizontal baseline and place the Today and In five years labels beneath equal-width stacked bars.
2. Build the legend in this exact top-to-bottom category and color order: orange = 50% or more; coral = 25% to 49%; blue = 10% to 24%; teal = Less than 10%; green = None.
3. Construct the Today bar from top to bottom as 4% orange, 8% coral, 16% blue, 37% teal, and 35% green.
4. Construct the In five years bar from top to bottom as 6% orange, 11% coral, 23% blue, 39% teal, and 23% green.
5. Place every percentage inside its corresponding colored segment, preserving the source's white text and relative segment heights.
6. Add the left 65% and right 77% bracket annotations exactly as displayed; treat them as independent source annotations and do not recompute them from rounded segment labels.
7. Preserve the title, question, bar spacing, baseline, background, bracket geometry, and legend placement.
8. Include an accessible semantic table with category, Today, and In five years values without changing the visible layout.
9. Render at the authoritative crop's exact pixel dimensions and perform a side-by-side check for clipping, overlap, scale, spacing, text, and data relationships.

## Locked evidence

- Normalized box: x1=505.511, y1=514.51, x2=954.785, y2=920.733
- Legend thresholds and colors: orange = 50% or more; coral = 25% to 49%; blue = 10% to 24%; teal = Less than 10%; green = None.
- Today, top to bottom: 4%, 8%, 16%, 37%, 35%; displayed bracket annotation: 65%.
- In five years, top to bottom: 6%, 11%, 23%, 39%, 23%; displayed bracket annotation: 77%.
- Preserve displayed rounded values exactly; do not normalize or replace them with derived totals.
- Native text:

```text
Figure 3
Employers expect to use
more freelance workers in the
future.
50% or more
QUESTION: Approximately what percent 25% to 49%
of your company’s workers are currently 10% to 24%
contract/freelance workers? In five years, Less than 10%
what percent of your company’s workers None
will be contract/freelance workers?
4% 6%
8% 11%
16%
23%65%
77%
37%
39%
35%
23%
Today In five years
```

Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.
