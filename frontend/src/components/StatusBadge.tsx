import React from 'react';
import type { DocumentStatus } from '../types/document';
import './StatusBadge.css';

interface StatusBadgeProps {
  status: DocumentStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  let label = status as string;
  if (status === 'uploaded') label = 'Uploaded';
  else if (status === 'processing') label = 'Indexing';
  else if (status === 'ready') label = 'Ready';
  else if (status === 'failed') label = 'Failed';

  return (
    <span className={`status-badge status-${status}`} role="status">
      <span className="status-dot" aria-hidden="true" />
      {label}
    </span>
  );
};
