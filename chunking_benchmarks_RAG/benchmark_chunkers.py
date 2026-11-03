"""Compatibility CLI for the centralized chunking benchmark."""

from geha_processing.benchmarks.chunkers import main, percentile, summarize, write_chunks

__all__ = ["main", "percentile", "summarize", "write_chunks"]


if __name__ == "__main__":
    main()
