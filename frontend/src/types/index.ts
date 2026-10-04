export type SourceType = 'web' | 'youtube' | 'pdf' | 'docx' | 'txt' | 'markdown' | 'csv' | 'xlsx';

export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed';

export interface Citation {
  chunk_id: string;
  document_id: string;
  source_title: string;
  source_type: SourceType;
  file_name?: string;
  source_url?: string;
  page_number?: number;
  page_index?: number;
  sheet_name?: string;
  row_number?: number;
  timestamp_str?: string;
  start_time?: number;
  end_time?: number;
  section_title?: string;
  snippet: string;
  relevance_score?: number;
}

export interface DocumentItem {
  id: string;
  title: string;
  source_type: SourceType;
  file_name?: string;
  source_url?: string;
  workspace_id: string;
  status: DocumentStatus;
  content_hash: string;
  chunk_count: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  latency_seconds?: number;
  has_sufficient_context?: boolean;
}

export interface SystemHealth {
  status: string;
  app_env: string;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  embedding_model: string;
  vector_store: string;
  indexed_chunks: number;
}

export type IngestionJobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface IngestionJobItem {
  job_id: string;
  document_id?: string;
  workspace_id: string;
  status: IngestionJobStatus;
  stage?: string;
  progress?: number;
  error?: string;
  source_type: string;
  retry_count: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}
