import React from 'react';
import { Video, Globe, Trash2, CheckCircle2, AlertCircle, Layers, FileText, Table, FileSpreadsheet, FileCode } from 'lucide-react';
import { DocumentItem } from '../types';

interface DocumentListProps {
  documents: DocumentItem[];
  onDelete: (id: string) => Promise<void>;
  isLoading: boolean;
}

export const DocumentList: React.FC<DocumentListProps> = ({ documents, onDelete, isLoading }) => {
  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'youtube':
        return <Video size={16} style={{ color: '#ef4444' }} />;
      case 'pdf':
        return <FileText size={16} style={{ color: '#3b82f6' }} />;
      case 'docx':
        return <FileText size={16} style={{ color: '#6366f1' }} />;
      case 'csv':
        return <Table size={16} style={{ color: '#f59e0b' }} />;
      case 'xlsx':
        return <FileSpreadsheet size={16} style={{ color: '#10b981' }} />;
      case 'markdown':
        return <FileCode size={16} style={{ color: '#ec4899' }} />;
      case 'txt':
        return <FileText size={16} style={{ color: '#94a3b8' }} />;
      default:
        return <Globe size={16} style={{ color: '#10b981' }} />;
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '0.9375rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Layers size={16} style={{ color: 'var(--accent-primary)' }} />
          <span>Knowledge Documents ({documents.length})</span>
        </h2>
      </div>

      {documents.length === 0 ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          color: 'var(--text-muted)',
          padding: '2rem 1rem'
        }}>
          <Layers size={32} style={{ opacity: 0.3, marginBottom: '0.75rem' }} />
          <p style={{ fontSize: '0.875rem', fontWeight: '500' }}>No sources ingested yet</p>
          <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
            Upload documents (PDF, DOCX, TXT, MD, CSV, XLSX) or paste URLs above.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem', overflowY: 'auto' }}>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="glass-panel-interactive"
              style={{ padding: '0.75rem 1rem' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
                <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'flex-start' }}>
                  <div style={{
                    marginTop: '2px',
                    padding: '6px',
                    borderRadius: '6px',
                    background: 'var(--bg-input)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {getSourceIcon(doc.source_type)}
                  </div>
                  <div>
                    <h3 style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-primary)', lineHeight: '1.3' }}>
                      {doc.title}
                    </h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem', fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                      <span style={{
                        textTransform: 'uppercase',
                        fontWeight: '700',
                        fontSize: '0.625rem',
                        padding: '1px 5px',
                        borderRadius: '4px',
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid var(--border-color)'
                      }}>
                        {doc.source_type}
                      </span>
                      <span>•</span>
                      <span>{doc.chunk_count} chunks</span>
                      <span>•</span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px', color: doc.status === 'ready' ? 'var(--success)' : 'var(--danger)' }}>
                        {doc.status === 'ready' ? <CheckCircle2 size={11} /> : <AlertCircle size={11} />}
                        {doc.status}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => onDelete(doc.id)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '4px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                  title="Delete document and vector index"
                >
                  <Trash2 size={14} style={{ color: 'var(--danger)' }} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
