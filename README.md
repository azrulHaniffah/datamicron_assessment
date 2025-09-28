
# datamicron_assessment


## Overview

This repository contains a modern AI-powered web application for intelligent news search and retrieval. Users interact with a conversational chatbot interface that leverages both an internal news knowledge base and real-time web search to provide comprehensive, context-aware answers.

**How it works:**
- Users ask questions via a Gradio-based chatbot UI.
- The system first searches an internal news database using semantic similarity (vector embeddings + FAISS).
- If internal results are insufficient, it performs a live web search and crawls relevant news articles.
- All results are ranked and summarized, then passed to Google's Gemini LLM to generate a helpful, well-sourced answer.
- The chatbot responds with a conversational answer and cites sources.

**Key Features:**
- Conversational AI chatbot interface (Gradio)
- Hybrid search: internal news + real-time web crawling
- Semantic search with Gemini embeddings and FAISS
- Automated news crawling and extraction
- Source attribution and context-aware responses

**Tech Stack:** Python, Gradio, Gemini LLM, FAISS, Pandas, Pydantic, Async Web Crawler, Parquet




## Key Components

- `app.py` — Main Gradio web application and chatbot logic. Handles user interaction, prompt construction, and LLM response generation.
- `search_router.py` — Orchestrates hybrid search: runs internal semantic search, falls back to web search/crawling, and reranks results.
- `web_crawl.py` — Performs web search (via SerpAPI), crawls news articles, and extracts relevant content using LLM-based extraction.
- `helper.py` — Core utilities for embedding, FAISS index building, and semantic search over the internal news dataset.
- `build_index.py` — Script to build the FAISS index and metadata parquet file from `news.csv` using `helper.py`.
- `news.csv` — Source data file containing news articles for the internal knowledge base.
- `requirements.txt` — List of required Python packages.
- `index/` — Directory containing search index files:
   - `news_metadata.parquet` — Metadata for news articles
   - `news.faiss` — FAISS index for efficient similarity search



## Setup Instructions

1. **Clone the repository**
   ```powershell
   git clone <repo-url>
   cd "datamicron_assessment"
   ```

2. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Create a `.env` file in the project root with the following content:
     ```env
     # Required for Gemini LLM and embeddings
     GEMINI_API_KEY=your_gemini_api_key_here
     
     # Required for web search (SerpAPI)
     SERPAPI_API_KEY=your_serpapi_api_key_here

     PYTHONIOENCODING=utf-8
     ```
   - Replace the values with your actual API keys.

4. **Build the search index**
   ```powershell
   python build_index.py
   ```

5. **Run the web application**
   ```powershell
   python app.py
   ```

6. **Access the app**
   Open your browser and go to the URL shown in the terminal (e.g., http://127.0.0.1:7860/)

### Option 2: Docker

1. **Build the Docker image**
    ```powershell
    docker build -t datamicron_assessment .
    ```

2. **Run the container**
    ```powershell
    docker run --env-file .env -p 7860:7860 datamicron_assessment
    ```

3. **Access the app**
    Open your browser and go to http://localhost:7860/



## Main Functionality

- **Conversational Search:** Users interact with a chatbot that answers questions using both internal and web sources.
- **Semantic Indexing:** News articles are embedded and indexed for fast similarity search.
- **Hybrid Retrieval:** The system combines internal search and live web crawling for comprehensive coverage.
- **LLM-Powered Summarization:** Gemini LLM synthesizes search results into clear, well-sourced answers.
- **Source Attribution:** All answers include links and internal IDs for traceability.
- **Automated Index Building:** Use `build_index.py` to process and index new data from `news.csv`.

## Requirements

- Python 3.11 or higher
- All dependencies listed in `requirements.txt`

## Notes

- Ensure `news.csv` is present in the root directory for data processing.
- The `index/` folder is used for storing generated search indices and metadata.

## License

This project is for assessment purposes only.
