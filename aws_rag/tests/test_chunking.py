"""Text chunking (chunker/rag_core.py) and Docling table chunks (local_ingest/docling_chunks.py)."""

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


if __name__ == "__main__":
    unittest.main()
