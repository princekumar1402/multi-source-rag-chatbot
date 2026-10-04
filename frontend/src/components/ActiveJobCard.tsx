import React from 'react';
import { Loader2, CheckCircle2, AlertCircle, RefreshCw, X } from 'lucide-react';
import { IngestionJobItem } from '../types';

interface ActiveJobCardProps {
  job: IngestionJobItem;
  onRetry: (jobId: string) => Promise<void>;
  onDismiss: () => void;
}

export const ActiveJobCard: React.FC<ActiveJobCardProps> = ({ job, onRetry, onDismiss }) => {
  const isRunning = job.status === 'pending' || job.status === 'processing';
  const isCompleted = job.status === 'completed';
  const isFailed = job.status === 'failed';

  const getStageLabel = (stage?: string) => {
    if (!stage) return isRunning ? 'Initializing...' : '';
    switch (stage.toLowerCase()) {
      case 'validating': return 'Validating file...';
      case 'extracting': return 'Extracting text...';
      case 'chunking': return 'Chunking content...';
      case 'persisting': return 'Saving chunks to database...';
      case 'embedding': return 'Generating vector embeddings...';
      case 'indexing': return 'Indexing in FAISS & BM25...';
      case 'finalizing': return 'Finalizing consistency check...';
      case 'completed': return 'Ingestion complete!';
      default: return stage;
    }
  };

  return (
    <div
      className="glass-panel"
      style={{
        padding: '0.875rem 1rem',
        marginBottom: '1rem',
        borderLeft: isRunning
          ? '3px solid var(--accent-primary)'
          : isCompleted
          ? '3px solid var(--success)'
          : '3px solid var(--danger)',
        background: 'rgba(255, 255, 255, 0.03)',
        animation: 'fadeIn 0.2s ease-in-out'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {isRunning && (
            <Loader2 size={15} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
          )}
          {isCompleted && (
            <CheckCircle2 size={15} style={{ color: 'var(--success)' }} />
          )}
          {isFailed && (
            <AlertCircle size={15} style={{ color: 'var(--danger)' }} />
          )}

          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {isRunning ? 'Ingestion In Progress' : isCompleted ? 'Ingestion Succeeded' : 'Ingestion Failed'}
          </span>

          <span
            style={{
              textTransform: 'uppercase',
              fontSize: '0.625rem',
              fontWeight: 700,
              padding: '1px 5px',
              borderRadius: '4px',
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-muted)'
            }}
          >
            {job.source_type}
          </span>
        </div>

        <button
          onClick={onDismiss}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '2px',
            display: 'flex',
            alignItems: 'center'
          }}
          title="Dismiss"
        >
          <X size={13} />
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.25rem' }}>
        <span style={{ fontSize: '0.75rem', color: isFailed ? 'var(--danger)' : 'var(--text-secondary)' }}>
          {isFailed ? (job.error || 'Ingestion encountered an error.') : getStageLabel(job.stage)}
        </span>

        {job.progress !== undefined && job.progress !== null && isRunning && (
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {Math.round(job.progress * 100)}%
          </span>
        )}
      </div>

      {/* Progress Bar for active jobs */}
      {isRunning && job.progress !== undefined && job.progress !== null && (
        <div style={{
          width: '100%',
          height: '4px',
          background: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '2px',
          marginTop: '0.5rem',
          overflow: 'hidden'
        }}>
          <div style={{
            width: `${Math.max(5, Math.min(100, Math.round(job.progress * 100)))}%`,
            height: '100%',
            background: 'var(--accent-primary)',
            transition: 'width 0.3s ease'
          }} />
        </div>
      )}

      {/* Retry Action for Failed Jobs */}
      {isFailed && (
        <div style={{ marginTop: '0.625rem', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={() => onRetry(job.job_id)}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              background: 'var(--accent-primary)',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <RefreshCw size={12} />
            <span>Retry Ingestion</span>
          </button>
        </div>
      )}
    </div>
  );
};
