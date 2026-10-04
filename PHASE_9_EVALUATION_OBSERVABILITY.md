# Phase 9: RAG Evaluation & Observability Architecture

This document specifies the architecture, data schemas, observability telemetry, and evaluation benchmarks implemented in **Phase 9** for the production-grade Multi-Source RAG Chatbot.

---

## 1. Overview & Objectives

Phase 9 establishes automated, deterministic measurement and runtime observability for every stage of the RAG pipeline.

### Core Questions Answered:
1. **Retrieval Quality**: What percentage of ground-truth relevant evidence is captured in Top-1, Top-3, Top-5, and Top-10 candidates across Dense, Keyword, and Hybrid configurations?
2. **Ranking Effectiveness**: Does Reciprocal Rank Fusion (RRF) and Cross-Encoder Reranking promote relevant documents to the top rank (MRR)?
3. **Groundedness & Faithfulness**: Are generated answers strictly supported by retrieved context?
4. **Citation Provenance**: Are cited chunk IDs guaranteed to exist within the retrieved context with valid page, sheet, or timestamp metadata?
5. **Document-Scoped Isolation**: Does retrieval stay 100% contained within selected document scopes without cross-document leakage?
6. **Latency Profiling**: What is the P50, P90, P95, and P99 latency, and what is the exact stage breakdown (query rewriting, dense retrieval, BM25 retrieval, RRF fusion, reranking, context selection, LLM generation, citation validation)?
7. **Structured Observability**: Can engineers trace any request using a unique `trace_id` without leaking sensitive secrets or raw document content?

---

## 2. Evaluation Dataset Architecture

Evaluation uses a controlled, reproducible multi-source dataset located at:
[`backend/evaluation/datasets/rag_evaluation.json`](file:///c:/Users/hp/Desktop/youtube-website-rag-chatbot-main/backend/evaluation/datasets/rag_evaluation.json)

Supported sources in the evaluation corpus:
- **PDF**: Operating Systems Manual (Deadlocks, Coffman conditions, CPU scheduling, Virtual memory paging)
- **DOCX**: DBMS Architecture (ACID properties, B+ Tree indexing, MVCC concurrency)
- **Markdown**: Data Engineering Guide (Polars Apache Arrow SIMD, Kafka partitioning, DuckDB vectorized execution)
- **TXT**: Networking Protocols (TCP 3-way handshake, DNS recursive resolution, TLS 1.3 security)
- **CSV**: Employee Directory (Principal Architect Rahul Sharma, Growth Director Sarah Jenkins, Senior Penetration Tester Alice Chen)
- **XLSX**: University Roster (Computer Science & Mathematics sheets, student Priya Patel, David Kim, Emma Watson)
- **Web**: Web Protocols (HTTP/3 QUIC transport, WebSocket full-duplex communication)
- **YouTube**: Technical Engineering Lectures (Backpropagation chain rule, Transformer self-attention, Raft consensus algorithm)
- **Distractors**: Unrelated documents (Cooking recipes, Gardening tips, Astronomy)

### Evaluation Item Schema:
```json
{
  "id": "eval_001",
  "question": "What are the four Coffman conditions necessary for a deadlock in operating systems?",
  "document_ids": ["doc-pdf-eval-01"],
  "relevant_chunk_ids": ["chunk-pdf-p24-1"],
  "source_type": "pdf",
  "category": "factual",
  "expected_answer": "Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.",
  "expected_refusal": false
}
```

### Benchmark Categories Evaluated:
- `factual`: Core factual recall across all 8 file formats.
- `exact_entity`: Specific entities (e.g. employee IDs `EMP-1092`, student roll numbers `1042`).
- `structured_data`: CSV row compensation/location and XLSX sheet/row CGPA/advisors.
- `source_specific`: Source metadata (e.g. YouTube timestamp strings `12:00 - 13:05`, PDF page `24`).
- `multi_hop`: Cross-concept comparative queries across multiple documents.
- `conversational`: Multi-turn follow-ups testing query rewriting with chat history.
- `insufficient_context`: Questions where the answer is absent from the knowledge base (e.g. "What is quantum error correction?").
- `document_scoped_negative`: Questions where the answer exists in another document, but the query is scoped strictly to a different document ID.

---

## 3. Retrieval Metrics & Mathematical Formulation

### 1. Recall@K
$$\text{Recall@K} = \frac{|\text{Retrieved@K} \cap \text{GroundTruth}|}{|\text{GroundTruth}|}$$
Evaluated at $K \in \{1, 3, 5, 10\}$.

### 2. Reciprocal Rank (RR) & Mean Reciprocal Rank (MRR)
$$\text{RR} = \frac{1}{\text{rank}_i}, \quad \text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \text{RR}_i$$
Where $\text{rank}_i$ is the 1-based rank of the first relevant chunk found for query $i$.

### Comparative Strategies Evaluated:
1. **Dense Retrieval (FAISS)**: Dense vector similarity using Inner Product cosine search.
2. **Keyword Retrieval (BM25)**: Lexical term frequency and document length normalization (Okapi BM25).
3. **Hybrid RRF**: Reciprocal Rank Fusion ($k=60$) combining Dense and BM25 candidate ranks.
4. **Hybrid RRF + Cross-Encoder Reranker**: Full production pipeline with deep sentence-pair cross-attention reranking.

---

## 4. RAG Execution Trace Architecture

Every query processed by `RAGEngine` automatically generates or receives a UUID4 `trace_id` and records a structured trace object:

```json
{
  "trace_id": "801a070e-d611-4007-8855-bc212bbd4ed3",
  "query_id": "801a070e-d611-4007-8855-bc212bbd4ed3",
  "query_rewriting_latency_ms": 0.05,
  "metadata_filtering_latency_ms": 0.02,
  "dense_retrieval_latency_ms": 0.35,
  "bm25_retrieval_latency_ms": 0.06,
  "rrf_fusion_latency_ms": 0.01,
  "reranking_latency_ms": 0.08,
  "context_selection_latency_ms": 0.12,
  "llm_latency_ms": 0.05,
  "citation_validation_latency_ms": 0.02,
  "total_latency_ms": 0.74,
  "retrieval_metrics": {
    "dense_candidate_count": 20,
    "bm25_candidate_count": 20,
    "rrf_candidate_count": 20,
    "reranked_candidate_count": 10,
    "final_context_count": 5,
    "selected_document_ids": ["doc-pdf-eval-01"],
    "score_statistics": {
      "min_score": 0.452,
      "max_score": 0.985,
      "avg_score": 0.718
    }
  }
}
```

### Safety & Privacy Guarantees:
- **No Raw Document Content**: Traces log chunk identifiers, counts, and scores, never full uploaded documents.
- **No Credentials**: Database connection strings, passwords, and API keys are strictly excluded from traces and logs.

---

## 5. Token & Model Metrics

When Groq LPU inference is active, `GroqLLM` extracts token usage directly from LangChain `response_metadata`:
- `input_tokens`: Prompt token count.
- `output_tokens`: Completion token count.
- `total_tokens`: Aggregate token count.
- `model`: Exact model name (e.g. `llama-3.3-70b-versatile`).
- `generation_latency_ms`: LLM response time.

If a provider does not expose token telemetry, values are recorded as `null` rather than fabricated.

---

## 6. Structured JSON Logging

`RAGEngine` emits structured single-line JSON log events for monitoring systems (e.g. Datadog, CloudWatch, ELK):

### Successful Completion:
```json
{
  "event": "rag_request_completed",
  "trace_id": "801a070e-d611-4007-8855-bc212bbd4ed3",
  "total_latency_ms": 0.69,
  "retrieved_chunks": 3,
  "context_chunks": 3,
  "citations": 3,
  "model": "llama-3.3-70b-versatile",
  "has_sufficient_context": true
}
```

### Failure Event:
```json
{
  "event": "rag_request_failed",
  "trace_id": "801a070e-d611-4007-8855-bc212bbd4ed3",
  "stage": "retrieval",
  "error_type": "ConnectionError"
}
```

---

## 7. Document Scope Isolation & Refusal Testing

Phase 9 explicitly validates Phase 6 Document-Scoped Retrieval:
1. **Containment Verification**: Every returned citation must belong to the allowed `document_ids`.
2. **Negative Scope Isolation**: If a user asks a question whose answer is in `doc-docx-eval-02`, but restricts scope to `doc-pdf-eval-01`, retrieval must NOT leak out of scope.
3. **Grounded Refusal**: The engine returns `has_sufficient_context = False` with the standardized grounded refusal:
   *"The available knowledge base sources do not contain enough information to answer this question."*
   and completely suppresses citations to prevent false provenance.

---

## 8. Reproducing the Evaluation Benchmark

Run the automated evaluation runner:

```bash
python -m backend.evaluation.runner
```

Output:
- Formatted ASCII performance summary in terminal.
- Baseline markdown report at [`PHASE_9_EVALUATION_REPORT.md`](file:///c:/Users/hp/Desktop/youtube-website-rag-chatbot-main/PHASE_9_EVALUATION_REPORT.md).
- Machine-readable JSON summary at [`backend/evaluation/evaluation_results.json`](file:///c:/Users/hp/Desktop/youtube-website-rag-chatbot-main/backend/evaluation/evaluation_results.json).

---

## 9. Baseline Benchmark Results (Phase 9)

- **Total Questions Evaluated**: 32
- **Document Scope Isolation**: **100.0%** (0 out-of-scope chunks leaked)
- **Refusal Accuracy on OOD / Negative Scope**: **100.0%**
- **Citation Provenance & Completeness**: **100.0%**
- **Recall@3 / Recall@5 / Recall@10**: **100.0%**
- **MRR (Hybrid RRF + Reranker)**: **0.9815**
- **P50 Latency**: **1.0 ms**
- **P95 Latency**: **1.0 ms**
- **P99 Latency**: **1.0 ms**
