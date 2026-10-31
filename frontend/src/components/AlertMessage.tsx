import React from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';
import './AlertMessage.css';

interface AlertMessageProps {
  type?: 'info' | 'success' | 'error';
  message: string;
  onDismiss?: () => void;
}

export const AlertMessage: React.FC<AlertMessageProps> = ({
  type = 'info',
  message,
  onDismiss,
}) => {
  if (!message) return null;

  return (
    <div className={`alert-banner alert-${type}`} role="alert">
      <div className="alert-content">
        {type === 'error' && <AlertCircle size={18} className="alert-icon" />}
        {type === 'success' && <CheckCircle2 size={18} className="alert-icon" />}
        {type === 'info' && <Info size={18} className="alert-icon" />}
        <span className="alert-text">{message}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          className="alert-dismiss"
          onClick={onDismiss}
          aria-label="Dismiss message"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
};
