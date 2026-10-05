from enum import Enum
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel
from backend.app.schemas.document import DocumentChunk

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class RetrievalConfidence(BaseModel):
    score: float
    level: ConfidenceLevel
    top_score: float
    score_margin: float
    candidate_count: int
    signals: List[str]

class RetrievalConfidenceAssessor:
    """
    Evaluates confidence of retrieved candidate sets using:
    1. Top candidate similarity/relevance score
    2. Score margin between top candidates (steep drop vs flat distribution)
    3. Candidate depth above minimum relevance threshold
    4. Overlap between dense and lexical (BM25) retrievers
    """

    def __init__(
        self,
        high_threshold: float = 0.65,
        low_threshold: float = 0.30,
        margin_threshold: float = 0.08
    ):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.margin_threshold = margin_threshold

    def assess(
        self,
        candidates: List[Tuple[DocumentChunk, float]],
        dense_candidates: Optional[List[Tuple[DocumentChunk, float]]] = None,
        bm25_candidates: Optional[List[Tuple[DocumentChunk, float]]] = None
    ) -> RetrievalConfidence:
        if not candidates:
            return RetrievalConfidence(
                score=0.0,
                level=ConfidenceLevel.LOW,
                top_score=0.0,
                score_margin=0.0,
                candidate_count=0,
                signals=["no_candidates_retrieved"]
            )

        top_score = float(candidates[0][1])
        second_score = float(candidates[1][1]) if len(candidates) > 1 else 0.0
        score_margin = max(0.0, top_score - second_score)
        signals: List[str] = []

        # 1. Base score from top candidate relevance
        base_confidence = min(1.0, max(0.0, top_score))

        # 2. Score margin signal
        if score_margin >= self.margin_threshold:
            signals.append("clear_top_candidate")
            base_confidence = min(1.0, base_confidence + 0.10)
        elif len(candidates) > 1 and score_margin < 0.02:
            signals.append("narrow_candidate_margin")

        # 3. Dense & BM25 overlap bonus
        if dense_candidates and bm25_candidates:
            dense_ids = {c.chunk_id for c, _ in dense_candidates[:5]}
            bm25_ids = {c.chunk_id for c, _ in bm25_candidates[:5]}
            overlap = len(dense_ids.intersection(bm25_ids))
            if overlap >= 2:
                signals.append(f"strong_hybrid_consensus_{overlap}_chunks")
                base_confidence = min(1.0, base_confidence + 0.15)
            elif overlap == 0:
                signals.append("zero_hybrid_overlap")
                base_confidence = max(0.0, base_confidence - 0.10)

        # 4. Determine Confidence Level
        if base_confidence >= self.high_threshold:
            level = ConfidenceLevel.HIGH
        elif base_confidence >= self.low_threshold:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return RetrievalConfidence(
            score=round(base_confidence, 4),
            level=level,
            top_score=round(top_score, 4),
            score_margin=round(score_margin, 4),
            candidate_count=len(candidates),
            signals=signals
        )
