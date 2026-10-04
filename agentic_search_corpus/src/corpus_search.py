"""Page-aware Markdown corpus search and optional original LangGraph agent."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import time
import numpy as np
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/Users/dc/geha/downloads/dental/fedvip')
DEFAULT_DIRS = [BASE / '2026-geha-dental-benefits-guide_pages', BASE / '2026-geha-dental-plan-brochure_pages']

def tokenize(text):
    return re.findall(r'[a-z0-9]+', text.lower())

def select_retrieval_mode(query):
    """Prefer lexical search only for exact CDT identifiers, not plain numbers."""
    return 'bm25' if re.search(r'\bD\d{4}\b', query, flags=re.I) else 'vector'

class CorpusSearch:
    def __init__(self, directories=DEFAULT_DIRS, mode='hybrid'):
        self.mode = mode
        self.docs = []
        # One source page per evidence unit preserves complete extracted tables.
        for directory in directories:
            directory = Path(directory)
            for path in sorted(directory.glob('page-*.md')):
                text = path.read_text()
                self.docs.append(Document(page_content=text, metadata={
                    'source': str(path), 'page': int(path.stem.split('-')[1]),
                    'document': directory.name, 'chunk_id': directory.name + '/' + path.name}))
        if not self.docs:
            raise ValueError('No page Markdown found in corpus directories')
        self.bm25 = BM25Okapi([tokenize(d.page_content) for d in self.docs])
        self.model = None
        self.vectors = None

    def load_vectors(self):
        if self.model is not None:
            return
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer('BAAI/bge-large-en-v1.5', local_files_only=True)
        # Token-safe windows prevent BGE silently dropping the ends of long pages.
        texts, owners = [], []
        for i, doc in enumerate(self.docs):
            ids = self.model.tokenizer.encode(doc.page_content, add_special_tokens=False)
            for start in range(0, len(ids), 360):
                texts.append(self.model.tokenizer.decode(ids[start:start + 440]))
                owners.append(i)
        self.owners = np.array(owners)
        digest = hashlib.sha256(('BAAI/bge-large-en-v1.5:440:360:' + '\n'.join(
            d.metadata['chunk_id'] + d.page_content for d in self.docs)).encode()).hexdigest()
        cache = ROOT / 'indexes'
        cache.mkdir(exist_ok=True)
        path = cache / (digest + '.npy')
        if path.exists():
            self.vectors = np.load(path)
        else:
            self.vectors = self.model.encode(texts, normalize_embeddings=True, batch_size=16)
            np.save(path, self.vectors)
        (cache / 'manifest.json').write_text(json.dumps({'model': 'BAAI/bge-large-en-v1.5',
            'pages': len(self.docs), 'vector_windows': len(texts), 'vectors': path.name,
            'sources': [d.metadata for d in self.docs]}, indent=2))

    def search(self, query, top_k=10, mode=None):
        mode = mode or self.mode
        if mode == 'auto':
            mode = select_retrieval_mode(query)
        lexical = self.bm25.get_scores(tokenize(query))
        bm_rank = np.argsort(-lexical, kind='stable')
        if mode == 'bm25':
            ranks = [i for i in bm_rank if lexical[i] > 0]
        else:
            self.load_vectors()
            vector = self.model.encode('Represent this sentence for searching relevant passages: ' + query,
                                       normalize_embeddings=True)
            scores = np.full(len(self.docs), -np.inf)
            np.maximum.at(scores, self.owners, self.vectors @ vector)
            vector_rank = np.argsort(-scores, kind='stable')
            if mode == 'vector':
                ranks = vector_rank
            elif mode == 'hybrid':
                fused = np.zeros(len(self.docs))
                for ranking in ([i for i in bm_rank if lexical[i] > 0][:30], vector_rank[:30]):
                    for rank, i in enumerate(ranking, 1):
                        fused[i] += 1 / (60 + rank)
                ranks = np.argsort(-fused, kind='stable')
            else:
                raise ValueError(mode)
        return [self.docs[int(i)] for i in list(ranks)[:top_k]]

    def invoke(self, query):
        return self.search(query)

class EvidenceReranker:
    def rerank(self, docs, query, model='none'):
        return ['[' + d.metadata['chunk_id'] + ']\n' + d.page_content for d in docs]

def make_agent(search):
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from agentic_rag import AgenticRag
    class Client:
        retriever = search
        reranker = EvidenceReranker()
        llm = ChatOpenAI(model='gpt-4o', temperature=0)
        chain = ChatPromptTemplate.from_template(
            'Answer only from the 2026 dental evidence. Cite [document/page-NNN.md] for each '
            'claim. Distinguish discounts from insurance benefits. State missing information. '
            'QUESTION: {question}\nEVIDENCE: {context}') | llm | StrOutputParser()
        @staticmethod
        def format_context(contexts):
            return '\n\n'.join(contexts)
    return AgenticRag(Client())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('query')
    parser.add_argument('--mode', choices=['bm25', 'vector', 'hybrid'], default='hybrid')
    parser.add_argument('--directories', nargs='+', type=Path, default=DEFAULT_DIRS)
    parser.add_argument('--agentic', action='store_true')
    args = parser.parse_args()
    search = CorpusSearch(args.directories, args.mode)
    if args.agentic:
        print(json.dumps(make_agent(search).generate(args.query), indent=2))
    else:
        for doc in search.search(args.query):
            print(doc.metadata['chunk_id'])
            print(doc.page_content[:300], '\n')

if __name__ == '__main__':
    main()
