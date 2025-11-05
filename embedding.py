import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForQuestionAnswering
import os

INDEX_FILE = 'document_index.faiss'
DOCUMENT_FILE = 'README.md'
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

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

    # Normalize whitespace and collapse excessive blank lines
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    # Split into paragraphs (logical blocks)
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    for para in paras:
        if len(para) <= max_chars:
            chunks.append(para)
            continue

        # Sentence-split (lightweight regex). Prefer a sentence tokenizer if available.
        sents = re.split(r"(?<=[\.\?\!])\s+", para)
        cur = ""
        for s in sents:
            s = s.strip()
            if not s:
                continue
            if len(cur) + 1 + len(s) <= max_chars:
                cur = (cur + " " + s).strip() if cur else s
            else:
                if cur:
                    chunks.append(cur)
                # If single sentence is still too large, force-split by characters with overlap
                if len(s) > max_chars:
                    start = 0
                    while start < len(s):
                        part = s[start : start + max_chars]
                        chunks.append(part.strip())
                        start += max_chars - overlap if max_chars > overlap else max_chars
                    cur = ""
                else:
                    cur = s
        if cur:
            chunks.append(cur)

    # Create sliding windows over the concatenated chunks to ensure the requested overlap
    if overlap > 0 and chunks:
        full = "\n\n".join(chunks)
        step = max(1, max_chars - overlap)
        windows = []
        for i in range(0, len(full), step):
            w = full[i : i + max_chars].strip()
            if w:
                windows.append(w)
        # Deduplicate very similar adjacent windows
        dedup = []
        prev = None
        for w in windows:
            if w != prev:
                dedup.append(w)
            prev = w
        chunks = [c for c in dedup if len(c) > 20]

    # Final cleanup
    chunks = [c.strip() for c in chunks if c and len(c) > 20]
    return chunks

def create_index():
    document_chunks = load_and_chunk_document(DOCUMENT_FILE)
    if not document_chunks:
        return None, None

    print(f"Loaded {len(document_chunks)} chunks. Generating embeddings...")
    
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    embeddings = model.encode(document_chunks)
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)  # L2 is Euclidean distance
    index.add(np.array(embeddings))
    
    faiss.write_index(index, INDEX_FILE)
    
    with open('document_chunks.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(document_chunks))
        
    return model, document_chunks

# Execute indexing once
embedding_model, document_chunks = create_index()