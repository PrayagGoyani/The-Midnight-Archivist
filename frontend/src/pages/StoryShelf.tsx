import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BookOpen, Feather, Trash2, Search, ArrowRight, GitBranch } from 'lucide-react';
import { Button } from '../components/Button';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { AlertMessage } from '../components/AlertMessage';
import { EmptyState } from '../components/EmptyState';
import type { StoryOut } from '../types/story';
import { deleteStory, listStories } from '../services/storiesApi';
import './StoryShelf.css';

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

export default function StoryShelf() {
  const navigate = useNavigate();
  const [allStories, setAllStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');

  // Alerts
  const [alertInfo, setAlertInfo] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  // Deletion modal
  const [deleteTarget, setDeleteTarget] = useState<StoryOut | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchShelf = useCallback(async () => {
    try {
      const res = await listStories();
      setAllStories(res.stories);
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: err.message || 'Failed to retrieve manuscripts from shelf.',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchShelf();
  }, [fetchShelf]);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);

    try {
      await deleteStory(deleteTarget.id);
      setAlertInfo({
        type: 'success',
        message: `Manuscript "${deleteTarget.title}" was removed from the shelf.`,
      });
      setDeleteTarget(null);
      await fetchShelf();
    } catch (err: any) {
      setAlertInfo({
        type: 'error',
        message: err.message || 'Failed to delete manuscript.',
      });
    } finally {
      setDeleting(false);
    }
  };

  // Group root stories (stories without parent) and compute child branch counts
  const rootStories = allStories.filter((s) => !s.parent_story_id);

  // Map to count children for any story
  const childCounts = allStories.reduce((acc, story) => {
    if (story.parent_story_id) {
      acc[story.parent_story_id] = (acc[story.parent_story_id] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);

  const filteredStories = rootStories.filter((story) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return (
      story.title.toLowerCase().includes(q) ||
      story.premise.toLowerCase().includes(q) ||
      story.atmosphere.toLowerCase().includes(q)
    );
  });

  return (
    <section className="shelf-page">
      <header className="shelf-header">
        <div>
          <h1 className="shelf-title">The Story Shelf</h1>
          <p className="shelf-subtitle">
            Catalog of generated manuscripts, branching folios, and historical fiction.
          </p>
        </div>
        <Link to="/write">
          <Button variant="primary">
            <Feather size={16} />
            Draft New Story
          </Button>
        </Link>
      </header>

      {alertInfo && (
        <AlertMessage
          type={alertInfo.type}
          message={alertInfo.message}
          onDismiss={() => setAlertInfo(null)}
        />
      )}

      {rootStories.length > 0 && (
        <div className="shelf-search-bar">
          <input
            type="search"
            className="shelf-search-input"
            placeholder="Search manuscripts by title, premise, or tone..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            aria-label="Filter manuscripts"
          />
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
          <span className="spinner" aria-hidden="true" />
          <p style={{ color: 'var(--color-secondary-text)', marginTop: 'var(--space-2)' }}>
            Retrieving manuscripts from the shelf...
          </p>
        </div>
      ) : rootStories.length === 0 ? (
        <EmptyState
          icon={<BookOpen size={40} />}
          title="The Story Shelf is bare"
          description="You haven't written any manuscripts yet. Visit the Writing Desk to commence your first atmospheric tale."
          action={
            <Link to="/write">
              <Button variant="primary">
                <Feather size={16} />
                Draft Your First Story
              </Button>
            </Link>
          }
        />
      ) : filteredStories.length === 0 ? (
        <EmptyState
          icon={<Search size={32} />}
          title="No matching manuscripts found"
          description={`No stories match "${searchFilter}". Try adjusting your search query.`}
        />
      ) : (
        <div className="shelf-grid">
          {filteredStories.map((story) => {
            const branchesCount = childCounts[story.id] || 0;
            return (
              <article key={story.id} className="story-card">
                <div className="story-card-top">
                  <div className="story-card-badges">
                    <span className="badge-atmosphere">{story.atmosphere}</span>
                    <span className="badge-grounding">
                      {story.grounding_mode === 'archive' ? 'Archive-Grounded' : 'Freeform'}
                    </span>
                    {branchesCount > 0 && (
                      <span
                        className="badge-atmosphere"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        <GitBranch size={12} />
                        {branchesCount} {branchesCount === 1 ? 'branch' : 'branches'}
                      </span>
                    )}
                  </div>

                  <h2 className="story-card-title">{story.title}</h2>
                  <p className="story-card-premise">"{story.premise}"</p>
                </div>

                <div>
                  <div className="story-card-meta">
                    <span>{story.word_count || 0} words</span>
                    <span>{formatDate(story.created_at)}</span>
                  </div>

                  <div className="story-card-actions">
                    <button
                      type="button"
                      className="action-icon-btn danger"
                      onClick={() => setDeleteTarget(story)}
                      title="Delete manuscript"
                      aria-label={`Delete manuscript ${story.title}`}
                    >
                      <Trash2 size={14} />
                    </button>

                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => navigate(`/read/${story.id}`)}
                    >
                      Read Folio
                      <ArrowRight size={14} />
                    </Button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        title="Delete Manuscript"
        message={
          deleteTarget
            ? `Are you sure you wish to delete "${deleteTarget.title}"? The manuscript and its chapters will be removed from your shelf.`
            : ''
        }
        confirmLabel="Delete Manuscript"
        cancelLabel="Keep Manuscript"
        variant="danger"
        loading={deleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
}
