import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForQuestionAnswering
import torch
from pathlib import Path
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
import multiprocessing as mp
mp.set_start_method("forkserver", force=True)

# Data paths (load index & chunks from src/data/embedding)
EMBEDDING_DIR = Path(__file__).resolve().parents[2] / 'data' / 'embedding'

INDEX_FILE = EMBEDDING_DIR / 'document_index.faiss'
CHUNKS_FILE = EMBEDDING_DIR / 'document_chunks.txt'

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
# This is a good, small, extractive QA model (BERT-based)
QA_MODEL_NAME = 'bert-large-uncased-whole-word-masking-finetuned-squad'

# --- helper ---
def _load_qa_components():
    global document_chunks

    # Load FAISS index
    index_path = str(INDEX_FILE)
    if not INDEX_FILE.exists():
        raise FileNotFoundError(f"FAISS index not found at {index_path}")
    index = faiss.read_index(index_path)

    # Load chunks
    chunks_path = CHUNKS_FILE
    if not chunks_path.exists():
        raise FileNotFoundError(f"Document chunks file not found at {chunks_path}")
    with open(chunks_path, 'r', encoding='utf-8') as f:
        document_chunks = [line for line in f.read().split('\n') if line.strip()]

    # Load the specialized QA Model and Tokenizer
    qa_tokenizer = AutoTokenizer.from_pretrained(QA_MODEL_NAME)
    qa_model = AutoModelForQuestionAnswering.from_pretrained(QA_MODEL_NAME)
    
    return index, qa_tokenizer, qa_model


def _answer_question(question, index, chunks, embed_model, qa_tokenizer, qa_model, k=3):
    """
    Performs Semantic Retrieval and Extractive QA.
    """

    question_embedding = embed_model.encode([question])
    # D is distance, I is the index of the best chunk
    D, I = index.search(question_embedding, k) 
    
    # Get the best context chunk based on index I[0][0]
    best_context = chunks[I[0][0]]
    

    # b. Extractive QA (Extract the precise answer)
    inputs = qa_tokenizer.encode_plus(
        question, 
        best_context, 
        add_special_tokens=True, 
        return_tensors="pt"
    )
    
    input_ids = inputs["input_ids"].tolist()[0]

    outputs = qa_model(**inputs)
    answer_start_scores, answer_end_scores = outputs.start_logits, outputs.end_logits

    answer_start = torch.argmax(answer_start_scores)
    answer_end = torch.argmax(answer_end_scores) + 1  # +1 to include the end token
    
    # Convert token IDs back to a string
    answer = qa_tokenizer.convert_tokens_to_string(
        qa_tokenizer.convert_ids_to_tokens(input_ids[answer_start:answer_end])
    )

    if answer.startswith('[CLS]') or answer.startswith(' '):
        return "Could not find a precise answer in the document."
    
    return answer


def chatbot_service(user_q):
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    
    faiss_index, qa_tokenizer, qa_model = _load_qa_components()

    answer = _answer_question(user_q, faiss_index, document_chunks, embedding_model, qa_tokenizer, qa_model)
    return answer