import React, { useState } from 'react';
import { Globe, Video, Plus, Loader2 } from 'lucide-react';

interface SourceInputProps {
  onIngest: (url: string) => Promise<void>;
  isLoading: boolean;
}

export const SourceInput: React.FC<SourceInputProps> = ({ onIngest, isLoading }) => {
  const [url, setUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  const isYouTube = url.toLowerCase().includes('youtube.com') || url.toLowerCase().includes('youtu.be');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setError(null);
    try {
      await onIngest(url.trim());
      setUrl('');
    } catch (err: any) {
      setError(err.message || 'Failed to ingest URL');
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h2 style={{ fontSize: '0.9375rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>Add Knowledge Source</span>
        </h2>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Webpage • Article • YouTube Video
        </span>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.75rem' }}>
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
              <span>Ingesting...</span>
            </>
          ) : (
            <>
              <Plus size={16} />
              <span>Ingest Source</span>
            </>
          )}
        </button>
      </form>

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
