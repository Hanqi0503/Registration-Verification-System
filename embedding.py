import os
# Set BEFORE importing tokenizers / sentence-transformers to avoid parallelism spawning workers
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
import multiprocessing as mp
mp.set_start_method("forkserver", force=True)

import faiss
from flask import json
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

INDEX_FILE = 'document_index.faiss'
DOCUMENT_FILE = 'QA.md'
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

import re
from bs4 import BeautifulSoup

def clean_markdown(text: str) -> str:
    """
    Cleans Markdown text to prepare for embedding.
    Removes code blocks, links, HTML, and extra symbols.
    """

    # Remove fenced code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Remove inline code like `code`
    text = re.sub(r"`[^`]*`", "", text)

    # Remove markdown links [text](url)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove images ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Remove HTML tags (safety for copy-pasted docs)
    text = BeautifulSoup(text, "html.parser").get_text()

    # Remove markdown headers (#, ##, etc.)
    text = re.sub(r"#+\s*", "", text)

    # Remove list markers (*, -, +, 1.)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Replace multiple spaces/newlines with one
    text = re.sub(r"\s+", " ", text).strip()

     # Normalize whitespace and collapse excessive blank lines
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text

def load_and_chunk_document(file_path, max_chars: int = 800, overlap: int = 200):
    """
    Read document and produce semantic chunks.

    - max_chars: target max characters per chunk (tune for your embedding model).
    - overlap: number of chars to overlap between adjacent chunks to preserve context.
    """
    import re

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: Document file not found at {file_path}")
        return []

    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")])
    sections = header_splitter.split_text(text)

    cleaned_sections = [clean_markdown(s.page_content) for s in sections]

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = [c for sec in cleaned_sections for c in splitter.split_text(sec)]
    chunks = list(dict.fromkeys(chunks))  # Remove duplicates while preserving order
    return chunks

def create_index():
    document_chunks = load_and_chunk_document(DOCUMENT_FILE)
    if not document_chunks:
        return None, None

    print(f"Loaded {len(document_chunks)} chunks. Generating embeddings...")
    
    model = SentenceTransformer(EMBEDDING_MODEL)

    embeddings = model.encode(document_chunks, device='cuda' if torch.cuda.is_available() else 'cpu')
    # Normalize for cosine similarity
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner Product is used for cosine similarity
    index.add(np.array(embeddings))
    
    faiss.write_index(index, INDEX_FILE)
    
    with open('document_chunks.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(document_chunks))
    
    import json
    with open('document_chunks.json', 'w', encoding='utf-8') as f:
        json.dump(document_chunks, f, ensure_ascii=False, indent=2)

    return model, document_chunks

if __name__ == "__main__":
    embedding_model, document_chunks = create_index()
    print('Embedding dimension:', embedding_model.get_sentence_embedding_dimension())