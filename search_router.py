import asyncio
from helper import search  
from web_crawl import web_search_and_fetch  

def simple_reranker(results, query, top_k=3):
    scored = [r for r in results if "score" in r]
    if scored:
        reranked = sorted(scored, key=lambda x: x.get("score", 0), reverse=True)
    else:
        def keyword_score(r):
            text = (r.get("title", "") + " " + r.get("text", "")).lower()
            return sum(1 for word in query.lower().split() if word in text)
        reranked = sorted(results, key=keyword_score, reverse=True)
    return reranked[:top_k]

def get_answer(query: str, k: int = 3, max_chars: int = 8000) -> dict:
    # Try internal search
    internal_results = search(query, k=k)
    reranked_internal = simple_reranker(internal_results, query, top_k=k)
    if reranked_internal and reranked_internal[0].get("score", 0) > 0.5:
        return {
            "source": "internal",
            "results": reranked_internal
        }
    # Fallback to web search
    web_results = web_search_and_fetch(query, k=k, max_chars=max_chars)
    reranked_web = simple_reranker(web_results, query, top_k=k)
    return {
        "source": "web",
        "results": reranked_web
    }

if __name__ == "__main__":
    query = input("Enter your question: ")
    answer = get_answer(query)
    print(answer)