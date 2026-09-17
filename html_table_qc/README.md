# GEHA HTML table QC viewer

This local utility displays every `.html` file in
`/Users/dc/geha/downloads/coverage-policies/html_tables` in filename order. Each
table remains visible for three seconds before the next table loads.

Run:

```bash
cd /Users/dc/geha/html_table_qc
python3 qc_slideshow.py
```

The viewer opens at `http://127.0.0.1:8765/`. Use **Pause**, **Previous**, and
**Next**, or the space bar and arrow keys. Stop the server with `Ctrl-C`.

To change the delay:

```bash
python3 qc_slideshow.py --interval 5
```

To use another table directory:

```bash
python3 qc_slideshow.py --source /path/to/html_tables
```

## Paired table/PDF review

To cycle through available extracted tables while showing the matching source
PDF page in a second browser window:

```bash
cd /Users/dc/geha/html_table_qc
python3 paired_qc.py
```

In the table window, click **Open PDF window** once. The PDF window follows the
table window automatically, advancing to the source page for each table every
three seconds. Keep both windows visible side by side. **Pause**, **Previous**,
and **Next** control both views; uncheck **Loop** to stop at the end. Pop-ups must
be allowed for `127.0.0.1` if the PDF window does not appear. The server binds
only to localhost, and no files are uploaded or modified.

The table/PDF associations come from `html_tables/manifest.json`. Entries whose
HTML table or PDF has since been removed are skipped. To change the delay, use
`python3 paired_qc.py --interval 5`. Stop the server with `Ctrl-C`.
