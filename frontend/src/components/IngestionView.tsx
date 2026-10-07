import React from 'react';
import {
  Layers,
  Loader2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Plus,
  Clock,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';
import { IngestionJobItem } from '../types';

interface IngestionViewProps {
  activeJobs: IngestionJobItem[];
  onRetryJob: (jobId: string) => Promise<void>;
  onOpenUploadModal: () => void;
}

const INGESTION_STAGES = [
  'Validating',
  'Extracting',
  'Chunking',
  'Embedding',
  'Indexing',
  'Finalizing'
];

export const IngestionView: React.FC<IngestionViewProps> = ({
  activeJobs,
  onRetryJob,
  onOpenUploadModal
}) => {
  const getStageIndex = (stage?: string) => {
    if (!stage) return 0;
    const lower = stage.toLowerCase();
    if (lower.includes('val')) return 0;
    if (lower.includes('ext')) return 1;
    if (lower.includes('chu')) return 2;
    if (lower.includes('emb') || lower.includes('pers')) return 3;
    if (lower.includes('ind')) return 4;
    if (lower.includes('fin')) return 5;
    if (lower.includes('com')) return 6;
    return 0;
  };

  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg-app)',
        overflowY: 'auto',
        padding: '2rem'
      }}
    >
      <div style={{ maxWidth: '1000px', width: '100%', margin: '0 auto' }}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '1.5rem'
          }}
        >
          <div>
            <div
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                letterSpacing: '0.08em',
                color: 'var(--text-muted)'
              }}
            >
              REAL-TIME SSE PIPELINE
            </div>
            <h1
              style={{
                fontSize: '1.5rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                marginTop: '0.25rem'
              }}
            >
              Ingestion Job Monitor
            </h1>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Authoritative asynchronous extraction, chunking, and dual-index embedding streams.
            </p>
          </div>

          <button onClick={onOpenUploadModal} className="gw-btn-primary">
            <Plus size={16} />
            <span>New Ingestion Job</span>
          </button>
        </div>

        {/* Live SSE Jobs List */}
        {activeJobs.length === 0 ? (
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              padding: '3rem 2rem',
              textAlign: 'center',
              color: 'var(--text-muted)'
            }}
          >
            <Layers size={36} style={{ margin: '0 auto 0.75rem auto', opacity: 0.4 }} />
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              No active ingestion jobs
            </h3>
            <p style={{ fontSize: '0.8125rem', marginTop: '0.25rem' }}>
              When you upload documents or add URLs, live stage transitions stream here automatically via SSE.
            </p>
            <button
              onClick={onOpenUploadModal}
              className="gw-btn-primary"
              style={{ marginTop: '1rem' }}
            >
              <Plus size={15} />
              <span>Start Ingestion</span>
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {activeJobs.map((job) => {
              const isRunning = job.status === 'pending' || job.status === 'processing';
              const isCompleted = job.status === 'completed';
              const isFailed = job.status === 'failed';
              const currentStageIdx = isCompleted ? 6 : getStageIndex(job.stage);

              return (
                <div
                  key={job.job_id}
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-color)',
                    borderLeft: isRunning
                      ? '4px solid var(--brand-blue)'
                      : isCompleted
                      ? '4px solid var(--success)'
                      : '4px solid var(--danger)',
                    borderRadius: '10px',
                    padding: '1.25rem',
                    boxShadow: 'var(--shadow-subtle)'
                  }}
                >
                  {/* Job Header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.875rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                      {isRunning && <Loader2 size={18} className="animate-spin" style={{ color: 'var(--brand-blue)' }} />}
                      {isCompleted && <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />}
                      {isFailed && <AlertCircle size={18} style={{ color: 'var(--danger)' }} />}

                      <div>
                        <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                          Job ID: {job.job_id}
                        </div>
                        <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                          Source: <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>{job.source_type}</span> · Workspace: {job.workspace_id}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      {isFailed && (
                        <button
                          onClick={() => onRetryJob(job.job_id)}
                          className="gw-btn-secondary"
                          style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
                        >
                          <RefreshCw size={13} />
                          <span>Retry</span>
                        </button>
                      )}

                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          textTransform: 'uppercase',
                          backgroundColor: isCompleted
                            ? 'var(--success-bg)'
                            : isFailed
                            ? 'rgba(239, 68, 68, 0.1)'
                            : 'var(--bg-active-nav)',
                          color: isCompleted
                            ? 'var(--success)'
                            : isFailed
                            ? 'var(--danger)'
                            : 'var(--brand-blue)'
                        }}
                      >
                        {job.status}
                      </span>
                    </div>
                  </div>

                  {/* Pipeline Stage Steps */}
                  <div style={{ margin: '1rem 0' }}>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: `repeat(${INGESTION_STAGES.length}, 1fr)`,
                        gap: '0.5rem'
                      }}
                    >
                      {INGESTION_STAGES.map((stageName, sIdx) => {
                        const isDone = isCompleted || sIdx < currentStageIdx;
                        const isCurrent = isRunning && sIdx === currentStageIdx;
                        return (
                          <div
                            key={stageName}
                            style={{
                              padding: '0.5rem 0.625rem',
                              borderRadius: '6px',
                              backgroundColor: isDone
                                ? 'var(--success-bg)'
                                : isCurrent
                                ? 'var(--bg-active-nav)'
                                : 'var(--bg-surface-subtle)',
                              border: `1px solid ${
                                isDone
                                  ? 'rgba(16, 185, 129, 0.3)'
                                  : isCurrent
                                  ? 'var(--brand-blue)'
                                  : 'var(--border-color)'
                              }`,
                              textAlign: 'center',
                              transition: 'all 0.2s ease'
                            }}
                          >
                            <div
                              style={{
                                fontSize: '0.625rem',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                color: isDone
                                  ? 'var(--success)'
                                  : isCurrent
                                  ? 'var(--brand-blue)'
                                  : 'var(--text-subtle)'
                              }}
                            >
                              Step {sIdx + 1}
                            </div>
                            <div
                              style={{
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                color: isDone
                                  ? 'var(--text-primary)'
                                  : isCurrent
                                  ? 'var(--brand-blue)'
                                  : 'var(--text-muted)',
                                marginTop: '2px'
                              }}
                            >
                              {stageName}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Status / Error Message */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                    <div style={{ color: isFailed ? 'var(--danger)' : 'var(--text-secondary)' }}>
                      {isCompleted && '✓ Ingestion complete and verified in vector index.'}
                      {isRunning && `Current stage: ${job.stage || 'Initializing pipeline...'}`}
                      {isFailed && `Error: ${job.error || 'Ingestion encountered an issue.'}`}
                    </div>

                    {job.progress !== undefined && job.progress !== null && (
                      <div style={{ fontWeight: 600, color: 'var(--brand-blue)' }}>
                        {job.progress}%
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
