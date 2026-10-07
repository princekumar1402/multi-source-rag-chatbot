import React, { useState, useRef } from 'react';
import {
  X,
  Upload,
  Globe,
  Video,
  FileText,
  Loader2,
  AlertCircle,
  FileSpreadsheet,
  Check
} from 'lucide-react';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadFile: (file: File, title?: string) => Promise<void>;
  onIngestUrl: (url: string, title?: string) => Promise<void>;
  isLoading: boolean;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadFile,
  onIngestUrl,
  isLoading
}) => {
  const [tab, setTab] = useState<'file' | 'url'>('file');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const isYouTube = url.toLowerCase().includes('youtube.com') || url.toLowerCase().includes('youtu.be');

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      if (tab === 'file') {
        if (!selectedFile) {
          setError('Please select a document file to upload.');
          return;
        }
        await onUploadFile(selectedFile, title.trim() || undefined);
      } else {
        if (!url.trim()) {
          setError('Please enter a valid website URL or YouTube link.');
          return;
        }
        await onIngestUrl(url.trim(), title.trim() || undefined);
      }
      onClose();
      // Reset form
      setSelectedFile(null);
      setUrl('');
      setTitle('');
    } catch (err: any) {
      setError(err.message || 'Ingestion request failed.');
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '1rem'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isLoading) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '540px',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-dropdown)',
          border: '1px solid var(--border-color)',
          overflow: 'hidden'
        }}
        className="animate-fade-in"
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Add Knowledge Sources
            </h2>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Upload files or connect remote URLs to ingest into the vector index.
            </p>
          </div>

          <button
            onClick={onClose}
            disabled={isLoading}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Selector */}
        <div style={{ padding: '1rem 1.5rem 0.5rem 1.5rem', display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={() => { setTab('file'); setError(null); }}
            style={{
              flex: 1,
              padding: '0.5rem',
              borderRadius: '8px',
              border: tab === 'file' ? '1px solid var(--brand-blue)' : '1px solid var(--border-color)',
              backgroundColor: tab === 'file' ? 'var(--bg-active-nav)' : 'var(--bg-surface)',
              color: tab === 'file' ? 'var(--brand-blue)' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.8125rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.375rem'
            }}
          >
            <Upload size={15} />
            <span>Document File</span>
          </button>

          <button
            type="button"
            onClick={() => { setTab('url'); setError(null); }}
            style={{
              flex: 1,
              padding: '0.5rem',
              borderRadius: '8px',
              border: tab === 'url' ? '1px solid var(--brand-blue)' : '1px solid var(--border-color)',
              backgroundColor: tab === 'url' ? 'var(--bg-active-nav)' : 'var(--bg-surface)',
              color: tab === 'url' ? 'var(--brand-blue)' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.8125rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.375rem'
            }}
          >
            <Globe size={15} />
            <span>Web URL / YouTube</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '1rem 1.5rem 1.5rem 1.5rem' }}>
          {error && (
            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '8px',
                padding: '0.625rem 0.875rem',
                color: 'var(--danger)',
                fontSize: '0.8125rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '1rem'
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Optional Title Input */}
          <div style={{ marginBottom: '1rem' }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '0.375rem'
              }}
            >
              Document Title (Optional)
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Attendance Policy 2026, Employee Guidelines"
              disabled={isLoading}
              style={{
                width: '100%',
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-surface)',
                color: 'var(--text-primary)',
                fontSize: '0.875rem',
                outline: 'none'
              }}
            />
          </div>

          {tab === 'file' ? (
            /* File Drag & Drop Zone */
            <div style={{ marginBottom: '1.25rem' }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />

              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? 'var(--brand-blue)' : 'var(--border-color)'}`,
                  backgroundColor: dragOver ? 'var(--bg-active-nav)' : 'var(--bg-surface-subtle)',
                  borderRadius: '10px',
                  padding: '2rem 1.5rem',
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--bg-surface)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 0.75rem auto',
                    boxShadow: 'var(--shadow-subtle)',
                    color: 'var(--brand-blue)'
                  }}
                >
                  <Upload size={20} />
                </div>

                {selectedFile ? (
                  <div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {selectedFile.name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB · Ready to upload
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Click to browse or drop file here
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Supports PDF, DOCX, TXT, MD, CSV, XLSX (Up to 50MB)
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Remote URL Input */
            <div style={{ marginBottom: '1.25rem' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: 'var(--text-secondary)',
                  marginBottom: '0.375rem'
                }}
              >
                Website or YouTube URL
              </label>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color)',
                  backgroundColor: 'var(--bg-surface)'
                }}
              >
                {isYouTube ? (
                  <Video size={16} style={{ color: '#ef4444' }} />
                ) : (
                  <Globe size={16} style={{ color: 'var(--text-muted)' }} />
                )}
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/docs or https://youtube.com/watch?v=..."
                  disabled={isLoading}
                  style={{
                    width: '100%',
                    border: 'none',
                    outline: 'none',
                    backgroundColor: 'transparent',
                    color: 'var(--text-primary)',
                    fontSize: '0.875rem'
                  }}
                />
              </div>

              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                {isYouTube
                  ? 'YouTube detected: audio transcripts will be synchronized with second-level timestamps.'
                  : 'Webpage: clean content will be extracted without navigation headers or ads.'}
              </div>
            </div>
          )}

          {/* Submit Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="gw-btn-secondary"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isLoading || (tab === 'file' ? !selectedFile : !url.trim())}
              className="gw-btn-primary"
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Submitting Job...</span>
                </>
              ) : (
                <span>Start Ingestion</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
