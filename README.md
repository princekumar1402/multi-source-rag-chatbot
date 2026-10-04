# 🌐 Multi-Source RAG Chatbot

A GenAI-powered application that ingests content from websites, YouTube videos, PDFs, DOCX, TXT, MD, CSV, XLSX, and documents, enables async ingestion, database workspace persistence, and allows users to ask questions using hybrid search (BM25 + Dense FAISS) and reranked Retrieval-Augmented Generation (RAG).

## 🚀 Live Demo

**Streamlit App:**

https://youtube-website-rag-chatbot-6xwiv7yqy6xxpmqjjwnnzm.streamlit.app/

## ✨ Features

* 🌐 Website Content Summarization & Ingestion
* 📺 YouTube Video Transcripts & Metadata Ingestion
* 📄 Multi-Format Document Ingestion (PDF, DOCX, TXT, MD, CSV, XLSX)
* ⚡ Async Background Ingestion Pipeline with Progress Tracking
* 🗄️ PostgreSQL Workspace & Conversation History Persistence
* 🎯 Document-Scoped Retrieval & Filtering
* 🔍 Hybrid Search (Dense FAISS Embeddings + BM25 Lexical Search + Reciprocal Rank Fusion / Cross-Encoder Reranking)
* 📝 Citation Validation & Verification
* 🤖 RAG-based Question Answering with Groq LLM Integration
* 🎨 Modern Glassmorphism React + TypeScript Frontend & FastAPI Backend

## 🏗️ Architecture

```text
Sources (YouTube, Web, PDF, DOCX, CSV, XLSX, TXT, MD)
   ↓
Async Job Ingestion Pipeline / Loaders
   ↓
Document Processing & Text Chunking
   ↓
HuggingFace Embeddings + BM25 Tokenizer
   ↓
FAISS Vector Store + PostgreSQL Metadata
   ↓
Hybrid Retriever (Dense + Sparse) & Reranker
   ↓
Groq LLM
   ↓
Citations & Verified Answers
```

## 🛠️ Tech Stack

* Python & FastAPI
* React & TypeScript (Vite)
* PostgreSQL & SQLAlchemy (Alembic)
* FAISS Vector Store
* HuggingFace Embeddings
* Groq (Llama 3.3 70B)
* Docker Compose

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/princekumar1402/multi-source-rag-chatbot.git
cd multi-source-rag-chatbot
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate virtual environment:

Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 🔑 Environment Variables

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
```

## ▶️ Run Locally

```bash
streamlit run app.py
```

## 📌 Notes

* Website extraction depends on the accessibility of the target website.
* Some YouTube videos may restrict transcript access.
* Cloud deployments may face limitations due to source-site blocking policies.

## 🎓 Learning Outcomes

This project demonstrates:

* Retrieval-Augmented Generation (RAG)
* Vector Databases (FAISS)
* Embeddings and Semantic Search
* Prompt Engineering
* LLM Integration with Groq
* Streamlit Deployment
* LangChain Framework

## 👨‍💻 Author

**Prince Kumar**

B.Tech CSE, IIIT Kottayam

