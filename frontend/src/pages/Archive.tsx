import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  FileText,
  UploadCloud,
  Trash2,
  RefreshCw,
  Search,
  Layers,
  BookOpen,
} from 'lucide-react';
import { Button } from '../components/Button';
import { StatusBadge } from '../components/StatusBadge';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ChunkModal } from '../components/ChunkModal';
import { AlertMessage } from '../components/AlertMessage';
import { EmptyState } from '../components/EmptyState';
import type { DocumentOut } from '../types/document';
import type { SearchResultItem } from '../types/search';
import {
  deleteDocument,
  listDocuments,
  processDocument,
  uploadDocument,
} from '../services/documentsApi';
import { performSearch } from '../services/searchApi';
import './Archive.css';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function formatFriendlyErrorMessage(rawError?: string | null): string {
  if (!rawError) return '';
  const lower = rawError.toLowerCase();
  if (
    lower.includes('10054') ||
    lower.includes('connection was forcibly closed') ||
    lower.includes('connection refused') ||
    lower.includes('cannot connect to ollama') ||
    lower.includes('connecterror') ||
    lower.includes('ollamaconnectionerror') ||
    lower.includes('failed to connect') ||
    lower.includes('network error')
  ) {
    return 'Indexing failed. Ollama connection was interrupted. Check that the local AI service is running and try again.';
  }
  if (lower.includes('model') && (lower.includes('not found') || lower.includes('pull'))) {
    return 'Indexing failed. Required embedding model was not found in Ollama. Pull nomic-embed-text and try again.';
  }
  if (lower.includes('timeout')) {
    return 'Indexing failed. Ollama embedding request timed out. Please try again.';
  }
  if (lower.includes('no extractable text') || lower.includes('empty')) {
    return 'No extractable text found in document. The file may be empty or contain scanned images without OCR.';
  }
  if (lower.includes('not found on disk')) {
    return 'Document file was not found on local storage.';
  }
  return rawError;
}

export default function Archive() {
  const [activeTab, setActiveTab] = useState<'documents' | 'search'>('documents');
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);

  // Alerts
  const [alertInfo, setAlertInfo] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  // Modals state
  const [deleteTarget, setDeleteTarget] = useState<DocumentOut | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [inspectTarget, setInspectTarget] = useState<DocumentOut | null>(null);

  // Drag and drop state
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searchExecuted, setSearchExecuted] = useState(false);
  const [selectedSearchDocId, setSelectedSearchDocId] = useState<string>('all');
  const [topK, setTopK] = useState<number>(5);

  const fetchDocs = useCallback(async () => {
    try {
      const res = await listDocuments();
      setDocuments(res.documents);
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: err.message || 'Failed to retrieve documents catalog.',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleFileUpload = async (file: File) => {
    const validExtensions = ['.pdf', '.txt', '.md', '.markdown'];
    const hasValidExt = validExtensions.some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    );

    if (!hasValidExt) {
      setAlertInfo({
        type: 'error',
        message: `Unsupported file type for "${file.name}". Please upload PDF, TXT, or Markdown documents.`,
      });
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setAlertInfo({
        type: 'error',
        message: `File "${file.name}" exceeds the 20MB limit.`,
      });
      return;
    }

    setUploading(true);
    setAlertInfo(null);

    try {
      const newDoc = await uploadDocument(file);
      setAlertInfo({
        type: 'success',
        message: `Document "${newDoc.title}" archived successfully. Click "Index Document" to generate embeddings.`,
      });
      await fetchDocs();
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: err.message || 'Failed to upload document.',
      });
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleProcess = async (doc: DocumentOut) => {
    setProcessingId(doc.id);
    setAlertInfo({
      type: 'info',
      message: `Extracting text and generating embeddings for "${doc.title}"...`,
    });

    try {
      const res = await processDocument(doc.id);
      setAlertInfo({
        type: 'success',
        message: `Indexed "${doc.title}" into ${res.chunk_count} semantic chunks using ${res.embedding_model}.`,
      });
      await fetchDocs();
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: `Indexing failed for "${doc.title}": ${err.message}`,
      });
      await fetchDocs();
    } finally {
      setProcessingId(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);

    try {
      await deleteDocument(deleteTarget.id);
      setAlertInfo({
        type: 'success',
        message: `Document "${deleteTarget.title}" and its indexed chunks were deleted.`,
      });
      setDeleteTarget(null);
      await fetchDocs();
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: err.message || 'Failed to delete document.',
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    setSearchExecuted(true);
    setAlertInfo(null);

    try {
      const docIds =
        selectedSearchDocId === 'all' ? undefined : [selectedSearchDocId];
      const res = await performSearch({
        query: searchQuery.trim(),
        document_ids: docIds,
        top_k: topK,
      });
      setSearchResults(res.results);
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: err.message || 'Semantic search failed.',
      });
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const readyDocuments = documents.filter((d) => d.status === 'ready');

  return (
    <section className="archive-page">
      <header className="archive-header">
        <h1 className="archive-title">The Archive</h1>
        <p className="archive-subtitle">
          Primary historical documents, transcripts, and records serving as grounding material.
        </p>
      </header>

      {alertInfo && (
        <AlertMessage
          type={alertInfo.type}
          message={alertInfo.message}
          onDismiss={() => setAlertInfo(null)}
        />
      )}

      <div className="archive-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === 'documents'}
          className={`archive-tab-btn ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          <FileText size={16} />
          Documents ({documents.length})
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'search'}
          className={`archive-tab-btn ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          <Search size={16} />
          Semantic Retrieval
        </button>
      </div>

      {activeTab === 'documents' && (
        <div className="archive-tab-content">
          {/* Upload Dropzone */}
          <div
            className={`dropzone-container ${dragActive ? 'drag-active' : ''}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload document dropzone"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click();
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              className="file-input-hidden"
              accept=".pdf,.txt,.md,.markdown,text/plain,application/pdf,text/markdown"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
            />
            <div className="dropzone-content">
              <UploadCloud size={32} className="dropzone-icon" />
              <h2 className="dropzone-title">
                {uploading ? 'Archiving Document...' : 'Deposit a Document into the Archive'}
              </h2>
              <p className="dropzone-hint">
                Drag and drop PDF, TXT, or Markdown files here, or click to browse (up to 20MB).
              </p>
            </div>
          </div>

          {/* Catalog list */}
          <div style={{ marginTop: 'var(--space-5)' }}>
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'var(--type-h2)',
                marginBottom: 'var(--space-3)',
              }}
            >
              Archived Documents
            </h2>

            {loading ? (
              <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                <span className="spinner" aria-hidden="true" />
                <p style={{ color: 'var(--color-secondary-text)', marginTop: 'var(--space-2)' }}>
                  Opening the catalog...
                </p>
              </div>
            ) : documents.length === 0 ? (
              <EmptyState
                icon={<BookOpen size={36} />}
                title="The Archive is currently empty"
                description="Upload research notes, public domain texts, historical letters, or records to ground your stories."
                action={
                  <Button
                    variant="primary"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Deposit First Document
                  </Button>
                }
              />
            ) : (
              <div className="documents-table-wrapper">
                <table className="documents-table" aria-label="Documents catalog">
                  <thead>
                    <tr>
                      <th scope="col">Title & Filename</th>
                      <th scope="col">Format</th>
                      <th scope="col">Size</th>
                      <th scope="col">Status</th>
                      <th scope="col">Chunks</th>
                      <th scope="col">Archived Date</th>
                      <th scope="col" style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => {
                      const isProcessingThis = processingId === doc.id;
                      return (
                        <tr key={doc.id}>
                          <td className="doc-title-cell">
                            <div className="doc-primary-title" title={doc.title}>
                              {doc.title}
                            </div>
                            <div className="doc-filename" title={doc.original_filename}>
                              {doc.original_filename}
                            </div>
                            {doc.error_message && (
                              <div
                                style={{
                                  color: 'var(--color-primary-accent)',
                                  fontSize: '0.75rem',
                                  marginTop: '4px',
                                  lineHeight: 1.3,
                                }}
                                title={`Diagnostic details: ${doc.error_message}`}
                              >
                                ⚠ {formatFriendlyErrorMessage(doc.error_message)}
                              </div>
                            )}
                            {doc.reindex_error && (
                              <div
                                style={{
                                  color: 'var(--color-primary-accent)',
                                  fontSize: '0.75rem',
                                  marginTop: '4px',
                                  lineHeight: 1.3,
                                }}
                                title={`Diagnostic details: ${doc.reindex_error}`}
                              >
                                ⚠ {formatFriendlyErrorMessage(doc.reindex_error)}
                              </div>
                            )}
                          </td>
                          <td style={{ textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                            {doc.file_extension}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>
                            {formatBytes(doc.file_size)}
                          </td>
                          <td>
                            <StatusBadge status={doc.status} />
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>
                            {doc.chunk_count !== null && doc.chunk_count !== undefined
                              ? doc.chunk_count
                              : '—'}
                          </td>
                          <td>{formatDate(doc.created_at)}</td>
                          <td>
                            <div className="doc-actions">
                              {/* Process / Re-index button */}
                              <Button
                                size="sm"
                                variant={doc.status === 'ready' ? 'ghost' : 'secondary'}
                                loading={isProcessingThis}
                                onClick={() => handleProcess(doc)}
                                title={
                                  doc.status === 'ready'
                                    ? 'Re-index document chunks and embeddings'
                                    : 'Extract text and generate embeddings'
                                }
                              >
                                <RefreshCw size={12} />
                                {doc.status === 'ready' ? 'Re-index' : 'Index'}
                              </Button>

                              {/* View Chunks button */}
                              {doc.status === 'ready' && (
                                <button
                                  type="button"
                                  className="action-icon-btn"
                                  onClick={() => setInspectTarget(doc)}
                                  title="Inspect indexed chunks"
                                  aria-label={`Inspect chunks for ${doc.title}`}
                                >
                                  <Layers size={14} />
                                </button>
                              )}

                              {/* Delete button */}
                              <button
                                type="button"
                                className="action-icon-btn danger"
                                onClick={() => setDeleteTarget(doc)}
                                title="Delete document from archive"
                                aria-label={`Delete document ${doc.title}`}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'search' && (
        <div className="search-section">
          <form onSubmit={handleSearchSubmit} className="search-box">
            <input
              type="text"
              className="search-input-field"
              placeholder="Enter a thematic question, motif, or phrase to search indexed records..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Semantic search query"
            />
            <Button
              type="submit"
              variant="primary"
              loading={searching}
              disabled={!searchQuery.trim()}
            >
              <Search size={16} />
              Retrieve Passages
            </Button>
          </form>

          <div className="search-filters">
            <div>
              <label htmlFor="search-doc-filter" style={{ marginRight: 'var(--space-2)' }}>
                Scope:
              </label>
              <select
                id="search-doc-filter"
                value={selectedSearchDocId}
                onChange={(e) => setSelectedSearchDocId(e.target.value)}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-primary-text)',
                }}
              >
                <option value="all">All Ready Documents ({readyDocuments.length})</option>
                {readyDocuments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="search-topk-filter" style={{ marginRight: 'var(--space-2)' }}>
                Results (Top K):
              </label>
              <select
                id="search-topk-filter"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-primary-text)',
                }}
              >
                <option value={3}>3 passages</option>
                <option value={5}>5 passages</option>
                <option value={10}>10 passages</option>
              </select>
            </div>
          </div>

          <div className="search-results-container">
            {searching && (
              <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                <span className="spinner" aria-hidden="true" />
                <p style={{ color: 'var(--color-secondary-text)', marginTop: 'var(--space-2)' }}>
                  Searching semantic embedding space...
                </p>
              </div>
            )}

            {!searching && searchExecuted && searchResults.length === 0 && (
              <EmptyState
                icon={<Search size={32} />}
                title="No matching passages found"
                description="Try broadening your query phrase or indexing additional documents into the archive."
              />
            )}

            {!searching && searchResults.length > 0 && (
              <div className="search-results-list">
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--color-secondary-text)' }}>
                  Found {searchResults.length} matching archival passages (sorted by cosine similarity):
                </p>
                {searchResults.map((result) => (
                  <div key={result.chunk_id} className="search-result-card">
                    <div className="search-result-header">
                      <span className="search-result-doc">{result.document_title}</span>
                      <span className="search-result-score">
                        Similarity: {result.similarity_score.toFixed(3)}
                      </span>
                    </div>
                    <div className="search-result-snippet">{result.text}</div>
                    <div className="search-result-meta">
                      {result.page_number && <span>Page {result.page_number}</span>}
                      {result.page_number && result.section && <span> • </span>}
                      {result.section && <span>{result.section}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Confirm Deletion Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        title="Delete Document"
        message={
          deleteTarget
            ? `Are you sure you wish to delete "${deleteTarget.title}"? All associated semantic chunks and indexed vectors will be permanently removed.`
            : ''
        }
        confirmLabel="Delete Document"
        cancelLabel="Keep Document"
        variant="danger"
        loading={deleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Chunk Inspector Modal */}
      <ChunkModal
        isOpen={Boolean(inspectTarget)}
        document={inspectTarget}
        onClose={() => setInspectTarget(null)}
      />
    </section>
  );
}
