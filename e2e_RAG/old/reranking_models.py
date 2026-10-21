from transformers import AutoTokenizer, AutoModel
from openai import OpenAI
from functools import lru_cache
import torch
import torch.nn.functional as F
import time
import json
import cohere
import os


# Function to compute MaxSim
def maxsim(
    query_embedding,
    document_embedding,
    query_attention_mask=None,
    document_attention_mask=None,
):
    """Compute token-level ColBERT-style late-interaction scores."""
    query_embedding = F.normalize(query_embedding, p=2, dim=-1)
    document_embedding = F.normalize(document_embedding, p=2, dim=-1)

    # [batch, query_tokens, document_tokens]
    similarity = torch.einsum(
        "bqh,bdh->bqd",
        query_embedding,
        document_embedding,
    )

    if document_attention_mask is not None:
        similarity = similarity.masked_fill(
            ~document_attention_mask[:, None, :].bool(),
            -torch.inf,
        )

    max_sim_scores = similarity.max(dim=-1).values

    if query_attention_mask is None:
        return max_sim_scores.mean(dim=-1)

    query_mask = query_attention_mask.to(max_sim_scores.dtype)
    return (max_sim_scores * query_mask).sum(dim=-1) / query_mask.sum(
        dim=-1
    ).clamp_min(1)


@lru_cache(maxsize=1)
def load_colbert_model():
    """Load ColBERT once and reuse it for every Streamlit query."""
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    tokenizer = AutoTokenizer.from_pretrained("colbert-ir/colbertv2.0")
    model = AutoModel.from_pretrained("colbert-ir/colbertv2.0")
    model.to(device)
    model.eval()
    return tokenizer, model, device

def reranking_gpt(similar_chunks, query):

    start = time.time()
    client = OpenAI()
    response = client.chat.completions.create(
        model='gpt-4-1106-preview',
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
        {"role": "system", 
        "content": """You are an expert relevance ranker. Given a list of documents and a query, your job is to determine how relevant each document is for answering the query. 
        Your output is JSON, which is a list of documents.  Each document has two fields, content and score.  relevance_score is from 0.0 to 100.0. Higher relevance means higher score."""},
        {"role": "user", "content": f"Query: {query} Docs: {similar_chunks}"}
        ]
    )

    print(f"Took {time.time() - start} seconds to re-rank documents with GPT-4.")

    # Sort the scores by highest to lowest and print
    scores = json.loads(response.choices[0].message.content)["documents"]
    sorted_data = sorted(scores, key=lambda x: x['score'], reverse=True)

    documents = []
    for idx, r in enumerate(sorted_data):
        documents.append(f"{r['content']}")
    return documents


def reranking_colbert(similar_chunks, query):

    start = time.time()
    scores = []

    tokenizer, model, device = load_colbert_model()

    query_encoding = tokenizer(
        query,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    ).to(device)

    with torch.inference_mode():
        query_embedding = model(**query_encoding).last_hidden_state

        for document in similar_chunks:
            document_encoding = tokenizer(
                document.page_content,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            ).to(device)
            document_embedding = model(
                **document_encoding
            ).last_hidden_state

            score = maxsim(
                query_embedding,
                document_embedding,
                query_encoding.get("attention_mask"),
                document_encoding.get("attention_mask"),
            )
            scores.append({
                "score": score.item(),
                "document": document.page_content,
            })

    print(f"Took {time.time() - start} seconds to re-rank documents with ColBERT.")

    # Sort the scores by highest to lowest and print
    sorted_data = sorted(scores, key=lambda x: x['score'], reverse=True)
    documents = []
    for idx, r in enumerate(sorted_data):
        documents.append(f"{r['document']}")
    
    return documents


def reranking_cohere(similar_chunks, query):
    # Get your cohere API key on: www.cohere.com
    co = cohere.Client(os.environ["COHERE_API_KEY"])

    documents = [f"{doc.page_content}" for doc in similar_chunks]
    # Example query and passages
    start = time.time()

    results = co.rerank(query=query, 
                        documents=documents, 
                        top_n=4, 
                        model="rerank-english-v3.0", 
                        return_documents=True)
    print(f"Took {time.time() - start} seconds to re-rank documents with Cohere.")

    documents = []
    for idx, r in enumerate(results.results):
        documents.append(f"{r.document.text}")

    return documents
