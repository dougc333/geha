from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from aws_data_workflow.llamaparse_extraction import (
    extract_llamaparse_pages,
    extract_llamaparse_split_pages,
)


class LlamaParseExtractionTests(unittest.TestCase):
    def test_returns_page_numbered_markdown(self) -> None:
        captured = {}

        class Files:
            @staticmethod
            def create(**kwargs):
                captured["upload"] = kwargs
                return SimpleNamespace(id="file-1")

        class Parsing:
            @staticmethod
            def parse(**kwargs):
                captured["parse"] = kwargs
                return SimpleNamespace(
                    markdown=SimpleNamespace(
                        pages=[
                            SimpleNamespace(page_number=1, markdown="# One"),
                            SimpleNamespace(page_number=2, markdown="# Two"),
                        ]
                    )
                )

        class Client:
            files = Files()
            parsing = Parsing()

        def factory(**kwargs):
            captured["client"] = kwargs
            return Client()

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.pdf"
            source.write_bytes(b"pdf")
            pages = extract_llamaparse_pages(
                source,
                api_key="test-key",
                client_factory=factory,
            )
        self.assertEqual(pages, {1: "# One\n", 2: "# Two\n"})
        self.assertEqual(captured["client"], {"api_key": "test-key"})
        self.assertEqual(captured["parse"]["expand"], ["markdown"])

    def test_split_pages_only_submits_requested_fallback_pages(self) -> None:
        events = []

        class Files:
            @staticmethod
            def create(**kwargs):
                return SimpleNamespace(id="file-2")

        class Parsing:
            @staticmethod
            def create(**kwargs):
                return SimpleNamespace(id="job-2")

            @staticmethod
            def wait_for_completion(job_id):
                return SimpleNamespace(id=job_id)

            @staticmethod
            def get(job_id, **kwargs):
                return SimpleNamespace(
                    markdown=SimpleNamespace(
                        pages=[SimpleNamespace(markdown="# Fallback")]
                    )
                )

        class Client:
            files = Files()
            parsing = Parsing()

        with tempfile.TemporaryDirectory() as temporary:
            pages = Path(temporary)
            for number in (1, 2):
                page_dir = pages / f"page-{number:03d}"
                page_dir.mkdir()
                (page_dir / "source.pdf").write_bytes(b"pdf")
            output = extract_llamaparse_split_pages(
                pages,
                api_key="test-key",
                client_factory=lambda **kwargs: Client(),
                include_pages={2},
                on_status=lambda *event: events.append(event),
            )
        self.assertEqual(output, {2: "# Fallback\n"})
        self.assertEqual({event[0] for event in events}, {2})

    def test_split_pages_report_submitted_and_completed_status(self) -> None:
        events = []

        class Files:
            counter = 0

            @classmethod
            def create(cls, **kwargs):
                cls.counter += 1
                return SimpleNamespace(id=f"file-{cls.counter}")

        class Parsing:
            counter = 0

            @classmethod
            def create(cls, **kwargs):
                cls.counter += 1
                return SimpleNamespace(id=f"job-{cls.counter}")

            @staticmethod
            def wait_for_completion(job_id):
                return SimpleNamespace(id=job_id, status="COMPLETED")

            @staticmethod
            def get(job_id, **kwargs):
                return SimpleNamespace(
                    markdown=SimpleNamespace(
                        pages=[SimpleNamespace(markdown=f"# {job_id}")]
                    )
                )

        class Client:
            files = Files()
            parsing = Parsing()

        with tempfile.TemporaryDirectory() as temporary:
            pages_dir = Path(temporary) / "pages"
            for page_number in (1, 2):
                page_dir = pages_dir / f"page-{page_number:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "source.pdf").write_bytes(b"pdf")
            output = extract_llamaparse_split_pages(
                pages_dir,
                api_key="test-key",
                client_factory=lambda **kwargs: Client(),
                on_status=lambda *event: events.append(event),
            )

            self.assertEqual(output, {1: "# job-1\n", 2: "# job-2\n"})
            self.assertEqual(
                [(page, status) for page, status, _, _ in events],
                [(1, "submitted"), (1, "completed"), (2, "submitted"), (2, "completed")],
            )
            self.assertTrue((pages_dir / "page-001" / "llamaparse.md").is_file())


if __name__ == "__main__":
    unittest.main()

