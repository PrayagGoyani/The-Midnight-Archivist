import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Download,
  Printer,
  ChevronRight,
  GitBranch,
  BookOpen,
  ArrowLeft,
  FileText,
} from 'lucide-react';
import { Button } from '../components/Button';
import { AlertMessage } from '../components/AlertMessage';
import { EmptyState } from '../components/EmptyState';
import type {
  FullStoryNarrativeResponse,
  StoryBranchesResponse,
} from '../types/story';
import {
  continueStory,
  getFullNarrative,
  getStoryBranches,
  listStories,
} from '../services/storiesApi';
import './ReadingRoom.css';

export default function ReadingRoom() {
  const { storyId } = useParams<{ storyId?: string }>();
  const navigate = useNavigate();

  const [narrative, setNarrative] = useState<FullStoryNarrativeResponse | null>(null);
  const [branches, setBranches] = useState<StoryBranchesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [continuing, setContinuing] = useState(false);
  const [activeChoiceId, setActiveChoiceId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showBranchesDrawer, setShowBranchesDrawer] = useState(false);

  // If no storyId in URL, attempt to load the most recent story
  useEffect(() => {
    let isMounted = true;

    if (!storyId) {
      setLoading(true);
      listStories()
        .then((res) => {
          if (isMounted) {
            if (res.stories.length > 0) {
              navigate(`/read/${res.stories[0].id}`, { replace: true });
            } else {
              setLoading(false);
            }
          }
        })
        .catch(() => {
          if (isMounted) setLoading(false);
        });
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    Promise.all([
      getFullNarrative(storyId),
      getStoryBranches(storyId).catch(() => null),
    ])
      .then(([narrativeData, branchData]) => {
        if (isMounted) {
          setNarrative(narrativeData);
          setBranches(branchData);
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          setErrorMessage(err.message || 'Failed to retrieve story narrative.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [storyId, navigate]);

  const handleBranchSelect = async (choiceId: string) => {
    if (!storyId || continuing) return;

    setContinuing(true);
    setActiveChoiceId(choiceId);
    setErrorMessage(null);

    try {
      const continuation = await continueStory(storyId, { choice_id: choiceId });
      // Navigate to the newly created continuation leaf
      navigate(`/read/${continuation.id}`);
    } catch (err: any) {
      setErrorMessage(
        err.message || 'Failed to continue narrative along the chosen branch.'
      );
    } finally {
      setContinuing(false);
      setActiveChoiceId(null);
    }
  };

  const exportMarkdown = () => {
    if (!narrative) return;
    let md = `# ${narrative.title}\n\n`;
    md += `*Premise:* ${narrative.premise}\n`;
    md += `*Atmosphere:* ${narrative.atmosphere}\n`;
    md += `*Grounding:* ${narrative.grounding_mode}\n`;
    md += `*Total Words:* ${narrative.total_word_count}\n\n`;
    md += `---\n\n`;

    narrative.segments.forEach((seg, idx) => {
      if (idx > 0 && seg.branch_label) {
        md += `## Branch: ${seg.branch_label}\n\n`;
      }
      md += `${seg.content}\n\n`;
    });

    if (narrative.source_references && narrative.source_references.length > 0) {
      md += `\n---\n\n### From the Archive (Grounding Material)\n\n`;
      narrative.source_references.forEach((src) => {
        const title = src.document_title || 'Archival Document';
        const page = src.page_number ? ` (Page ${src.page_number})` : '';
        const snippet = src.text || '';
        md += `> **${title}${page}**\n> "${snippet}"\n\n`;
      });
    }

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${narrative.title.replace(/[^a-zA-Z0-9_-]/g, '_')}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportPlainText = () => {
    if (!narrative) return;
    let txt = `${narrative.title.toUpperCase()}\n\n`;
    txt += `Premise: ${narrative.premise}\n`;
    txt += `Atmosphere: ${narrative.atmosphere}\n`;
    txt += `Total Words: ${narrative.total_word_count}\n\n`;
    txt += `========================================\n\n`;

    narrative.segments.forEach((seg, idx) => {
      if (idx > 0 && seg.branch_label) {
        txt += `\n[ BRANCH: ${seg.branch_label} ]\n\n`;
      }
      txt += `${seg.content}\n\n`;
    });

    const blob = new Blob([txt], { type: 'text/plain;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${narrative.title.replace(/[^a-zA-Z0-9_-]/g, '_')}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <section className="reading-room-page">
        <div style={{ textAlign: 'center', padding: 'var(--space-7)' }}>
          <span className="spinner" aria-hidden="true" />
          <p style={{ color: 'var(--color-secondary-text)', marginTop: 'var(--space-3)' }}>
            Retrieving narrative folio from the archive...
          </p>
        </div>
      </section>
    );
  }

  if (!storyId || !narrative) {
    return (
      <section className="reading-room-page">
        <div className="reader-container">
          <EmptyState
            icon={<BookOpen size={40} />}
            title="The Reading Room is quiet"
            description="No story is currently open. Select a manuscript from the Story Shelf or draft a new one at the Writing Desk."
            action={
              <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                <Link to="/write">
                  <Button variant="primary">Visit Writing Desk</Button>
                </Link>
                <Link to="/shelf">
                  <Button variant="secondary">Browse Story Shelf</Button>
                </Link>
              </div>
            }
          />
        </div>
      </section>
    );
  }

  return (
    <section className="reading-room-page">
      <div className="reader-container">
        {/* Top Controls Toolbar */}
        <header className="reader-toolbar" role="toolbar" aria-label="Reading controls">
          <div className="reader-toolbar-left">
            <Link to="/shelf" className="action-icon-btn" title="Back to Story Shelf">
              <ArrowLeft size={16} />
              <span style={{ fontSize: '0.8125rem', marginLeft: '4px' }}>Shelf</span>
            </Link>
            <span className="reader-meta-tag">
              {narrative.segments.length} {narrative.segments.length === 1 ? 'Chapter' : 'Chapters'}
            </span>
            <span className="reader-meta-tag">
              {narrative.total_word_count} Words
            </span>
            <span className="reader-meta-tag">
              {narrative.atmosphere}
            </span>
          </div>

          <div className="reader-toolbar-right">
            {branches && branches.child_branches.length > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowBranchesDrawer(!showBranchesDrawer)}
                title="View existing child branches"
              >
                <GitBranch size={14} />
                Branches ({branches.child_branches.length})
              </Button>
            )}

            <Button size="sm" variant="ghost" onClick={exportMarkdown} title="Download Markdown">
              <Download size={14} />
              MD
            </Button>

            <Button size="sm" variant="ghost" onClick={exportPlainText} title="Download Plain Text">
              <FileText size={14} />
              TXT
            </Button>

            <Button size="sm" variant="ghost" onClick={handlePrint} title="Print or save as PDF">
              <Printer size={14} />
              Print
            </Button>
          </div>
        </header>

        {errorMessage && (
          <AlertMessage
            type="error"
            message={errorMessage}
            onDismiss={() => setErrorMessage(null)}
          />
        )}

        {/* Existing child branches quick navigator */}
        {showBranchesDrawer && branches && branches.child_branches.length > 0 && (
          <aside className="branch-tree-box" aria-label="Alternative narrative branches">
            <div className="branch-tree-title">Alternative Continuations from this Chapter</div>
            <div className="branch-node-list">
              {branches.child_branches.map((child) => (
                <Link
                  key={child.story_id}
                  to={`/read/${child.story_id}`}
                  className="branch-node-item"
                >
                  <div>
                    <strong>{child.branch_label || child.title}</strong>
                    <div style={{ color: 'var(--color-secondary-text)', fontSize: '0.75rem' }}>
                      {child.preview}
                    </div>
                  </div>
                  <ChevronRight size={14} style={{ color: 'var(--color-primary-accent)' }} />
                </Link>
              ))}
            </div>
          </aside>
        )}

        {/* Story Title & Premise Header */}
        <div className="story-header">
          <h1 className="story-title">{narrative.title}</h1>
          <p className="story-premise">"{narrative.premise}"</p>
          <div className="story-attributes">
            <span>Atmosphere: {narrative.atmosphere}</span>
            <span>•</span>
            <span>Mode: {narrative.grounding_mode === 'archive' ? 'Archive-Grounded' : 'Freeform'}</span>
          </div>
        </div>

        {/* Chronological Narrative Segments */}
        <article className="prose-content" aria-label="Story narrative">
          {narrative.segments.map((segment, index) => {
            const paragraphs = segment.content
              .split(/\n\s*\n/)
              .map((p) => p.trim())
              .filter((p) => p.length > 0);

            return (
              <section key={segment.story_id} className="narrative-segment">
                {index > 0 && (
                  <div className="segment-divider" aria-hidden="true">
                    ❦
                  </div>
                )}

                {segment.branch_label && (
                  <header className="segment-header">
                    <h2 className="segment-title">Chapter {index + 1}</h2>
                    <span className="segment-branch-badge">
                      Choice: {segment.branch_label}
                    </span>
                  </header>
                )}

                <div className="segment-body">
                  {paragraphs.map((para, pIdx) => (
                    <p key={pIdx}>{para}</p>
                  ))}
                </div>
              </section>
            );
          })}
        </article>

        {/* Branch Choices / Continuation */}
        {narrative.available_choices && narrative.available_choices.length > 0 && (
          <section className="branch-choices-section" aria-label="Narrative paths">
            <h3 className="branch-section-title">Where does the narrative venture next?</h3>
            <p className="branch-section-desc">
              Select a path below to direct the next chapter.
            </p>

            <div className="branch-cards-grid">
              {narrative.available_choices.map((choice) => {
                const isThisLoading = continuing && activeChoiceId === choice.id;
                return (
                  <button
                    key={choice.id}
                    type="button"
                    className="branch-choice-card"
                    onClick={() => handleBranchSelect(choice.id)}
                    disabled={continuing}
                    aria-label={`Choose path: ${choice.label}`}
                  >
                    <div>
                      <div className="branch-choice-label">{choice.label}</div>
                      {choice.description && (
                        <div className="branch-choice-desc">{choice.description}</div>
                      )}
                    </div>
                    <div className="branch-choice-arrow">
                      {isThisLoading ? (
                        <span className="spinner" aria-hidden="true" />
                      ) : (
                        <ChevronRight size={20} />
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {/* From the Archive Appendix (Grounding Citations) */}
        {narrative.grounding_mode === 'archive' &&
          narrative.source_references &&
          narrative.source_references.length > 0 && (
            <footer className="archive-appendix" aria-label="Archival source references">
              <h3 className="appendix-title">From the Archive</h3>
              <p className="appendix-desc">
                The preceding narrative was grounded in the following excerpts retrieved from primary archival records:
              </p>
              <div className="appendix-sources-list">
                {narrative.source_references.map((src, sIdx) => (
                  <div key={sIdx} className="appendix-source-card">
                    <div className="appendix-source-doc">
                      {src.document_title || 'Archival Document'}
                      {src.page_number && ` • Page ${src.page_number}`}
                      {src.section && ` • ${src.section}`}
                    </div>
                    {src.text && (
                      <div className="appendix-source-snippet">"{src.text}"</div>
                    )}
                    {src.similarity_score !== undefined && (
                      <div className="appendix-source-meta">
                        Cosine similarity score: {Number(src.similarity_score).toFixed(3)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </footer>
          )}
      </div>
    </section>
  );
}
