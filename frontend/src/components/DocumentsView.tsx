import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  FileText,
  Video,
  Globe,
  Table,
  FileSpreadsheet,
  FileCode,
  Upload,
  Plus,
  ArrowUpDown,
  MessageSquare
} from 'lucide-react';
import { DocumentItem, SourceType } from '../types';

interface DocumentsViewProps {
  documents: DocumentItem[];
  onDeleteDocument: (id: string) => Promise<void>;
  onOpenUploadModal: () => void;
  onQueryDocumentInChat: (docId: string) => void;
}

export const DocumentsView: React.FC<DocumentsViewProps> = ({
  documents,
  onDeleteDocument,
  onOpenUploadModal,
  onQueryDocumentInChat
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'date' | 'title' | 'chunks'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const getSourceIcon = (type: SourceType) => {
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

  const filteredDocs = useMemo(() => {
    return documents
      .filter((doc) => {
        const matchesSearch =
          (doc.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
          (doc.file_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
          (doc.source_url || '').toLowerCase().includes(searchQuery.toLowerCase());
        const matchesType = selectedType === 'all' || doc.source_type === selectedType;
        const matchesStatus = selectedStatus === 'all' || doc.status === selectedStatus;
        return matchesSearch && matchesType && matchesStatus;
      })
      .sort((a, b) => {
        if (sortBy === 'date') {
          const dateA = new Date(a.created_at).getTime();
          const dateB = new Date(b.created_at).getTime();
          return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
        } else if (sortBy === 'title') {
          return sortOrder === 'desc'
            ? b.title.localeCompare(a.title)
            : a.title.localeCompare(b.title);
        } else if (sortBy === 'chunks') {
          return sortOrder === 'desc'
            ? b.chunk_count - a.chunk_count
            : a.chunk_count - b.chunk_count;
        }
        return 0;
      });
  }, [documents, searchQuery, selectedType, selectedStatus, sortBy, sortOrder]);

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this document from the knowledge base?')) {
      setDeletingId(id);
      try {
        await onDeleteDocument(id);
      } finally {
        setDeletingId(null);
      }
    }
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
      <div style={{ maxWidth: '1100px', width: '100%', margin: '0 auto' }}>
        {/* Top Header */}
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
              KNOWLEDGE REPOSITORY
            </div>
            <h1
              style={{
                fontSize: '1.5rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                marginTop: '0.25rem'
              }}
            >
              Documents & Sources
            </h1>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Manage multi-source ingested files, spreadsheets, articles, and video transcripts.
            </p>
          </div>

          <button
            onClick={onOpenUploadModal}
            className="gw-btn-primary"
            style={{ padding: '0.625rem 1.125rem' }}
          >
            <Plus size={16} />
            <span>Add Knowledge</span>
          </button>
        </div>

        {/* Filter and Search Controls Card */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '1rem',
            marginBottom: '1.25rem',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.75rem',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: 'var(--shadow-subtle)'
          }}
        >
          {/* Search Box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              padding: '0.4rem 0.75rem',
              minWidth: '260px'
            }}
          >
            <Search size={15} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents by title or url..."
              style={{
                border: 'none',
                outline: 'none',
                backgroundColor: 'transparent',
                color: 'var(--text-primary)',
                fontSize: '0.8125rem',
                width: '100%'
              }}
            />
          </div>

          {/* Filter Selectors */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
            {/* Source Type Filter */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '0.4rem 0.625rem',
                fontSize: '0.8125rem',
                color: 'var(--text-secondary)',
                outline: 'none'
              }}
            >
              <option value="all">All Source Types</option>
              <option value="pdf">PDF Documents</option>
              <option value="docx">Word (.docx)</option>
              <option value="csv">CSV Spreadsheets</option>
              <option value="xlsx">Excel (.xlsx)</option>
              <option value="txt">Plain Text (.txt)</option>
              <option value="markdown">Markdown (.md)</option>
              <option value="web">Websites</option>
              <option value="youtube">YouTube Videos</option>
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '0.4rem 0.625rem',
                fontSize: '0.8125rem',
                color: 'var(--text-secondary)',
                outline: 'none'
              }}
            >
              <option value="all">All Statuses</option>
              <option value="ready">Ready</option>
              <option value="processing">Processing</option>
              <option value="failed">Failed</option>
            </select>

            {/* Sort Filter */}
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="gw-btn-secondary"
              title="Toggle sort direction"
            >
              <ArrowUpDown size={14} />
              <span>{sortBy === 'date' ? 'Date' : sortBy === 'title' ? 'Title' : 'Chunks'} ({sortOrder})</span>
            </button>
          </div>
        </div>

        {/* Document List Table / Cards */}
        {filteredDocs.length === 0 ? (
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
              No documents matched your criteria
            </h3>
            <p style={{ fontSize: '0.8125rem', marginTop: '0.25rem' }}>
              Upload new PDF, Word, Spreadsheets, or add Web/YouTube URLs to populate the knowledge base.
            </p>
            <button
              onClick={onOpenUploadModal}
              className="gw-btn-primary"
              style={{ marginTop: '1rem' }}
            >
              <Plus size={15} />
              <span>Ingest Document Now</span>
            </button>
          </div>
        ) : (
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              overflow: 'hidden',
              boxShadow: 'var(--shadow-subtle)'
            }}
          >
            {filteredDocs.map((doc, idx) => (
              <div
                key={doc.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '1rem 1.25rem',
                  borderBottom: idx < filteredDocs.length - 1 ? '1px solid var(--border-color)' : 'none',
                  transition: 'background-color 0.15s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', minWidth: 0 }}>
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '8px',
                      backgroundColor: 'var(--bg-surface-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                  >
                    {getSourceIcon(doc.source_type)}
                  </div>

                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '480px'
                      }}
                    >
                      {doc.title}
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        fontSize: '0.75rem',
                        color: 'var(--text-muted)',
                        marginTop: '2px'
                      }}
                    >
                      <span
                        style={{
                          textTransform: 'uppercase',
                          fontWeight: 700,
                          fontSize: '0.625rem',
                          padding: '1px 5px',
                          borderRadius: '4px',
                          backgroundColor: 'var(--bg-surface-subtle)',
                          border: '1px solid var(--border-color)'
                        }}
                      >
                        {doc.source_type}
                      </span>
                      <span>•</span>
                      <span>{doc.chunk_count} chunks indexed</span>
                      <span>•</span>
                      <span>
                        {new Date(doc.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right Status & Actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
                  {/* Status Indicator */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem' }}>
                    {doc.status === 'ready' ? (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          color: 'var(--success)',
                          backgroundColor: 'var(--success-bg)',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontWeight: 600
                        }}
                      >
                        <CheckCircle2 size={12} />
                        <span>Ready</span>
                      </span>
                    ) : doc.status === 'failed' ? (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          color: 'var(--danger)',
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontWeight: 600
                        }}
                      >
                        <AlertCircle size={12} />
                        <span>Failed</span>
                      </span>
                    ) : (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          color: 'var(--warning)',
                          backgroundColor: 'rgba(245, 158, 11, 0.1)',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontWeight: 600
                        }}
                      >
                        <Clock size={12} />
                        <span>Processing</span>
                      </span>
                    )}
                  </div>

                  {/* Query Document in Chat */}
                  <button
                    onClick={() => onQueryDocumentInChat(doc.id)}
                    className="gw-btn-secondary"
                    style={{ padding: '0.35rem 0.625rem', fontSize: '0.75rem' }}
                    title="Scope query to this document in Chat"
                  >
                    <MessageSquare size={13} />
                    <span>Chat</span>
                  </button>

                  {/* Delete Document */}
                  <button
                    onClick={() => handleDelete(doc.id)}
                    disabled={deletingId === doc.id}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--danger)',
                      cursor: deletingId === doc.id ? 'not-allowed' : 'pointer',
                      padding: '4px',
                      opacity: deletingId === doc.id ? 0.4 : 0.8
                    }}
                    title="Delete document and remove vector chunks"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
