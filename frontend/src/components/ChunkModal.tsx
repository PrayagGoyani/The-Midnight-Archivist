import React, { useEffect, useState } from 'react';
import { X, Search } from 'lucide-react';
import type { ChunkOut, DocumentOut } from '../types/document';
import { getDocumentChunks } from '../services/documentsApi';
import './ChunkModal.css';

interface ChunkModalProps {
  document: DocumentOut | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ChunkModal: React.FC<ChunkModalProps> = ({
  document,
  isOpen,
  onClose,
}) => {
  const [chunks, setChunks] = useState<ChunkOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    if (!isOpen || !document) {
      setChunks([]);
      setError(null);
      setFilterText('');
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    getDocumentChunks(document.id)
      .then((res) => {
        if (isMounted) {
          setChunks(res.chunks);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load document chunks');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, document]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !document) return null;

  const filteredChunks = chunks.filter((c) =>
    filterText.trim() === ''
      ? true
      : c.text.toLowerCase().includes(filterText.toLowerCase()) ||
        (c.section && c.section.toLowerCase().includes(filterText.toLowerCase()))
  );

  return (
    <div className="chunk-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="chunk-modal-container"
        role="dialog"
        aria-modal="true"
        aria-labelledby="chunk-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="chunk-modal-header">
          <div>
            <h3 id="chunk-modal-title" className="chunk-modal-title">
              Archival Chunks: {document.title}
            </h3>
            <p className="chunk-modal-meta">
              <span>{document.original_filename}</span> •{' '}
              <span>{chunks.length} total chunks</span> •{' '}
              <span>Model: {document.embedding_model_used || 'None'}</span>
            </p>
          </div>
          <button
            className="chunk-modal-close"
            onClick={onClose}
            aria-label="Close chunk inspector"
          >
            <X size={20} />
          </button>
        </div>

        <div className="chunk-modal-search">
          <Search size={16} className="chunk-search-icon" />
          <input
            type="search"
            placeholder="Filter chunks by passage text..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="chunk-search-input"
            aria-label="Filter chunks by passage text"
          />
        </div>

        <div className="chunk-modal-body">
          {loading && (
            <div className="chunk-loading">
              <span className="spinner" aria-hidden="true" />
              <p>Examining archival fragments...</p>
            </div>
          )}

          {error && (
            <div className="chunk-error" role="alert">
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && filteredChunks.length === 0 && (
            <div className="chunk-empty">
              <p>
                {chunks.length === 0
                  ? 'No chunks available. Please process the document first.'
                  : 'No chunks match your filter.'}
              </p>
            </div>
          )}

          {!loading &&
            !error &&
            filteredChunks.map((chunk) => (
              <div key={chunk.id} className="chunk-card">
                <div className="chunk-card-meta">
                  <span className="chunk-index">Chunk #{chunk.chunk_index + 1}</span>
                  {chunk.page_number && (
                    <span className="chunk-page">Page {chunk.page_number}</span>
                  )}
                  {chunk.section && (
                    <span className="chunk-section">{chunk.section}</span>
                  )}
                </div>
                <div className="chunk-card-text">{chunk.text}</div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};
