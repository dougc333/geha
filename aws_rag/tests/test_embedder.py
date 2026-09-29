"""Embedder Lambda (embedder/handler.py) with fake Bedrock, S3 and Postgres."""

import io
import json
import unittest
from unittest import mock

from support import load

handler = load("embedder_handler", "embedder/handler.py")


class ModelErrorException(Exception):
    pass


def fake_bedrock(failures: int):
    """invoke_model fails `failures` times with ModelErrorException, then succeeds."""
    client = mock.Mock()
    client.exceptions.ModelErrorException = ModelErrorException
    outcomes = [ModelErrorException("try again")] * failures
    outcomes.append({"body": io.BytesIO(json.dumps({"embedding": [0.1, 0.2]}).encode())})
    client.invoke_model.side_effect = outcomes
    return client


class EmbedRetryTest(unittest.TestCase):
    """Titan's occasional ModelErrorException failed Llama 3 (274 chunks) on every retry."""

    @mock.patch.object(handler.time, "sleep")
    def test_retries_then_succeeds(self, sleep):
        client = fake_bedrock(failures=2)
        with mock.patch.object(handler, "bedrock", client):
            self.assertEqual(handler.embed("text"), [0.1, 0.2])
        self.assertEqual(client.invoke_model.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @mock.patch.object(handler.time, "sleep")
    def test_gives_up_after_four_attempts(self, _sleep):
        client = fake_bedrock(failures=4)
        with mock.patch.object(handler, "bedrock", client), self.assertRaises(ModelErrorException):
            handler.embed("text")
        self.assertEqual(client.invoke_model.call_count, 4)

    def test_long_text_is_truncated(self):
        client = fake_bedrock(failures=0)
        with mock.patch.object(handler, "bedrock", client):
            handler.embed("x" * (handler.MAX_EMBED_CHARS + 500))
        body = json.loads(client.invoke_model.call_args.kwargs["body"])
        self.assertEqual(len(body["inputText"]), handler.MAX_EMBED_CHARS)


class ProcessTest(unittest.TestCase):
    def run_process(self, lines: list[dict]):
        s3 = mock.Mock()
        s3.get_object.return_value = {"Body": io.BytesIO("\n".join(map(json.dumps, lines)).encode())}
        connection = mock.MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        with mock.patch.object(handler, "s3", s3), \
                mock.patch.object(handler, "embed", side_effect=lambda text: [float(len(text))]), \
                mock.patch.object(handler, "database_url", return_value="postgresql://x"), \
                mock.patch.object(handler, "register_vector"), \
                mock.patch.object(handler.psycopg, "connect", return_value=connection):
            handler.process("bucket", "chunks/doc.jsonl")
        return cursor

    def test_rows_sorted_nul_stripped_and_image_kept(self):
        base = {"document_id": "doc", "source": "docling:x.pdf", "title": "Paper"}
        cursor = self.run_process([
            {**base, "chunk_index": 1, "page_number": 3, "content": "Figure (page 3)",
             "kind": "figure", "image": "figures/doc/p003_f01.png"},
            {**base, "chunk_index": 0, "page_number": 1, "content": "text\x00 here"},
        ])
        cursor.execute.assert_any_call("DELETE FROM rag_chunks WHERE document_id = %s", ("doc",))
        rows = cursor.executemany.call_args.args[1]
        self.assertEqual([r[1] for r in rows], [0, 1])  # sorted by chunk_index
        self.assertEqual(rows[0][3], "text here")        # NUL removed (Postgres rejects it)
        self.assertIsNone(rows[0][5])                    # text chunk: no image
        self.assertEqual(rows[1][5], "figures/doc/p003_f01.png")

    def test_empty_file_fails(self):
        with self.assertRaises(ValueError):
            self.run_process([])


if __name__ == "__main__":
    unittest.main()
