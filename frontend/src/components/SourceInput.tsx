import React, { useState, useRef } from 'react';
import { Globe, Video, Plus, Loader2, Upload, FileText } from 'lucide-react';

interface SourceInputProps {
  onIngestUrl: (url: string) => Promise<void>;
  onUploadFile: (file: File) => Promise<void>;
  isLoading: boolean;
}

export const SourceInput: React.FC<SourceInputProps> = ({ onIngestUrl, onUploadFile, isLoading }) => {
  const [tab, setTab] = useState<'file' | 'url'>('file');
  const [url, setUrl] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isYouTube = url.toLowerCase().includes('youtube.com') || url.toLowerCase().includes('youtu.be');

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setError(null);
    try {
      await onIngestUrl(url.trim());
      setUrl('');
    } catch (err: any) {
      setError(err.message || 'Failed to ingest URL');
    }
  };

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    setError(null);
    try {
      await onUploadFile(file);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
      {/* Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.875rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={() => setTab('file')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.8125rem',
              fontWeight: tab === 'file' ? '600' : '400',
              background: tab === 'file' ? 'var(--accent-primary)' : 'transparent',
              color: tab === 'file' ? '#ffffff' : 'var(--text-secondary)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Upload size={13} />
            <span>Upload File</span>
          </button>

          <button
            type="button"
            onClick={() => setTab('url')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.8125rem',
              fontWeight: tab === 'url' ? '600' : '400',
              background: tab === 'url' ? 'var(--accent-primary)' : 'transparent',
              color: tab === 'url' ? '#ffffff' : 'var(--text-secondary)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Globe size={13} />
            <span>URL / YouTube</span>
          </button>
        </div>

        <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
          {tab === 'file' ? 'PDF • DOCX • TXT • MD • CSV • XLSX' : 'Webpage • YouTube'}
        </span>
      </div>

      {tab === 'file' ? (
        <div>
          <input
            type="file"
            ref={fileInputRef}
            onChange={(e) => handleFileSelect(e.target.files)}
            style={{ display: 'none' }}
            accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx"
          />

          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFileSelect(e.dataTransfer.files);
            }}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragOver ? 'var(--accent-primary)' : 'var(--border-color)'}`,
              borderRadius: '10px',
              padding: '1.25rem',
              textAlign: 'center',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              background: dragOver ? 'rgba(99, 102, 241, 0.05)' : 'var(--bg-input)',
              transition: 'all 0.2s ease'
            }}
          >
            {isLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Processing & indexing document...</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.375rem' }}>
                <FileText size={24} style={{ color: 'var(--accent-primary)', opacity: 0.8 }} />
                <p style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                  Drag & drop your document here, or <span style={{ color: 'var(--accent-primary)' }}>browse</span>
                </p>
                <p style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                  Supports PDF (with page metadata), DOCX, TXT, Markdown, CSV & XLSX
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <form onSubmit={handleUrlSubmit} style={{ display: 'flex', gap: '0.75rem' }}>
          <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center' }}>
            <div style={{ position: 'absolute', left: '0.875rem', color: isYouTube ? '#ef4444' : 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>
              {isYouTube ? <Video size={18} /> : <Globe size={18} />}
            </div>
            <input
              type="url"
              className="input-field"
              style={{ paddingLeft: '2.5rem' }}
              placeholder="Paste URL (e.g. https://example.com/docs or https://youtube.com/watch?v=...)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isLoading}
              required
            />
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={isLoading || !url.trim()}
            style={{ opacity: isLoading || !url.trim() ? 0.7 : 1 }}
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>{isYouTube ? 'Processing YouTube video...' : 'Ingesting...'}</span>
              </>
            ) : (
              <>
                <Plus size={16} />
                <span>Add Source</span>
              </>
            )}
          </button>
        </form>
      )}

      {error && (
        <div style={{
          marginTop: '0.75rem',
          padding: '0.625rem 0.875rem',
          borderRadius: '8px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          color: '#f87171',
          fontSize: '0.8125rem'
        }}>
          {error}
        </div>
      )}
    </div>
  );
};
