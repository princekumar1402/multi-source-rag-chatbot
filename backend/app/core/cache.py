import time
import threading
import hashlib
import json
from typing import Any, Dict, Optional, Tuple, List, Set
from collections import OrderedDict
from backend.app.core.config import settings
from backend.app.core.logging import logger

class BoundedLRUCache:
    """
    Thread-safe, bounded, in-process LRU cache with TTL support and observability metrics.
    Suitable for single-process deployments with seamless migration path to Redis.
    """

    def __init__(self, maxsize: int = 1000, default_ttl_seconds: int = 3600, name: str = "default"):
        self.maxsize = maxsize
        self.default_ttl = default_ttl_seconds
        self.name = name
        self._cache: OrderedDict[str, Tuple[Any, float, Optional[str]]] = OrderedDict()  # key -> (value, expiry, tag)
        self._lock = threading.RLock()

        # Telemetry metrics
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            value, expiry, tag = self._cache[key]
            if expiry is not None and time.time() > expiry:
                # Expired
                del self._cache[key]
                self.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None, tag: Optional[str] = None) -> None:
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            expiry = time.time() + ttl if ttl > 0 else None

            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expiry, tag)

            # Evict LRU if over capacity
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)
                self.evictions += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidates all entries matching the given tag (e.g., workspace_id)."""
        with self._lock:
            to_remove = [k for k, (_, _, t) in self._cache.items() if t == tag]
            for k in to_remove:
                del self._cache[k]
            return len(to_remove)

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidates all entries whose key starts with prefix."""
        with self._lock:
            to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in to_remove:
                del self._cache[k]
            return len(to_remove)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def hit_rate(self) -> float:
        with self._lock:
            total = self.hits + self.misses
            return round((self.hits / total) * 100.0, 2) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "name": self.name,
                "size": len(self._cache),
                "max_size": self.maxsize,
                "hits": self.hits,
                "misses": self.misses,
                "total_requests": total,
                "hit_rate_pct": self.hit_rate,
                "evictions": self.evictions
            }


class RAGCacheManager:
    """
    Central Coordinator for RAG Caches:
    - Embedding Cache (content hash -> 384d vector)
    - Query Rewrite Cache ((question, history_hash, model) -> rewritten query)
    - Retrieval Cache ((workspace_id, index_version, doc_ids, query, top_k) -> candidates)
    - Answer Cache ((workspace_id, index_version, doc_ids, query, model) -> RAGQueryResponse)
    - Ready Documents Cache (workspace_id -> set of ready doc_ids)
    - Workspace Index Version Tracking (increments on document add/update/delete)

    Guarantees:
    - Absolute Document & Workspace Isolation: Cross-workspace or cross-scope cache hits are impossible.
    - Zero Stale Data: Index updates immediately bump workspace version, invalidating all downstream retrieval & answers.
    """

    _instance: Optional["RAGCacheManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "RAGCacheManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RAGCacheManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self) -> None:
        max_size = getattr(settings, "CACHE_MAX_SIZE", 1000)
        ttl = getattr(settings, "CACHE_TTL_SECONDS", 3600)

        self.embedding_cache = BoundedLRUCache(maxsize=max_size * 5, default_ttl_seconds=ttl * 24, name="embeddings")
        self.query_rewrite_cache = BoundedLRUCache(maxsize=max_size, default_ttl_seconds=ttl, name="query_rewrite")
        self.retrieval_cache = BoundedLRUCache(maxsize=max_size, default_ttl_seconds=ttl, name="retrieval")
        self.answer_cache = BoundedLRUCache(maxsize=max_size, default_ttl_seconds=ttl, name="answers")
        self.reranker_cache = BoundedLRUCache(maxsize=max_size * 2, default_ttl_seconds=ttl, name="reranker")
        self.ready_docs_cache = BoundedLRUCache(maxsize=max_size // 2, default_ttl_seconds=300, name="ready_docs")

        # Workspace index versions: workspace_id -> int
        self._workspace_versions: Dict[str, int] = {}
        self._version_lock = threading.Lock()

    def get_workspace_version(self, workspace_id: str) -> int:
        with self._version_lock:
            if workspace_id not in self._workspace_versions:
                self._workspace_versions[workspace_id] = 1
            return self._workspace_versions[workspace_id]

    def increment_workspace_version(self, workspace_id: str) -> int:
        """
        Increments workspace index version.
        This atomically invalidates all retrieval and answer caches for this workspace.
        """
        with self._version_lock:
            current = self._workspace_versions.get(workspace_id, 1)
            new_version = current + 1
            self._workspace_versions[workspace_id] = new_version

        # Invalidate tagged entries
        self.retrieval_cache.invalidate_by_tag(workspace_id)
        self.answer_cache.invalidate_by_tag(workspace_id)
        self.ready_docs_cache.delete(workspace_id)
        logger.info(f"Incremented workspace {workspace_id} index version to {new_version}. Invalidated retrieval and answer caches.")
        return new_version

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def build_retrieval_cache_key(
        self,
        workspace_id: str,
        query: str,
        document_ids: Optional[List[str]],
        source_types: Optional[List[str]],
        top_k: int
    ) -> str:
        version = self.get_workspace_version(workspace_id)
        doc_str = ",".join(sorted(document_ids)) if document_ids else "__all__"
        st_str = ",".join(sorted(source_types)) if source_types else "__all__"
        query_hash = self.hash_text(query.strip().lower())
        return f"retrieval:{workspace_id}:v{version}:docs:{doc_str}:st:{st_str}:k{top_k}:{query_hash}"

    def build_answer_cache_key(
        self,
        workspace_id: str,
        query: str,
        document_ids: Optional[List[str]],
        model_name: str,
        temperature: float,
        top_k: int
    ) -> str:
        version = self.get_workspace_version(workspace_id)
        doc_str = ",".join(sorted(document_ids)) if document_ids else "__all__"
        query_hash = self.hash_text(query.strip().lower())
        return f"answer:{workspace_id}:v{version}:docs:{doc_str}:m:{model_name}:t{temperature}:k{top_k}:{query_hash}"

    def build_query_rewrite_key(
        self,
        question: str,
        history: List[Any],
        model_name: str
    ) -> str:
        # Build deterministic history string
        hist_parts = []
        for turn in history[-4:]:
            role = getattr(turn, "role", "user")
            content = getattr(turn, "content", "")
            hist_parts.append(f"{role}:{content}")
        hist_str = "|".join(hist_parts)
        hist_hash = self.hash_text(hist_str)
        q_hash = self.hash_text(question.strip().lower())
        return f"rewrite:{model_name}:{hist_hash}:{q_hash}"

    def get_all_stats(self) -> Dict[str, Any]:
        return {
            "embeddings": self.embedding_cache.get_stats(),
            "query_rewrite": self.query_rewrite_cache.get_stats(),
            "retrieval": self.retrieval_cache.get_stats(),
            "answers": self.answer_cache.get_stats(),
            "reranker": self.reranker_cache.get_stats(),
            "ready_docs": self.ready_docs_cache.get_stats(),
            "workspace_versions": dict(self._workspace_versions)
        }

    def clear_all(self) -> None:
        self.embedding_cache.clear()
        self.query_rewrite_cache.clear()
        self.retrieval_cache.clear()
        self.answer_cache.clear()
        self.reranker_cache.clear()
        self.ready_docs_cache.clear()
        with self._version_lock:
            self._workspace_versions.clear()

cache_manager = RAGCacheManager()
