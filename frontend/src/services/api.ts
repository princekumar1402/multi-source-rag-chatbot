import { DocumentItem, Citation, SystemHealth, IngestionJobItem } from '../types';

const API_BASE = '/api/v1';

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchDocuments(workspaceId = 'default'): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/documents?workspace_id=${workspaceId}`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  return res.json();
}

export async function uploadFile(file: File, workspaceId = 'default', title?: string): Promise<IngestionJobItem> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('workspace_id', workspaceId);
  if (title) formData.append('title', title);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to upload document file');
  }
  return data;
}

export async function ingestUrl(url: string, workspaceId = 'default', title?: string): Promise<IngestionJobItem> {
  const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
  const endpoint = isYouTube ? `${API_BASE}/documents/youtube` : `${API_BASE}/documents/url`;

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, workspace_id: workspaceId, title })
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to ingest URL');
  }
  return data;
}

export async function fetchJobStatus(jobId: string): Promise<IngestionJobItem> {
  const res = await fetch(`${API_BASE}/ingestion/jobs/${jobId}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to fetch job status');
  }
  return data;
}

export async function retryJob(jobId: string): Promise<IngestionJobItem> {
  const res = await fetch(`${API_BASE}/ingestion/jobs/${jobId}/retry`, {
    method: 'POST'
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to retry job');
  }
  return data;
}

export interface JobEventCallbacks {
  onUpdate: (event: IngestionJobItem) => void;
  onComplete: (event: IngestionJobItem) => void;
  onError: (event: IngestionJobItem) => void;
}

/**
 * Connects to the SSE endpoint for a given ingestion job and streams real-time updates.
 * Returns an unsubscribe cleanup function.
 */
export function subscribeToJobEvents(
  jobId: string,
  workspaceId: string = 'default',
  callbacks: JobEventCallbacks
): () => void {
  const url = `${API_BASE}/ingestion/jobs/${encodeURIComponent(jobId)}/events?workspace_id=${encodeURIComponent(workspaceId)}`;
  const eventSource = new EventSource(url);

  const handleMessage = (e: MessageEvent) => {
    try {
      const data: IngestionJobItem = JSON.parse(e.data);
      callbacks.onUpdate(data);

      if (data.status === 'completed') {
        eventSource.close();
        callbacks.onComplete(data);
      } else if (data.status === 'failed' || data.status === 'cancelled') {
        eventSource.close();
        callbacks.onError(data);
      }
    } catch (err) {
      console.error('Failed to parse SSE event data', err);
    }
  };

  eventSource.addEventListener('current_state', handleMessage);
  eventSource.addEventListener('job_created', handleMessage);
  eventSource.addEventListener('job_started', handleMessage);
  eventSource.addEventListener('job_stage_changed', handleMessage);

  eventSource.addEventListener('job_completed', (e: MessageEvent) => {
    try {
      const data: IngestionJobItem = JSON.parse(e.data);
      eventSource.close();
      callbacks.onComplete(data);
    } catch (err) {
      console.error('Failed to parse SSE completion data', err);
    }
  });

  eventSource.addEventListener('job_failed', (e: MessageEvent) => {
    try {
      const data: IngestionJobItem = JSON.parse(e.data);
      eventSource.close();
      callbacks.onError(data);
    } catch (err) {
      console.error('Failed to parse SSE failure data', err);
    }
  });

  eventSource.onmessage = handleMessage;

  eventSource.onerror = (err) => {
    console.warn(`SSE stream error for job ${jobId}; EventSource will auto-reconnect`, err);
  };

  return () => {
    eventSource.close();
  };
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete document');
}

export interface QueryResponse {
  question: string;
  standalone_query: string;
  answer: string;
  citations: Citation[];
  has_sufficient_context: boolean;
  retrieved_count: number;
  latency_seconds: number;
}

export async function queryRAG(
  question: string,
  history: { role: string; content: string }[] = [],
  workspaceId = 'default',
  documentIds?: string[]
): Promise<QueryResponse> {
  const payload: any = {
    question,
    history,
    workspace_id: workspaceId,
    top_k: 5,
    enable_query_rewriting: true,
    enable_reranking: true
  };
  if (documentIds && documentIds.length > 0) {
    payload.document_ids = documentIds;
  }

  const res = await fetch(`${API_BASE}/chat/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'RAG query failed');
  }
  return data;
}
