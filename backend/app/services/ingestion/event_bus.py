import asyncio
import threading
from typing import Dict, Set, Tuple, Optional
from backend.app.core.logging import logger
from backend.app.schemas.ingestion_job import IngestionEvent

class IngestionEventBus:
    """
    Lightweight, thread-safe in-process event bus for streaming ingestion job events.
    Decoupled from FastAPI HTTP response objects to keep the domain runner portable
    and future-migration-ready (e.g. for Redis Pub/Sub / Celery).
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Maps job_id -> set of (asyncio.Queue, asyncio.AbstractEventLoop)
        self._subscribers: Dict[str, Set[Tuple[asyncio.Queue, asyncio.AbstractEventLoop]]] = {}

    def subscribe(self, job_id: str, max_queue_size: int = 100) -> asyncio.Queue:
        """
        Subscribes to real-time events for a specific ingestion job.
        Must be called within an active asyncio event loop.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = set()
            self._subscribers[job_id].add((queue, loop))
            logger.debug(f"event_bus_subscribed | job_id={job_id} total_for_job={len(self._subscribers[job_id])}")
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribes a queue from a specific ingestion job and cleans up maps.
        Thread-safe and idempotent.
        """
        with self._lock:
            if job_id in self._subscribers:
                self._subscribers[job_id] = {
                    (q, loop) for (q, loop) in self._subscribers[job_id] if q is not queue
                }
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]
                logger.debug(f"event_bus_unsubscribed | job_id={job_id} remaining={len(self._subscribers.get(job_id, set()))}")

    def publish(self, job_id: str, event: IngestionEvent) -> int:
        """
        Publishes an event to all subscribers of a job.
        Can be safely invoked from any thread (e.g. sync BackgroundTasks or worker threads).
        Returns the number of subscribers notified.
        """
        with self._lock:
            subscribers = list(self._subscribers.get(job_id, set()))

        if not subscribers:
            return 0

        dispatched = 0
        for queue, loop in subscribers:
            try:
                if loop.is_closed():
                    continue

                def _put():
                    try:
                        if queue.full():
                            try:
                                queue.get_nowait()
                            except Exception:
                                pass
                        queue.put_nowait(event)
                    except Exception as ex:
                        logger.debug(f"Failed to put event into subscriber queue: {ex}")

                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None

                if current_loop is loop:
                    _put()
                else:
                    loop.call_soon_threadsafe(_put)
                dispatched += 1
            except Exception as e:
                logger.error(f"Error publishing ingestion event for job {job_id}: {e}")

        return dispatched

    def subscriber_count(self, job_id: str) -> int:
        """Returns the number of active subscribers for a specific job."""
        with self._lock:
            return len(self._subscribers.get(job_id, set()))

    def total_subscribers(self) -> int:
        """Returns the total number of subscriptions across all jobs."""
        with self._lock:
            return sum(len(subs) for subs in self._subscribers.values())

    def clear(self) -> None:
        """Clears all subscribers. Useful for test isolation."""
        with self._lock:
            self._subscribers.clear()
