import React from 'react';
import { ExternalLink, Video, FileText, Globe, Clock } from 'lucide-react';
import { Citation } from '../types';

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation, index }) => {
  const getIcon = () => {
    switch (citation.source_type) {
      case 'youtube':
        return <Video size={14} style={{ color: '#ef4444' }} />;
      case 'pdf':
        return <FileText size={14} style={{ color: '#3b82f6' }} />;
      default:
        return <Globe size={14} style={{ color: '#10b981' }} />;
    }
  };

  return (
    <div className="glass-panel" style={{
      padding: '0.75rem 1rem',
      borderRadius: '8px',
      fontSize: '0.8125rem',
      border: '1px solid var(--border-color)',
      background: 'rgba(255, 255, 255, 0.02)',
      marginTop: '0.5rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: '600', color: 'var(--text-primary)' }}>
          <span style={{
            fontSize: '0.6875rem',
            padding: '1px 6px',
            borderRadius: '4px',
            background: 'var(--badge-bg)',
            color: 'var(--badge-text)',
            fontWeight: '700'
          }}>
            [Source {index + 1}]
          </span>
          {getIcon()}
          <span style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {citation.source_title}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {citation.timestamp_str && (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.6875rem',
              color: '#f87171',
              background: 'rgba(239, 68, 68, 0.1)',
              padding: '1px 6px',
              borderRadius: '4px'
            }}>
              <Clock size={11} />
              {citation.timestamp_str}
            </span>
          )}

          {citation.page_number && (
            <span style={{
              fontSize: '0.6875rem',
              color: '#60a5fa',
              background: 'rgba(59, 130, 246, 0.1)',
              padding: '1px 6px',
              borderRadius: '4px'
            }}>
              Page {citation.page_number}
            </span>
          )}

          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
              title="Open source URL"
            >
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      </div>

      <p style={{
        color: 'var(--text-secondary)',
        fontSize: '0.75rem',
        lineHeight: '1.4',
        borderLeft: '2px solid var(--accent-primary)',
        paddingLeft: '0.5rem',
        marginTop: '0.375rem'
      }}>
        "{citation.snippet}"
      </p>
    </div>
  );
};
