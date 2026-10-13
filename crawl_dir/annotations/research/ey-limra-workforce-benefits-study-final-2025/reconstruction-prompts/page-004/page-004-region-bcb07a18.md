# Figure 1 reconstruction prompt

## User-directed method

Create an HTML equivalent of the supplied chart image using semantic HTML, Tailwind CSS,
supplemental inline CSS, and inline SVG where useful.

Work in this order:

1. Start with the bottom horizontal baseline and the text beneath it. Create three aligned
   groups labeled **Small**, **Midsize**, and **Large**, including their employee-count labels.
2. Match the source fonts as closely as possible before constructing the chart. Do not run an
   iterative font-size or font-family guessing loop.
3. Construct the Small stacked vertical bar. Match the yellow, dark-gray, and light-gray
   proportions using the displayed values as authoritative ratios:
   - Yellow: 57% of the total bar height.
   - Dark gray: 40% of the total bar height.
   - Light gray: 3% of the total bar height.
4. Add the **+7% change from 2023** annotation beside the Small bar.
5. Repeat the same procedure for the other two bars:
   - Midsize: 64% yellow, 35% dark gray, 1% light gray; +6% change from 2023.
   - Large: 67% yellow, 30% dark gray, 3% light gray; +5% change from 2023.
6. Preserve the chart title, question, percentage labels, baseline, leader lines, legend, colors,
   spacing, and reading order from the authoritative crop.
7. Include an accessible semantic data table that does not alter the visible layout.
8. Render at exactly **868 x 884 CSS pixels** and compare it side by side with the authoritative
   crop. Treat the displayed percentages and extracted PDF text as locked evidence.

## Figure-specific implementation evidence

- Authoritative crop: `../figure-01-playwright-chromium.png`
- Embedded typefaces: EYInterstate Light, Regular, and Bold
- Common bar height: 402 pixels
- Baseline: x=74 through x=732 at y=710
- Browser render: `verified.png`
- Browser-ready output: `verified.html`
