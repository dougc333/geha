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
