import os
import faiss
import numpy as np
import pandas as pd
import requests
import time
from dotenv import load_dotenv


load_dotenv() 

CSV_PATH   = "./news.csv"
TEXT_COL   = "article_content"               
OUT_DIR    = "./index"
OUT_FAISS  = os.path.join(OUT_DIR, "news.faiss")
OUT_META   = os.path.join(OUT_DIR, "news_metadata.parquet")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"


def _normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
    return vectors / norms

def clean_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    
    text = text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
    
    # Truncate if too long (Gemini has token limits)
    if len(text) > 50000:  # Conservative limit
        text = text[:50000]
    
    if len(text.strip()) < 5:
        return ""
    
    return text.strip()

def embed(text: str, task_type: str = "RETRIEVAL_DOCUMENT", max_retries: int = 3) -> np.ndarray:
    
    text = clean_text(text)
    if not text:
        raise ValueError("Text is empty after cleaning")
    
    headers = {
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "models/text-embedding-004",
        "content": {
            "parts": [{"text": text}]
        },
        "taskType": task_type,
    }
    
    url = f"{EMBED_URL}?key={GEMINI_API_KEY}"
    
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if r.status_code == 429:  # Rate limit
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            if r.status_code != 200:
                print(f"Error response: {r.status_code}")
                print(f"Response body: {r.text}")
                r.raise_for_status()
            
            response_data = r.json()
            
            if "embedding" not in response_data:
                print(f"Unexpected response format: {response_data}")
                raise ValueError("No embedding in response")
            
            vec = response_data["embedding"]["values"]
            return np.asarray(vec, dtype="float32")
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Request failed (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)
    
    raise Exception("Max retries exceeded")

def embed_query(text: str) -> np.ndarray:
    return embed(text, task_type="RETRIEVAL_QUERY")

def build_index():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(CSV_PATH)
    df = df[df[TEXT_COL].astype(str).str.strip().ne("")].copy()

    if "news_id" not in df.columns:
        df["news_id"] = np.arange(len(df), dtype=np.int64)

    df = df.dropna(subset=["news_id"]).copy()
    df["vec_id"] = pd.to_numeric(df["news_id"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["vec_id"]).copy()
    df = df[~df["vec_id"].duplicated(keep="first")].copy()
    df["vec_id"] = df["vec_id"].astype(np.int64)

    df.reset_index(drop=True, inplace=True)
    print(f"Final dataset: {len(df)} rows")

    vectors = []
    failed_indices = []
    
    for i, txt in enumerate(df[TEXT_COL].astype(str)):
        try:
            print(f"Processing {i+1}/{len(df)}: {txt[:100]}...")
            vec = embed(txt)
            vectors.append(vec)
            
            # Add small delay to avoid rate limits
            if i > 0 and i % 10 == 0:
                time.sleep(1)
                
        except Exception as e:
            print(f"Failed to embed row {i}: {e}")
            failed_indices.append(i)
            continue

    if not vectors:
        raise ValueError("No embeddings were created successfully")
    
    if failed_indices:
        print(f"Removing {len(failed_indices)} failed rows")
        df = df.drop(failed_indices).reset_index(drop=True)

    emb = np.vstack(vectors).astype("float32")
    print(f"Created embeddings: {emb.shape}")

    # Normalize for cosine similarity
    emb = _normalize(emb)
    d = emb.shape[1]

    # Build FAISS index
    index = faiss.IndexFlatIP(d)
    index = faiss.IndexIDMap2(index)
    index.add_with_ids(emb, df["vec_id"].to_numpy(dtype=np.int64))

    print(f"FAISS index built: {index.ntotal} vectors, dim={d}")

    # Save
    faiss.write_index(index, OUT_FAISS)
    df.to_parquet(OUT_META, index=False)
    print(f"Saved index → {OUT_FAISS}")
    print(f"Saved metadata → {OUT_META}")

def load_resources(index_path=OUT_FAISS, meta_path=OUT_META):
    idx = faiss.read_index(index_path)
    meta = pd.read_parquet(meta_path)
    meta.set_index("vec_id", inplace=True)
    return idx, meta

def search(query: str, k: int = 5):
    idx, meta = load_resources()
    qv = embed_query(query).reshape(1, -1)
    qv = _normalize(qv)
    
    D, I = idx.search(qv, k)
    results = []
    for score, vid in zip(D[0], I[0]):
        if vid == -1:
            continue
        row = meta.loc[int(vid)]
        results.append({"score": float(score), **row.to_dict()})
    return results

    
# Build index
# build_index()

# Test search
# try:
#     results = search("What are some initiatives launched by MCMC?", k=5)
#     for r in results:
#         print(f"Score: {r['score']:.4f} - {str(r.get(TEXT_COL, ''))[:100]} - {str(r.get('vec_id', -1))}...")
# except Exception as e:
#     print(f"Search test failed: {e}")