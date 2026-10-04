# Phase 6 — Document-Scoped Retrieval Architecture & Production Implementation

## Executive Summary

In multi-source RAG platforms, unconstrained retrieval over an entire knowledge base can cause cross-document semantic leakage. When a user intends to query a specific document or subset of documents (e.g. an uploaded docx prompt specification vs. unrelated YouTube video transcripts), unconstrained retrieval retrieves top-k chunks by global similarity, which may surface irrelevant or distracting documents into the prompt context and final citations.

Phase 6 implements a **pre-retrieval Document Scoping Layer** that restricts both **Dense (FAISS)** and **Keyword (BM25)** retrieval candidates to the selected document ID(s) **before** Reciprocal Rank Fusion (RRF), Cross-Encoder reranking, context assembly, and LLM generation take place.

---

## 1. Architectural Design & Flow

### Flow Diagram

```
                 User Question + Retrieval Scope (document_ids)
                                       │
                                       ▼
                   Workspace Validation & Document Scoping
          (Validate doc IDs belong to workspace; reject/isolate invalid)
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        FAISS Dense Retrieval                 BM25 Keyword Retrieval
      (Scoped candidate filter)             (Scoped candidate filter)
                    │                                     │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                        Reciprocal Rank Fusion (RRF)
                                       │
                                       ▼
                         Cross-Encoder Reranking
                      (Only scoped chunks evaluated)
                                       │
                                       ▼
                          Strict Context Selection
                                       │
                                       ▼
                         Grounded LLM Generation
                                       │
                                       ▼
                 Citations & Insufficient-Context Refusal
          (Citations strictly limited to scoped document; zero fallback)
```

---

## 2. Backend Implementation Details

### A. Vector Store (FAISS) Filtering Layer
- **File**: `backend/app/services/vector_store/faiss_store.py`
- **Challenge**: FAISS indices natively search vectors without aware metadata partitioning unless oversampling is performed. If `top_k=5` was requested on a large index, querying only the top 5 global nearest neighbors could easily miss the target document chunks.
- **Solution**:
  - When `document_ids` is specified in `filters`, `fetch_k` is dynamically expanded up to `self.index.ntotal` (or `max(top_k * 10, 100)`), ensuring all matching chunks from the selected document(s) are evaluated.
  - The metadata filter strictly checks:
    ```python
    v = chunk.metadata.document_id
    if v is not None and v not in target_doc_ids:
        matches = False
    ```
  - Empty `document_ids: []` properly yields zero results, preventing accidental fallback to all documents.

### B. BM25 Keyword Filtering Layer
- **File**: `backend/app/services/rag/bm25.py`
- **Implementation**:
  - Pre-filters candidate indices:
    ```python
    target_docs = filters["document_ids"]
    v = chunk.metadata.document_id
    if v is not None and v not in target_docs:
        continue
    ```
  - BM25 candidate scoring is completely restricted to eligible documents, guaranteeing that unselected documents cannot score in the keyword branch.

### C. Chat API & Workspace Isolation
- **File**: `backend/app/api/v1/chat.py`
- **Validation**:
  - When `document_ids` is passed in the chat request payload (`ChatMessageRequest`), the API queries `DocumentRepository.list_by_workspace(db, workspace_id)`.
  - Any provided document ID that does not belong to the current workspace is safely stripped out.
  - If the user provides only cross-workspace or nonexistent IDs, the scope is replaced with a non-matching token (`["__scoped_non_existent__"]`), completely preventing cross-workspace data leakage.
- **Backward Compatibility**:
  - When `document_ids` is `None` or omitted, the system defaults to `ALL DOCUMENTS` within the current workspace.

---

## 3. Frontend Implementation Details

### A. Scope Selector UI
- **Files**:
  - `frontend/src/components/ChatView.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/services/api.ts`
- **Features**:
  - A clean, modern retrieval-scope bar positioned right above the chat input box.
  - Dropdown selector displaying:
    - `All Documents` (Default)
    - Each ingested document with title and source type badge (PDF, DOCX, YouTube).
  - When a single document is selected, an active scoping banner appears with a direct "Clear" button to return to All Documents with one click.
  - Retains all existing responsive layouts and design aesthetics.

---

## 4. Grounding & Zero-Fallback Refusal

When a user selects a specific document (e.g., `AI Prompt engineering task 5`) and asks an out-of-scope question (e.g., *"What happened in Iraq?"*):
1. FAISS and BM25 retrieve 0 chunks related to Iraq from the selected document.
2. Context selector assesses relevance: context score is below the threshold and `has_sufficient_context = False`.
3. The LLM refuses using the standard refusal prompt:
   > *"The available knowledge base sources do not contain enough information to answer this question."*
4. Zero citations are returned. Under no circumstance does the engine fall back to unselected documents in the knowledge base.

---

## 5. Verification & Test Suite

### Automated Tests Added: `backend/tests/test_document_scoped_retrieval.py`
1. `test_faiss_document_filtering`: Verifies FAISS metadata filtering on single and multiple document IDs.
2. `test_bm25_document_filtering`: Verifies BM25 filtering excludes matching query terms from unselected documents.
3. `test_hybrid_document_filtering`: Verifies end-to-end hybrid retrieval with RRF and reranker under single document scope.
4. `test_multi_document_search`: Verifies multi-document scope retrieves chunks from only the selected subset.
5. `test_all_documents_search`: Verifies default backward-compatible all-documents behavior.
6. `test_workspace_isolation`: Verifies queries targeting a different workspace yield zero results.
7. `test_citation_isolation_guarantee`: Verifies zero citation leakage from unselected documents.

### Manual Live Tests Conducted:
- **Test A (Scope: AI Prompt engineering task 5)**:
  - Query: *"Explain the main topic of this document."*
  - Result: Detailed explanation of AI Prompt engineering task 5. Citations strictly from `AI Prompt engineering task 5`. 0 YouTube citations.
- **Test B (Scope: Proof Of Trump's Receding Power?)**:
  - Query: *"What is the video about?"*
  - Result: Summary of video topic with YouTube timestamp citations.
- **Test C (Scope: AI Prompt engineering task 5, Query: "What happened in Iraq?")**:
  - Result: Refusal: *"The available knowledge base sources do not contain enough information to answer this question."* 0 citations.
- **Test D (Scope: All Documents)**:
  - Query: *"Which uploaded sources discuss prompt engineering?"*
  - Result: Accurate multi-source retrieval across all eligible documents.

---

## 6. Limitations & Future Considerations
- For extremely large vector indexes (>1M vectors per workspace), pre-filtering with index-native partition tags (such as Milvus partitions or Qdrant collections) is recommended over post-search filtering on Flat indices.
- Multi-document multi-select checkboxes can be enhanced with folder/tag-based filtering in Phase 7.
