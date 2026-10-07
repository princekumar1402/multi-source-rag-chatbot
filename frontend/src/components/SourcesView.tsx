import React from 'react';
import {
  FileText,
  FileSpreadsheet,
  Globe,
  Video,
  Plus,
  ArrowRight,
  Database,
  Layers,
  Sparkles
} from 'lucide-react';
import { DocumentItem } from '../types';

interface SourcesViewProps {
  documents: DocumentItem[];
  onOpenUploadModal: () => void;
  onFilterByCategory: (type: string) => void;
}

export const SourcesView: React.FC<SourcesViewProps> = ({
  documents,
  onOpenUploadModal,
  onFilterByCategory
}) => {
  const fileDocs = documents.filter((d) => ['pdf', 'docx', 'txt', 'markdown'].includes(d.source_type));
  const tableDocs = documents.filter((d) => ['xlsx', 'csv'].includes(d.source_type));
  const webDocs = documents.filter((d) => d.source_type === 'web');
  const youtubeDocs = documents.filter((d) => d.source_type === 'youtube');

  const categories = [
    {
      title: 'Unstructured Documents',
      description: 'PDF, Microsoft Word, Markdown, and Plain text documents with semantic chunking.',
      icon: <FileText size={24} style={{ color: '#3b82f6' }} />,
      count: fileDocs.length,
      chunks: fileDocs.reduce((acc, d) => acc + d.chunk_count, 0),
      type: 'pdf'
    },
    {
      title: 'Structured Spreadsheets',
      description: 'Excel (.xlsx) and CSV files parsed with sheet and row-level citation references.',
      icon: <FileSpreadsheet size={24} style={{ color: '#10b981' }} />,
      count: tableDocs.length,
      chunks: tableDocs.reduce((acc, d) => acc + d.chunk_count, 0),
      type: 'xlsx'
    },
    {
      title: 'Websites & Documentation',
      description: 'Web pages and technical documentation articles extracted with boilerplate removal.',
      icon: <Globe size={24} style={{ color: '#6366f1' }} />,
      count: webDocs.length,
      chunks: webDocs.reduce((acc, d) => acc + d.chunk_count, 0),
      type: 'web'
    },
    {
      title: 'YouTube Transcripts',
      description: 'Video audio transcripts with automatic timestamp mapping down to the second.',
      icon: <Video size={24} style={{ color: '#ef4444' }} />,
      count: youtubeDocs.length,
      chunks: youtubeDocs.reduce((acc, d) => acc + d.chunk_count, 0),
      type: 'youtube'
    }
  ];

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
              MULTI-MODAL KNOWLEDGE
            </div>
            <h1
              style={{
                fontSize: '1.5rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                marginTop: '0.25rem'
              }}
            >
              Connected Source Channels
            </h1>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Universal RAG integration across 8 distinct file formats and remote media types.
            </p>
          </div>

          <button onClick={onOpenUploadModal} className="gw-btn-primary">
            <Plus size={16} />
            <span>Connect Source</span>
          </button>
        </div>

        {/* Source Channel Cards Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(440px, 1fr))',
            gap: '1.25rem'
          }}
        >
          {categories.map((cat) => (
            <div
              key={cat.title}
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                padding: '1.5rem',
                boxShadow: 'var(--shadow-subtle)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <div
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '10px',
                      backgroundColor: 'var(--bg-surface-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    {cat.icon}
                  </div>

                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: 'var(--brand-blue)',
                      backgroundColor: 'var(--bg-active-nav)',
                      padding: '2px 8px',
                      borderRadius: '12px'
                    }}
                  >
                    {cat.count} sources
                  </span>
                </div>

                <h3 style={{ fontSize: '1.0625rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {cat.title}
                </h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.375rem', lineHeight: 1.5 }}>
                  {cat.description}
                </p>
              </div>

              <div
                style={{
                  marginTop: '1.5rem',
                  paddingTop: '1rem',
                  borderTop: '1px solid var(--border-color)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{cat.chunks}</span> vector chunks indexed
                </div>

                <button
                  onClick={() => onFilterByCategory(cat.type)}
                  className="gw-btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.625rem' }}
                >
                  <span>View sources</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
