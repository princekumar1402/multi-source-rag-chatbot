# 🌐 URL Summarizer & RAG Chatbot

A GenAI-powered application that summarizes content from websites and YouTube videos, generates key takeaways, and enables users to ask questions using Retrieval-Augmented Generation (RAG).

## 🚀 Live Demo

**Streamlit App:**

https://youtube-website-rag-chatbot-6xwiv7yqy6xxpmqjjwnnzm.streamlit.app/

## ✨ Features

* 🌐 Website Content Summarization
* 📺 YouTube Video Summarization
* 📝 Key Takeaways Generation
* 🤖 RAG-based Question Answering
* 🔍 Semantic Search with FAISS
* 🧠 HuggingFace Embeddings
* ⚡ Groq LLM Integration
* 🎨 Streamlit User Interface

## 🏗️ Architecture

```text
User URL
   ↓
Content Loader
(Website / YouTube)
   ↓
Document Processing
   ↓
Text Chunking
   ↓
HuggingFace Embeddings
   ↓
FAISS Vector Store
   ↓
Retriever
   ↓
Groq LLM
   ↓
Summary & Answers
```

## 🛠️ Tech Stack

* Python
* Streamlit
* LangChain
* Groq (Llama 3.3 70B)
* HuggingFace Embeddings
* FAISS
* UnstructuredURLLoader
* YoutubeLoader
* python-dotenv

## 📂 Project Workflow

### Summarization Flow

```text
URL
 ↓
Load Content
 ↓
Generate Summary
 ↓
Display Summary
```

### RAG Question Answering Flow

```text
Question
 ↓
Retriever
 ↓
Relevant Chunks
 ↓
Context Creation
 ↓
Groq LLM
 ↓
Answer
```

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/princekumar1402/youtube-website-rag-chatbot.git
cd youtube-website-rag-chatbot
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

