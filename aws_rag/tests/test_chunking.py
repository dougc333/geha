"""Text chunking (chunker/rag_core.py) and Docling table chunks (local_ingest/docling_chunks.py)."""

import hashlib
import json
import unittest

from support import load

rag_core = load("chunker_rag_core", "chunker/rag_core.py")
docling_chunks = load("docling_chunks", "local_ingest/docling_chunks.py")


class ChunkTextTest(unittest.TestCase):
    def test_chunks_overlap_by_50_words(self):
        words = [f"w{i}" for i in range(700)]
        chunks = rag_core.chunk_text(" ".join(words))
        self.assertEqual([len(c.split()) for c in chunks], [350, 350, 100])
        self.assertEqual(chunks[1].split()[0], "w300")  # starts 300 words (350 - 50) in

    def test_short_and_empty_text(self):
        self.assertEqual(rag_core.chunk_text("just a few words"), ["just a few words"])
        self.assertEqual(rag_core.chunk_text("  \n "), [])

    def test_rejects_bad_sizes(self):
        with self.assertRaises(ValueError):
            rag_core.chunk_text("x", size=50, overlap=50)


class ValidatedSidecarTest(unittest.TestCase):
    SOURCE_SHA = "a" * 64

    @staticmethod
    def page(number, content, status="matched"):
        return {
            "page_number": number,
            "validation_status": status,
            "content": content,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }

    def payload(self):
        return {
            "schema_version": 1,
            "source_sha256": self.SOURCE_SHA,
            "validation_status": "validated",
            "page_count": 2,
            "pages": [self.page(1, "alpha beta"), self.page(2, "gamma delta")],
        }

    def test_validates_and_chunks_page_text(self):
        pages, evidence = rag_core.validated_pages(
            json.dumps(self.payload()).encode(), source_sha256=self.SOURCE_SHA
        )
        chunks = rag_core.chunk_validated_pages(pages, size=2, overlap=0)
        self.assertEqual(evidence["validation_status"], "validated")
        self.assertEqual([c["page_number"] for c in chunks], [1, 2])
        self.assertEqual([c["chunk_index"] for c in chunks], [0, 1])

    def test_rejects_sidecar_for_another_pdf(self):
        with self.assertRaisesRegex(ValueError, "source PDF SHA-256"):
            rag_core.validated_pages(self.payload(), source_sha256="b" * 64)

    def test_rejects_page_that_did_not_match(self):
        payload = self.payload()
        payload["pages"][1] = self.page(2, "gamma delta", status="needs_human_review")
        with self.assertRaisesRegex(ValueError, "not visually matched"):
            rag_core.validated_pages(payload, source_sha256=self.SOURCE_SHA)

    def test_rejects_changed_page_content(self):
        payload = self.payload()
        payload["pages"][0]["content"] = "tampered"
        with self.assertRaisesRegex(ValueError, "content SHA-256"):
            rag_core.validated_pages(payload, source_sha256=self.SOURCE_SHA)


def table(rows: int, row_text: str = "value") -> str:
    lines = ["| name | score |", "|---|---|"]
    lines += [f"| {row_text} {i} | {i} |" for i in range(rows)]
    return "\n".join(lines)


class TableChunksTest(unittest.TestCase):
    def test_small_table_is_one_chunk_with_caption(self):
        chunks = docling_chunks.table_chunks("Table 1: Scores.", table(3))
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("Table 1: Scores.\n\n| name | score |"))

    def test_long_table_splits_by_rows_and_repeats_header(self):
        chunks = docling_chunks.table_chunks("Table 2: Many rows.", table(400, "x" * 40))
        self.assertGreater(len(chunks), 1)
        for i, chunk in enumerate(chunks, 1):
            self.assertIn(f"(part {i} of {len(chunks)})", chunk)
            self.assertIn("| name | score |\n|---|---|", chunk)
            self.assertLessEqual(len(chunk), docling_chunks.MAX_TABLE_CHARS + 100)  # + caption

    def test_oversized_row_is_cut(self):
        # T5 had one ~14,000-character row, over Titan's token limit.
        chunks = docling_chunks.table_chunks("Table 3: One huge row.", table(1, "y" * 14000))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= docling_chunks.MAX_TABLE_CHARS + 100 for c in chunks))

    def test_compact_markdown_drops_padding(self):
        padded = "| name     | score   |\n|----------|---------|\n| a        | 1       |"
        self.assertEqual(docling_chunks.compact_markdown(padded),
                         "| name | score |\n|---|---|\n| a | 1 |")


class FigureFilterTest(unittest.TestCase):
    def test_captioned_wide_strips_are_kept(self):
        # YOLO Figure 1 (475x98) and Atari's screenshots (794x103) used to be dropped.
        self.assertTrue(docling_chunks.keep_figure(475, 98, "Figure 1: The YOLO Detection System."))
        self.assertTrue(docling_chunks.keep_figure(794, 103, "Figure 1: Screen shots from five Atari games"))

    def test_small_uncaptioned_images_are_skipped(self):
        self.assertFalse(docling_chunks.keep_figure(303, 41, ""))    # a rule or logo strip
        self.assertFalse(docling_chunks.keep_figure(73, 147, ""))
        self.assertTrue(docling_chunks.keep_figure(131, 252, ""))    # big enough without a caption


class CarryDescriptionsTest(unittest.TestCase):
    def fig(self, file, page, caption, **extra):
        return {"file": file, "page": page, "caption": caption, "width": 400, "height": 300, **extra}

    def test_descriptions_follow_the_figure_not_the_file_name(self):
        old = [self.fig("p006_f01.png", 6, "Figure 4: Error analysis.", description="pie charts")]
        # A newly kept figure on page 1 shifts the numbering: page 6 is now f02.
        new = [self.fig("p001_f01.png", 1, "Figure 1: The YOLO Detection System."),
               self.fig("p006_f02.png", 6, "Figure 4: Error analysis.")]
        self.assertEqual(docling_chunks.carry_descriptions(old, new), 1)
        self.assertNotIn("description", new[0])
        self.assertEqual(new[1]["description"], "pie charts")


class FigurePdfTextTest(unittest.TestCase):
    def test_reads_only_the_text_inside_the_figure_box(self):
        import pymupdf
        pdf = pymupdf.open()
        page = pdf.new_page(width=600, height=800)
        page.insert_text((100, 120), "Test AUC")           # inside the figure
        page.insert_text((100, 160), "global eps=0.3")     # inside the figure
        page.insert_text((100, 400), "Body text below")    # outside
        self.assertEqual(docling_chunks.figure_pdf_text(page, (90, 100, 300, 180)),
                         "Test AUC | global eps=0.3")
        self.assertEqual(docling_chunks.figure_pdf_text(page, (300, 500, 500, 700)), "")


if __name__ == "__main__":
    unittest.main()
