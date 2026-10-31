import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  Database,
  Cpu,
  FolderArchive,
  CheckCircle2,
  AlertCircle,
  HardDrive,
  FileText,
} from 'lucide-react';
import { Button } from '../components/Button';
import { AlertMessage } from '../components/AlertMessage';
import type { SystemStatusResponse } from '../types/system';
import { getSystemStatus } from '../services/systemApi';
import './Settings.css';

export default function Settings() {
  const [statusData, setStatusData] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchStatus = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setErrorMessage(null);

    try {
      const data = await getSystemStatus();
      setStatusData(data);
    } catch (err: any) {
      setErrorMessage(
        err.message ||
          'Failed to reach backend API. Ensure the FastAPI server is running on port 8000.'
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return (
    <section className="settings-page">
      <header className="settings-header">
        <div>
          <h1 className="settings-title">System & Archive Status</h1>
          <p className="settings-subtitle">
            Live telemetry of SQLite persistence, local Ollama runtime, and archival storage.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => fetchStatus(true)}
          loading={refreshing}
          title="Re-test system connections and model presence"
        >
          <RefreshCw size={14} />
          Refresh Telemetry
        </Button>
      </header>

      {errorMessage && (
        <AlertMessage
          type="error"
          message={errorMessage}
          onDismiss={() => setErrorMessage(null)}
        />
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
          <span className="spinner" aria-hidden="true" />
          <p style={{ color: 'var(--color-secondary-text)', marginTop: 'var(--space-2)' }}>
            Polling local system telemetry...
          </p>
        </div>
      ) : !statusData ? (
        <div className="settings-card">
          <p style={{ color: 'var(--color-primary-accent)' }}>
            Unable to communicate with the local archivist daemon.
          </p>
        </div>
      ) : (
        <div className="settings-cards-list">
          {/* Overall Health Status Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h2 className="settings-card-title">
                {statusData.status === 'healthy' ? (
                  <CheckCircle2 size={20} style={{ color: 'var(--color-secondary-accent)' }} />
                ) : (
                  <AlertCircle size={20} style={{ color: 'var(--color-primary-accent)' }} />
                )}
                System Health: {statusData.status.toUpperCase()}
              </h2>
              <span
                className={`status-pill ${
                  statusData.status === 'healthy' ? 'online' : 'offline'
                }`}
              >
                {statusData.status === 'healthy' ? 'All Systems Nominal' : 'Degraded Runtime'}
              </span>
            </div>
            <div className="settings-grid">
              <div className="settings-field">
                <span className="settings-field-label">Archivist Version</span>
                <span className="settings-field-val">v{statusData.version}</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Environment</span>
                <span className="settings-field-val">Local Workstation</span>
              </div>
            </div>
          </div>

          {/* SQLite Database Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h2 className="settings-card-title">
                <Database size={18} />
                Relational Database (SQLite)
              </h2>
              <span
                className={`status-pill ${
                  statusData.database.status === 'connected' ? 'online' : 'offline'
                }`}
              >
                {statusData.database.status === 'connected' ? 'Connected' : 'Unavailable'}
              </span>
            </div>
            <div className="settings-grid">
              <div className="settings-field">
                <span className="settings-field-label">Database Engine</span>
                <span className="settings-field-val">SQLite 3 (Embedded)</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Storage Mode</span>
                <span className="settings-field-val">Local SQLite storage</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Persistence File</span>
                <span className="settings-field-val">Local Store (archivist.db)</span>
              </div>
            </div>
          </div>

          {/* Ollama Machine Intelligence Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h2 className="settings-card-title">
                <Cpu size={18} />
                Local AI Runtime (Ollama)
              </h2>
              <span
                className={`status-pill ${
                  statusData.ollama.status === 'connected' ? 'online' : 'offline'
                }`}
              >
                {statusData.ollama.status.toUpperCase()}
              </span>
            </div>

            <div className="settings-grid">
              <div className="settings-field">
                <span className="settings-field-label">Inference Mode</span>
                <span className="settings-field-val">Local Ollama inference</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Provider Isolation</span>
                <span className="settings-field-val">No external AI provider</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Base URL</span>
                <span className="settings-field-val">{statusData.ollama.base_url}</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Generation Model</span>
                <span className="settings-field-val">
                  {statusData.ollama.generation_model}{' '}
                  {statusData.ollama.generation_model_available ? (
                    <span style={{ color: 'var(--color-secondary-accent)' }}>[Available]</span>
                  ) : (
                    <span style={{ color: 'var(--color-primary-accent)' }}>[Missing]</span>
                  )}
                </span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Embedding Model</span>
                <span className="settings-field-val">
                  {statusData.ollama.embedding_model}{' '}
                  {statusData.ollama.embedding_model_available ? (
                    <span style={{ color: 'var(--color-secondary-accent)' }}>[Available]</span>
                  ) : (
                    <span style={{ color: 'var(--color-primary-accent)' }}>[Missing]</span>
                  )}
                </span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Detected Models</span>
                <span className="settings-field-val">
                  {statusData.ollama.available_models.length} installed
                </span>
              </div>
            </div>

            {statusData.ollama.available_models.length > 0 && (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <span className="settings-field-label">Installed Models:</span>
                <div className="models-tags-container">
                  {statusData.ollama.available_models.map((mod) => (
                    <span key={mod} className="model-tag">
                      {mod}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Diagnostic helper if Ollama is unreachable */}
            {statusData.ollama.status !== 'connected' && (
              <div style={{ marginTop: 'var(--space-3)' }}>
                <p style={{ color: 'var(--color-primary-accent)', fontSize: '0.875rem', margin: 0 }}>
                  Ollama is currently unreachable at {statusData.ollama.base_url}.
                </p>
                <div className="code-snippet">ollama serve</div>
              </div>
            )}
          </div>

          {/* Archival Storage Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h2 className="settings-card-title">
                <FolderArchive size={18} />
                Archival Storage & Metrics
              </h2>
              <span className="status-pill online">Active</span>
            </div>
            <div className="settings-grid">
              <div className="settings-field">
                <span className="settings-field-label">Ingestion Mode</span>
                <span className="settings-field-val">Local document storage</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Upload Storage Directory</span>
                <span className="settings-field-val">{statusData.storage.upload_dir}</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Max Ingestion Size</span>
                <span className="settings-field-val">{statusData.storage.max_upload_size_mb} MB</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Total Documents</span>
                <span className="settings-field-val">{statusData.storage.document_count}</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Semantic Chunks</span>
                <span className="settings-field-val">{statusData.storage.chunk_count}</span>
              </div>
              <div className="settings-field">
                <span className="settings-field-label">Generated Stories</span>
                <span className="settings-field-val">{statusData.storage.story_count}</span>
              </div>
            </div>
          </div>

          {/* Model Attribution & Licensing Card */}
          <div className="settings-card attribution-card">
            <div className="settings-card-header">
              <h2 className="settings-card-title">
                <FileText size={18} />
                Model Attribution & Licensing
              </h2>
              <span className="status-pill llama-attribution-pill">Built with Llama</span>
            </div>
            <p className="attribution-intro">
              The Midnight Archivist is an open-source, local-first application licensed under the MIT License.
              Neural inference runs entirely on your local workstation via Ollama using open-weight models.
            </p>
            <div className="attribution-list">
              <div className="attribution-item">
                <div className="attribution-row">
                  <span className="attribution-model-name">Meta Llama 3.2 3B (<code>llama3.2:3b</code>)</span>
                  <span className="attribution-license-badge">Meta Llama 3.2 Community License</span>
                </div>
                <p className="attribution-desc">
                  Story synthesis, multi-stage narrative generation, and branching continuations are <strong>Built with Llama</strong>. Llama 3.2 is an open-weight model licensed by Meta Platforms, Inc. under the{' '}
                  <a
                    href="https://llama.meta.com/llama3/license/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="editorial-link"
                  >
                    Meta Llama 3.2 Community License Agreement
                  </a>
                  .
                </p>
              </div>

              <div className="attribution-item">
                <div className="attribution-row">
                  <span className="attribution-model-name">Nomic Embed Text (<code>nomic-embed-text</code>)</span>
                  <span className="attribution-license-badge">Apache 2.0</span>
                </div>
                <p className="attribution-desc">
                  768-dimensional dense vector embeddings and semantic archival search are powered by Nomic AI's embedding model under the{' '}
                  <a
                    href="http://www.apache.org/licenses/LICENSE-2.0"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="editorial-link"
                  >
                    Apache License 2.0
                  </a>
                  .
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
