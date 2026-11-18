# Local Docling Serve

This runs the same pinned Docling Serve CPU image used by the AWS task, as a local HTTP server. It does not use AWS. The container listens only on `127.0.0.1:5011` on the Mac.

```bash
cd /Users/dc/geha/aws_docling/docker
docker compose up -d
docker compose ps
curl http://127.0.0.1:5011/health
```

Open the interactive API at [http://127.0.0.1:5011/docs](http://127.0.0.1:5011/docs). To convert the Georgetown paper into Markdown with embedded PNG figures:

```bash
python3 convert.py \
  /Users/dc/geha/crawl_dir/raw/benefits_research/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf
```

The output is `output/CRI_WP_Rao_Burke_EmpBen_Dec2025.md`. Choose a different path with `--output /path/to/result.md`. The conversion request uses `to_formats=md`, `image_export_mode=embedded`, and `include_images=true`. It returns the entire multipage document as one Markdown file. The API's default image scale makes the embedded PNG crops about twice the dimensions of those in `verification/georgetown/document-with-images.md`.

## Compare extraction options

`convert.py` passes these options to the pinned server's `/v1/convert/file` API:

| Purpose | Flags | Default |
| --- | --- | --- |
| Table structure | `--table-mode accurate\|fast`, `--no-cell-matching`, `--no-table-structure` | Accurate, cell matching on |
| Numeric chart data | `--chart-extraction`, `--chart-preset granite_vision_v4` | Off |
| Figure categories | `--classify-pictures` | Off |
| Figure descriptions | `--describe-pictures`, `--picture-description-preset smolvlm` | Off |
| Figure images | `--image-mode embedded\|placeholder`, `--image-scale 1`, `--no-images` | Embedded PNGs at 2× scale |
| Page images | `--page-images` | Off |

For the malformed Georgetown Table 4, compare the default with cell matching disabled:

```bash
python3 convert.py /path/to/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf \
  --output output/georgetown-default.md
python3 convert.py /path/to/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf \
  --no-cell-matching --output output/georgetown-no-cell-matching.md
```

To attempt chart-value extraction, use `--chart-extraction --chart-preset granite_vision_v4`. This loads a vision-language model and may need more memory and time. Check every numeric result against the PDF; the six saved PNG crops only verify image placement. Picture classification labels chart versus diagram or other image types, while picture description produces prose. Neither substitutes for verified chart numbers. Use `--format json` to inspect structured picture and chart metadata, or `--format html` for HTML output.

The `--table-mode fast --no-cell-matching` combination succeeded on Georgetown PDF page 19 and separated the Table 4 variable and statistic rows, but it omitted some standard errors and header text. It is a useful candidate for comparison, not a corrected Table 4. Save each variant under a different `--output` path and compare it with the PDF.

`--classify-pictures --format json` also succeeded on Georgetown page 11: it labeled the figure `bar_chart` with confidence 0.9998 in `pictures[0].meta.classification`. That label does not extract the bar values. Chart extraction and picture description flags are exposed but have not been exercised in this Docker setup.

Stop the container when finished:

```bash
docker compose down
```

The tested 30-page server output and result comparison are saved in `../verification/georgetown/server-local.md` and `../verification/georgetown/server-test.json`. This server is separate from the AWS worker: the deployed worker uses `DocumentConverter().convert()` inside a one-off Fargate task, while this Compose service accepts HTTP requests and stays up until stopped.
