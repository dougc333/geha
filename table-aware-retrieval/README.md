# Table-Aware Retrieval

*RAG architecture note*

Most chunking pipelines slice documents into fixed-size windows, and a table caught inside one gets sliced along with everything else — headers end up in a different chunk than the rows that give them meaning. A table-aware pipeline detects table regions during parsing, keeps each one whole, and indexes it by a short generated summary. When a query matches that summary, the retriever hands back the entire table as one unit — not the single row or cell that happened to match.

![Pipeline diagram: a document is parsed into text chunks and intact tables; text chunks are embedded into a vector index while tables are stored whole in a table store and represented in the index only by a summary vector. At query time the index is searched, and a table match is resolved by fetching the full table from the table store before it reaches the model.](figures/01-table-aware-pipeline.png)

FIG. 1 Ingestion keeps every table region intact and files it in the table store under an id; the vector index only ever holds a summary vector for it. A retrieval hit on that summary triggers one extra hop — a lookup by id — that returns the full table before it reaches the model.

[View scalable SVG](figures/01-table-aware-pipeline.svg)

The difference is invisible until a query lands on a table row. Chunk a table and the retriever can only hand back the fragment that matched — a number with no header. Keep it whole and the retriever hands back the number's entire context.

![Comparison diagram: the same query and the same source table run through two retrieval strategies. Row-level chunking shreds the table into disconnected row fragments, so the model receives a bare number with no header context. Table-aware retrieval keeps the table whole, so the model receives region, quarter, and value together.](figures/02-retrieval-comparison.png)

FIG. 2 Same table, same query, two outcomes. Row-level chunking hands the model an orphaned number; table-aware retrieval hands it the row inside its table — header, neighboring rows, and units all still attached.

[View scalable SVG](figures/02-retrieval-comparison.svg)

## Conversion notes

Converted from the locally saved `Table-Aware Retrieval.html` and its companion `Table-Aware Retrieval_files/_t.html`. Original explanatory text, figure labels, and captions are preserved; browser chrome and runtime scripts are excluded. The figures are illustrative architecture examples, not measured evaluation results or a claim that this pipeline is already implemented in the GEHA app.

Figures are supplied as standalone SVGs and PNGs. The light palette is retained; local Arial and Menlo fonts replace web-hosted fonts so the assets do not require network access. Keep the `figures/` folder beside this README when copying it.

The original example numbers and claims have not been fact-checked or silently corrected. In particular, the comparison artwork is schematic and does not constitute a benchmark of row-level versus whole-table retrieval.
