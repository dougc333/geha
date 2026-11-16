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

Stop the container when finished:

```bash
docker compose down
```

The tested 30-page server output and result comparison are saved in `../verification/georgetown/server-local.md` and `../verification/georgetown/server-test.json`. This server is separate from the AWS worker: the deployed worker uses `DocumentConverter().convert()` inside a one-off Fargate task, while this Compose service accepts HTTP requests and stays up until stopped.
