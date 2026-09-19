"""Export the exact RAG demo Chroma documents in source/page order."""

from collections import defaultdict

from rag import ROOT, Retriever


def main() -> None:
    retriever = Retriever()
    stored = retriever.collection.get(include=["documents", "metadatas"])
    by_id = {
        chunk_id: (document, metadata)
        for chunk_id, document, metadata in zip(
            stored["ids"], stored["documents"], stored["metadatas"], strict=True
        )
    }
    if set(by_id) != {chunk["id"] for chunk in retriever.chunks}:
        raise ValueError("Stored Chroma chunks differ from the current source documents")

    by_source = defaultdict(list)
    for chunk in retriever.chunks:
        document, metadata = by_id[chunk["id"]]
        if document != chunk["text"] or metadata != chunk["metadata"]:
            raise ValueError(f"Stored chunk differs from source: {chunk['id']}")
        by_source[metadata["source_file"]].append((chunk["id"], metadata, document))

    sources = sorted((ROOT / "data" / "sources").glob("*.pdf"))
    if {path.name for path in sources} != set(by_source):
        raise ValueError("Source PDFs differ from indexed PDFs")

    output = ROOT / "indexed_chunks.txt"
    with output.open("w", encoding="utf-8") as stream:
        stream.write(f"Indexed text chunks from {ROOT / 'data' / 'sources'}\n")
        stream.write(f"Collection: {retriever.collection.name}\n")
        stream.write("These are the exact text documents stored in Chroma; embeddings are not shown.\n")
        stream.write("PDFs are in filename order, then page and chunk order. No OCR was used.\n\n")
        for source in sources:
            chunks = by_source[source.name]
            stream.write("=" * 90 + "\n")
            stream.write(f"SOURCE: {source}\n")
            stream.write(f"CHUNKS: {len(chunks)}\n")
            stream.write("=" * 90 + "\n\n")
            per_page = defaultdict(int)
            for chunk_id, metadata, document in chunks:
                page = metadata["page"]
                per_page[page] += 1
                stream.write(
                    f"--- Page {page}, chunk {per_page[page]} | ID: {chunk_id} "
                    f"| kind: {metadata['kind']} ---\n"
                )
                stream.write(document + "\n\n")
    print(f"Wrote {len(sources)} PDFs and {len(by_id)} chunks to {output}")


if __name__ == "__main__":
    main()
