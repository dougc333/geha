"""Compatibility CLI entrypoint for the centralized RAG application."""

from geha_processing.rag.cli import CliApplication, main

__all__ = ["CliApplication", "main"]


if __name__ == "__main__":
    from jsonargparse import CLI

    CLI(main)
