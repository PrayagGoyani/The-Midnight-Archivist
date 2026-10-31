import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Feather, BookOpen, Sparkles, AlertCircle } from 'lucide-react';
import { Button } from '../components/Button';
import { AlertMessage } from '../components/AlertMessage';
import type { DocumentOut } from '../types/document';
import type { GroundingMode, NarrativeLength } from '../types/story';
import { listDocuments } from '../services/documentsApi';
import { generateStory } from '../services/storiesApi';
import './WritingDesk.css';

const ATMOSPHERE_PRESETS = [
  'Gothic',
  'Melancholic Victorian',
  'Coastal Decay',
  'Surreal Folk Horror',
  'Cold War Bureaucracy',
  'Scholarly Obsession',
  'Midnight Train',
  'Sunken Library',
  'Custom...',
];

const LENGTH_OPTIONS: {
  id: NarrativeLength;
  label: string;
  range: string;
  desc: string;
}[] = [
  {
    id: 'short',
    label: 'Short',
    range: '400–600 words',
    desc: 'An evocative narrative fragment or sudden revelation.',
  },
  {
    id: 'medium',
    label: 'Medium',
    range: '800–1,200 words',
    desc: 'A full atmospheric chapter with rising suspense.',
  },
  {
    id: 'long',
    label: 'Long',
    range: '1,500–2,000 words',
    desc: 'An expansive short story with layered dialogue and depth.',
  },
];

export default function WritingDesk() {
  const navigate = useNavigate();

  // Form State
  const [premise, setPremise] = useState('');
  const [selectedAtmosphere, setSelectedAtmosphere] = useState('Gothic');
  const [customAtmosphere, setCustomAtmosphere] = useState('');
  const [length, setLength] = useState<NarrativeLength>('medium');
  const [groundingMode, setGroundingMode] = useState<GroundingMode>('freeform');
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [topK, setTopK] = useState(3);

  // Documents available for grounding
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Submission State
  const [generating, setGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoadingDocs(true);

    listDocuments()
      .then((res) => {
        if (isMounted) {
          const ready = res.documents.filter((d) => d.status === 'ready');
          setDocuments(ready);
          // Default select all ready documents if available
          setSelectedDocIds(ready.map((d) => d.id));
        }
      })
      .catch(() => {
        // Non-blocking; user can still write freeform
      })
      .finally(() => {
        if (isMounted) setLoadingDocs(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleDocCheckboxChange = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSelectAllDocs = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(documents.map((d) => d.id));
    }
  };

  const effectiveAtmosphere =
    selectedAtmosphere === 'Custom...'
      ? customAtmosphere.trim() || 'Gothic'
      : selectedAtmosphere;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!premise.trim()) {
      setErrorMessage('Please provide a narrative premise or opening circumstance.');
      return;
    }

    if (groundingMode === 'archive') {
      if (documents.length === 0) {
        setErrorMessage(
          'No ready documents found in the Archive. Please index documents first or switch to Freeform mode.'
        );
        return;
      }
      if (selectedDocIds.length === 0) {
        setErrorMessage(
          'Please select at least one indexed document to ground the story.'
        );
        return;
      }
    }

    setGenerating(true);
    setErrorMessage(null);
    setStatusMessage(
      groundingMode === 'archive'
        ? 'Retrieving relevant archival passages and drafting the opening chapter...'
        : 'Synthesizing the atmospheric world and drafting the opening chapter...'
    );

    try {
      const response = await generateStory({
        premise: premise.trim(),
        atmosphere: effectiveAtmosphere,
        length,
        grounding_mode: groundingMode,
        document_ids: groundingMode === 'archive' ? selectedDocIds : undefined,
        top_k: topK,
      });

      // Successful generation: immediately navigate to the Reading Room
      navigate(`/read/${response.id}`);
    } catch (err: any) {
      setErrorMessage(
        err.message ||
          'Story generation failed. Ensure the local Ollama instance is running.'
      );
    } finally {
      setGenerating(false);
      setStatusMessage(null);
    }
  };

  return (
    <section className="writing-desk-page">
      <header className="desk-header">
        <h1 className="desk-title">The Writing Desk</h1>
        <p className="desk-subtitle">
          Compose atmospheric narratives, drawing upon either pure creative invention or indexed archival records.
        </p>
      </header>

      {errorMessage && (
        <AlertMessage
          type="error"
          message={errorMessage}
          onDismiss={() => setErrorMessage(null)}
        />
      )}

      {statusMessage && (
        <div className="desk-loading-indicator" role="status">
          <span className="spinner" aria-hidden="true" />
          <span>{statusMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="desk-form" aria-label="Story generation form">
        {/* Premise */}
        <div className="form-group">
          <label htmlFor="premise-input" className="form-label">
            Narrative Premise & Inciting Incident
          </label>
          <textarea
            id="premise-input"
            className="premise-textarea"
            placeholder="A solitary cartographer arrives in a flooded coastal hamlet to record an island that officially sank sixty years ago..."
            value={premise}
            onChange={(e) => setPremise(e.target.value)}
            disabled={generating}
            required
            rows={4}
          />
          <span className="form-hint">
            Specify the protagonist, mystery, location, or opening tension.
          </span>
        </div>

        {/* Atmosphere & Length Row */}
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="atmosphere-select" className="form-label">
              Atmosphere & Tone
            </label>
            <select
              id="atmosphere-select"
              className="desk-select"
              value={selectedAtmosphere}
              onChange={(e) => setSelectedAtmosphere(e.target.value)}
              disabled={generating}
            >
              {ATMOSPHERE_PRESETS.map((preset) => (
                <option key={preset} value={preset}>
                  {preset}
                </option>
              ))}
            </select>
            {selectedAtmosphere === 'Custom...' && (
              <input
                type="text"
                className="desk-input"
                style={{ marginTop: 'var(--space-2)' }}
                placeholder="e.g. Victorian Séance, Saltwater Dread"
                value={customAtmosphere}
                onChange={(e) => setCustomAtmosphere(e.target.value)}
                disabled={generating}
                required
              />
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Grounding Mode</label>
            <div className="mode-toggle-grid">
              <button
                type="button"
                className={`radio-card ${groundingMode === 'freeform' ? 'selected' : ''}`}
                onClick={() => setGroundingMode('freeform')}
                disabled={generating}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Sparkles size={16} />
                  <span className="radio-card-title">Freeform</span>
                </div>
                <span className="radio-card-desc">
                  Pure narrative imagination unconstrained by documents.
                </span>
              </button>

              <button
                type="button"
                className={`radio-card ${groundingMode === 'archive' ? 'selected' : ''}`}
                onClick={() => setGroundingMode('archive')}
                disabled={generating}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <BookOpen size={16} />
                  <span className="radio-card-title">Archive-Grounded</span>
                </div>
                <span className="radio-card-desc">
                  Grounded in semantic passages retrieved from the archive.
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Archive Selection (Conditional) */}
        {groundingMode === 'archive' && (
          <div className="grounding-box">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span className="form-label">Select Archival Sources</span>
                <p className="form-hint">
                  The model will semantically retrieve and cite passages from selected documents.
                </p>
              </div>
              {documents.length > 0 && (
                <button
                  type="button"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-primary-accent)',
                    fontSize: '0.8125rem',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                  onClick={handleSelectAllDocs}
                >
                  {selectedDocIds.length === documents.length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>

            {loadingDocs ? (
              <p style={{ color: 'var(--color-secondary-text)', fontSize: '0.875rem' }}>
                Checking archive for indexed documents...
              </p>
            ) : documents.length === 0 ? (
              <div style={{ padding: 'var(--space-3)', background: '#fff', borderRadius: '4px' }}>
                <p style={{ color: 'var(--color-primary-accent)', margin: '0 0 var(--space-2) 0', fontSize: '0.875rem' }}>
                  <AlertCircle size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                  No indexed documents are available in the Archive.
                </p>
                <Link to="/archive" style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                  Go to Archive to deposit and index documents →
                </Link>
              </div>
            ) : (
              <div className="doc-checklist" role="group" aria-label="Available archival sources">
                {documents.map((doc) => (
                  <label key={doc.id} className="doc-check-item">
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(doc.id)}
                      onChange={() => handleDocCheckboxChange(doc.id)}
                      disabled={generating}
                    />
                    <span>
                      <strong>{doc.title}</strong>{' '}
                      <span style={{ color: 'var(--color-secondary-text)', fontSize: '0.75rem' }}>
                        ({doc.chunk_count || 0} chunks, {doc.file_extension.toUpperCase()})
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginTop: 'var(--space-2)' }}>
              <label htmlFor="topk-slider" style={{ fontSize: '0.8125rem', color: 'var(--color-secondary-text)' }}>
                Passages to retrieve per generation:
              </label>
              <select
                id="topk-slider"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                disabled={generating}
                style={{
                  padding: '2px 8px',
                  borderRadius: '3px',
                  border: '1px solid var(--color-border)',
                  background: '#fff',
                }}
              >
                <option value={2}>2 passages</option>
                <option value={3}>3 passages (Recommended)</option>
                <option value={5}>5 passages</option>
              </select>
            </div>
          </div>
        )}

        {/* Narrative Length Options */}
        <div className="form-group">
          <label className="form-label">Narrative Scope & Length</label>
          <div className="radio-card-grid">
            {LENGTH_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`radio-card ${length === opt.id ? 'selected' : ''}`}
                onClick={() => setLength(opt.id)}
                disabled={generating}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span className="radio-card-title">{opt.label}</span>
                  <span className="radio-card-target">{opt.range}</span>
                </div>
                <span className="radio-card-desc">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-3)' }}>
          <Button
            type="submit"
            variant="primary"
            loading={generating}
            disabled={!premise.trim()}
          >
            <Feather size={16} />
            Commence Story Generation
          </Button>
        </div>
      </form>
    </section>
  );
}
