# Author: Worker Owner
import chromadb
from sentence_transformers import SentenceTransformer
import os
from datetime import datetime

# Initialize models once
_model = SentenceTransformer('all-MiniLM-L6-v2')
_client = chromadb.PersistentClient(path='./chroma_db')
_collection = _client.get_or_create_collection('day09_docs')

def run(state: dict) -> dict:
    """
    Retrieval Worker: Tìm kiếm chunks từ ChromaDB dựa trên query.
    Input: state với trường 'task'
    Output: retrieved_chunks, retrieved_sources, worker_io_log
    """
    query = state.get("task", "")
    
    retrieved_chunks = []
    retrieved_sources = set()
    method_used = "chromadb_embedding"

    try:
        # Generate embedding
        query_embedding = _model.encode(query).tolist()
        
        # Search ChromaDB
        results = _collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )
        
        if results['documents'] and results['documents'][0]:
            for i in range(len(results['documents'][0])):
                doc = results['documents'][0][i]
                meta = results['metadatas'][0][i]
                dist = results['distances'][0][i] if results.get('distances') else None
                score = round(1 - dist, 4) if dist is not None else 0.9
                retrieved_chunks.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "score": score
                })
                retrieved_sources.add(meta.get("source", "unknown"))
    except Exception as e:
        print(f"ChromaDB/Model not ready: {e}. Falling back to keyword search.")
        method_used = "keyword_fallback"
        docs_dir = './data/docs'
        if os.path.exists(docs_dir):
            for fname in os.listdir(docs_dir):
                with open(os.path.join(docs_dir, fname), encoding='utf-8') as f:
                    content = f.read()
                    if any(word in content.lower() for word in query.lower().split()):
                        retrieved_chunks.append({
                            "text": content[:1000],
                            "source": fname,
                            "score": 0.5
                        })
                        retrieved_sources.add(fname)
                if len(retrieved_chunks) >= 5:
                    break

    worker_io_log = {
        "worker": "retrieval_worker",
        "method": method_used,
        "input_query": query,
        "chunks_found": len(retrieved_chunks),
        "sources": list(retrieved_sources),
        "timestamp": datetime.now().isoformat()
    }

    return {
        "retrieved_chunks": retrieved_chunks[:5],
        "retrieved_sources": list(retrieved_sources),
        "worker_io_log": worker_io_log
    }


if __name__ == "__main__":
    # Test independent
    test_state = {"task": "SLA ticket P1 là bao lâu?"}
    res = run(test_state)
    print(f"Retrieved {len(res['retrieved_chunks'])} chunks.")
    for chunk in res['retrieved_chunks']:
        print(f"- [{chunk['source']}] {chunk['text'][:100]}...")
    print(f"Worker IO log: {res['worker_io_log']}")
