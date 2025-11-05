import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from transformers import AutoTokenizer, AutoModelForQuestionAnswering
import torch
from pathlib import Path
import os
import json
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
import multiprocessing as mp
mp.set_start_method("forkserver", force=True)

# Data paths (load index & chunks from src/data/embedding)
EMBEDDING_DIR = Path(__file__).resolve().parents[2] / 'data' / 'embedding'

INDEX_FILE = EMBEDDING_DIR / 'document_index.faiss'
CHUNKS_FILE = EMBEDDING_DIR / 'document_chunks.json'

EMBEDDING_MODEL = 'nomic-ai/nomic-embed-text-v1'

# This is a good, small, extractive QA model (BERT-based)
QA_MODEL_NAME = 'bert-large-uncased-whole-word-masking-finetuned-squad'

class HybridRerankRetriever:
    """
    Combines FAISS (semantic) + BM25 (keyword) retrieval,
    then reranks the merged candidates using a local cross-encoder model.
    """

    def __init__(
        self,
        embed_model_path: str,
        index_path: str,
        chunks_path: str,
        rerank_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        # 1️⃣ Load embedding model
        self.embed_model = SentenceTransformer(embed_model_path, trust_remote_code=True)
        # 2️⃣ Load FAISS index
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"❌ FAISS index not found: {index_path}")
        self.index = faiss.read_index(str(index_path))

        # 3️⃣ Load chunks
        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"❌ Chunks file not found: {chunks_path}")
        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        # 4️⃣ Prepare BM25 keyword index
        tokenized = [chunk.lower().split() for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized)

        # 5️⃣ Load reranker (local cross-encoder)
        self.reranker = CrossEncoder(rerank_model_name)

        print("✅ HybridRerankRetriever initialized successfully!")

    # --- semantic + lexical retrieval ---
    def retrieve(self, query: str, k: int = 10, alpha: float = 0.7):
        """Perform hybrid retrieval: FAISS (semantic) + BM25 (lexical)."""
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Semantic search via FAISS
        q_emb = self.embed_model.encode([query], device=device)
        q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
        scores, idxs = self.index.search(q_emb, k)
        faiss_results = [(int(i), float(scores[0][n])) for n, i in enumerate(idxs[0])]

        # Lexical search via BM25
        bm25_scores = self.bm25.get_scores(query.lower().split())
        bm25_top = np.argsort(bm25_scores)[::-1][:k]
        bm25_results = [(int(i), float(bm25_scores[i])) for i in bm25_top]

        # Merge with weighting
        all_scores = {}
        for i, s in faiss_results:
            all_scores[i] = all_scores.get(i, 0) + alpha * s
        for i, s in bm25_results:
            all_scores[i] = all_scores.get(i, 0) + (1 - alpha) * s

        ranked = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return [(self.chunks[i], score) for i, score in ranked]

    # --- rerank for precision ---
    def rerank(self, query: str, candidates: list, top_k: int = 5):
        """Re-score candidates using a local cross-encoder."""
        pairs = [(query, c) for c, _ in candidates]
        scores = self.reranker.predict(pairs)
        reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [(text, float(score)) for ((text, _), score) in reranked[:top_k]]

    # --- single call helper ---
    def search(self, query: str, top_k: int = 5, alpha: float = 0.7):
        hybrid_candidates = self.retrieve(query, k=top_k * 2, alpha=alpha)
        reranked = self.rerank(query, hybrid_candidates, top_k=top_k)
        return reranked

def chatbot_service(user_q):
    retriever = HybridRerankRetriever(
        embed_model_path=EMBEDDING_MODEL,
        index_path=INDEX_FILE,
        chunks_path=CHUNKS_FILE,
    )

    context_snippets = retriever.search(user_q)

    context_text = "\n\n".join([c for c, _ in context_snippets])

    qa_tokenizer = AutoTokenizer.from_pretrained(QA_MODEL_NAME)
    qa_model = AutoModelForQuestionAnswering.from_pretrained(QA_MODEL_NAME)

    inputs = qa_tokenizer.encode_plus(
        user_q,
        context_text,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )

    with torch.no_grad():
        outputs = qa_model(**inputs)
    start_scores = outputs.start_logits
    end_scores = outputs.end_logits

    # pick the most likely start and end token
    start_idx = torch.argmax(start_scores, dim=1).item()
    end_idx = torch.argmax(end_scores, dim=1).item()

    input_ids = inputs["input_ids"][0].tolist()

    # guard: if end before start, swap or return fallback
    if end_idx < start_idx:
        return "Unable to find a concise answer."

    answer_ids = input_ids[start_idx : end_idx + 1]
    answer = qa_tokenizer.decode(answer_ids, skip_special_tokens=True).strip()

    if not answer:
        return "No answer found in the retrieved context."
    return answer