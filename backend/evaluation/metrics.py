import math
from typing import List, Set, Dict, Any, Optional

def calculate_recall_at_k(retrieved_ids: List[str], ground_truth_ids: List[str], k: int) -> float:
    """
    Computes Recall@K: fraction of ground-truth relevant chunks retrieved in top-k.
    If ground_truth_ids is empty:
      - Returns 1.0 if no chunks were retrieved (proper negative/refusal)
      - Returns 0.0 if chunks were inappropriately retrieved
    """
    if not ground_truth_ids:
        return 1.0 if len(retrieved_ids[:k]) == 0 else 0.0

    top_k_retrieved = set(retrieved_ids[:k])
    target_set = set(ground_truth_ids)
    hits = len(top_k_retrieved.intersection(target_set))
    return round(hits / len(target_set), 4)

def calculate_reciprocal_rank(retrieved_ids: List[str], ground_truth_ids: List[str]) -> float:
    """
    Computes Reciprocal Rank (RR): 1 / rank of the first relevant chunk found.
    Returns 0.0 if no relevant chunk is retrieved or ground_truth_ids is empty.
    """
    if not ground_truth_ids:
        return 0.0

    target_set = set(ground_truth_ids)
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in target_set:
            return round(1.0 / rank, 4)
    return 0.0

def calculate_mean_reciprocal_rank(rr_list: List[float]) -> float:
    """
    Computes Mean Reciprocal Rank (MRR) across a list of query reciprocal ranks.
    """
    if not rr_list:
        return 0.0
    return round(sum(rr_list) / len(rr_list), 4)

def evaluate_document_scope_isolation(
    retrieved_chunk_ids: List[str],
    retrieved_doc_ids: List[str],
    allowed_doc_ids: Optional[List[str]]
) -> Dict[str, Any]:
    """
    Verifies that all retrieved chunks belong strictly to the allowed document IDs.
    Zero leakage out of scope.
    """
    if not allowed_doc_ids:
        return {
            "scoped": False,
            "leakage_count": 0,
            "is_isolated": True,
            "allowed_document_ids": None
        }

    allowed_set = set(allowed_doc_ids)
    leakage = [doc_id for doc_id in retrieved_doc_ids if doc_id not in allowed_set]
    return {
        "scoped": True,
        "leakage_count": len(leakage),
        "is_isolated": len(leakage) == 0,
        "allowed_document_ids": allowed_doc_ids,
        "leaked_document_ids": list(set(leakage))
    }

def evaluate_citation_quality(
    citations: List[Any],
    retrieved_chunk_ids: List[str],
    allowed_doc_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Evaluates citation precision, provenance, and metadata completeness:
    - Chunk existence in retrieved context
    - Document scope containment
    - Source metadata presence (page, sheet, timestamp, etc.)
    """
    if not citations:
        return {
            "citation_count": 0,
            "valid_citations": 0,
            "accuracy": 1.0,
            "issues": []
        }

    retrieved_set = set(retrieved_chunk_ids)
    allowed_set = set(allowed_doc_ids) if allowed_doc_ids else None

    valid_count = 0
    issues = []

    def _field(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    for cit in citations:
        chunk_id = _field(cit, "chunk_id")
        doc_id = _field(cit, "document_id")
        source_type = _field(cit, "source_type")
        source_type_val = getattr(source_type, "value", str(source_type)).lower()

        # 1. Chunk existence check
        if chunk_id not in retrieved_set:
            issues.append(f"Citation chunk_id '{chunk_id}' was not in retrieved context")
            continue

        # 2. Scope isolation check
        if allowed_set is not None and doc_id not in allowed_set:
            issues.append(f"Citation document_id '{doc_id}' leaked outside allowed scope {allowed_doc_ids}")
            continue

        # 3. Source-specific metadata validation
        has_meta_issue = False
        if source_type_val == "pdf":
            page = _field(cit, "page_number")
            if page is None:
                issues.append(f"PDF citation missing page_number: {chunk_id}")
                has_meta_issue = True
        elif source_type_val == "xlsx":
            sheet = _field(cit, "sheet_name")
            if sheet is None:
                issues.append(f"XLSX citation missing sheet_name: {chunk_id}")
                has_meta_issue = True
        elif source_type_val == "youtube":
            ts = _field(cit, "timestamp_str")
            if not ts:
                issues.append(f"YouTube citation missing timestamp_str: {chunk_id}")
                has_meta_issue = True

        if not has_meta_issue:
            valid_count += 1

    accuracy = round(valid_count / len(citations), 4) if citations else 1.0
    return {
        "citation_count": len(citations),
        "valid_citations": valid_count,
        "accuracy": accuracy,
        "issues": issues
    }

def evaluate_groundedness(
    answer: str,
    context_texts: List[str]
) -> Dict[str, Any]:
    """
    Deterministic groundedness check: evaluates lexical support of key n-grams
    and entity terms from the answer within the retrieved context chunks.
    Detects unsupported statements.
    """
    insufficient_phrases = [
        "do not contain enough information",
        "does not contain enough information",
        "insufficient information"
    ]
    is_refusal = any(p in answer.lower() for p in insufficient_phrases)
    if is_refusal:
        return {
            "score": 1.0,
            "is_refusal": True,
            "supported_ratio": 1.0
        }

    DISCOURSE_MARKERS = {
        "based", "provided", "sources", "source", "according", "context", "information",
        "stated", "states", "shows", "referenced", "explained", "mentions", "details",
        "section", "document", "report", "question", "following"
    }

    combined_context = " ".join(context_texts).lower()
    answer_words = [
        w.strip(".,;:?!'\"()[]{}")
        for w in answer.lower().split()
        if len(w) > 3 and w.strip(".,;:?!'\"()[]{}") not in DISCOURSE_MARKERS
    ]

    if not answer_words:
        return {
            "score": 1.0,
            "is_refusal": False,
            "supported_ratio": 1.0
        }

    matched_words = [w for w in answer_words if w in combined_context]
    support_ratio = round(len(matched_words) / len(answer_words), 4)

    return {
        "score": support_ratio,
        "is_refusal": False,
        "supported_ratio": support_ratio
    }

def calculate_latency_percentiles(latencies: List[float]) -> Dict[str, float]:
    """
    Calculates P50, P90, P95, P99, min, max, and avg for a sequence of latencies (in milliseconds).
    """
    if not latencies:
        return {
            "p50_ms": 0.0,
            "p90_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "avg_ms": 0.0
        }

    sorted_lats = sorted(latencies)
    n = len(sorted_lats)

    def percentile(p: float) -> float:
        idx = int(math.ceil(p * n)) - 1
        return round(sorted_lats[max(0, min(idx, n - 1))], 2)

    return {
        "p50_ms": percentile(0.50),
        "p90_ms": percentile(0.90),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "min_ms": round(sorted_lats[0], 2),
        "max_ms": round(sorted_lats[-1], 2),
        "avg_ms": round(sum(sorted_lats) / n, 2)
    }
