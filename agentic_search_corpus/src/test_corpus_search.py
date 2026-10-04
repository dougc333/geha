import tempfile
import unittest
from pathlib import Path
from corpus_search import CorpusSearch

class CorpusTests(unittest.TestCase):
    def test_exact_code_preserves_source_and_table(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            text = '| Procedure | Limit |\n| D1110 | three cleanings |'
            (path / 'page-001.md').write_text(text)
            (path / 'page-002.md').write_text('Eligibility federal employees')
            (path / 'page-003.md').write_text('Enrollment dates')
            (path / 'page-001.html').write_text('duplicate should not be indexed')
            search = CorpusSearch([path], mode='bm25')
            self.assertEqual(len(search.docs), 3)
            result = search.search('D1110')
            self.assertEqual(result[0].metadata['page'], 1)
            self.assertEqual(result[0].page_content, text)
            self.assertEqual(search.search('xyzabsent'), [])

    def test_empty_corpus_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                CorpusSearch([directory])

if __name__ == '__main__':
    unittest.main()
