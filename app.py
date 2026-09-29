import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

import streamlit as st
from langchain_community.document_loaders import (
    WebBaseLoader,
    YoutubeLoader
)

# Define function FIRST
def load_content(url):

    try:
        if "youtube.com" in url or "youtu.be" in url:

            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False,
                language=["en"]
            )

        else:

           loader = WebBaseLoader(url)

        docs = loader.load()

        return docs

    except Exception as e:
        st.error(f"Failed to load content: {str(e)}")
        return []


# Streamlit code AFTER function
st.set_page_config(
    page_title="URL Summarizer",
    page_icon="🌐"
)

st.title("🌐 URL Summarizer & RAG Chatbot")
url = st.text_input(
    "Enter Website or YouTube URL"
)
# split documents into chunks
def split_documents(docs):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(docs)

    return chunks
# create vectorstore from chunks
def create_vectorstore(chunks):

    if not chunks:
        raise ValueError("No chunks found.")

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return FAISS.from_documents(
        chunks,
        embeddings
    )
# create retriever from vectorstore
def create_retriever(vectorstore):

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 5}
    )

    return retriever

# create LLM instance
load_dotenv()
def get_llm():

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0
    )

    return llm
# generate summary from docs
from langchain_core.prompts import ChatPromptTemplate
def generate_summary(llm, docs):

    content = "\n\n".join(
        [doc.page_content for doc in docs]
    )
    content = content[:5000]

    prompt = ChatPromptTemplate.from_template(
        """
        Summarize the following content.

        Content:
        {content}

        Provide:
        1. Short Summary
        2. Key Takeaways
        3. Important Topics Covered
        """
    )

    chain = prompt | llm

    response = chain.invoke(
        {"content": content}
    )

    return response.content

# ask question from retriever
from langchain_core.output_parsers import StrOutputParser
def ask_question(llm, retriever, question):

    docs = retriever.invoke(question)

    # DEBUG
    st.write("Retrieved Documents:", len(docs))

    for i, doc in enumerate(docs):
        st.write(f"Chunk {i+1}")
        st.write(doc.page_content[:500])

    context = "\n\n".join(
        [doc.page_content for doc in docs]
    )

    prompt = ChatPromptTemplate.from_template(
        """
        Use the context below to answer the question.

        Context:
        {context}

        Question:
        {question}
        """
    )

    chain = prompt | llm | StrOutputParser()

    response = chain.invoke({
        "context": context,
        "question": question
    })

    return response

llm = get_llm()
docs = []
# button to process URL and generate summary and retriever
if st.button("Process"):
    with st.spinner("Processing..."):
        if not url:
            st.error("Please enter a URL")
            st.stop()
         
        docs = load_content(url)
        st.write("Docs Loaded:", len(docs))

        if not docs:
            st.error("Could not extract content from the URL.")
            st.stop()

        summary = generate_summary(
            llm,
            docs
        )

        chunks = split_documents(docs)

        st.write("Documents:", len(docs))
        st.write("Chunks:", len(chunks))

        if not chunks:
            st.error("No chunks were created from the content.")
            st.stop()

        vectorstore = create_vectorstore(
            chunks
        )

        retriever = create_retriever(
            vectorstore
        )

        st.session_state.retriever = retriever


        st.session_state.summary = summary

if "summary" in st.session_state:

    st.subheader("Summary")

    st.write(
        st.session_state.summary
    )

if "retriever" in st.session_state:

    st.subheader("Chat With Content")

    question = st.text_input(
        "Ask a Question"
    )

    if question:

        answer = ask_question(
            llm,
            st.session_state.retriever,
            question
        )

        st.write(answer)