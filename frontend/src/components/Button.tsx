import React from 'react';
import './Button.css';

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  loading?: boolean;
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading,
  children,
  disabled,
  className = '',
  ...rest
}) => {
  const combinedClass = `btn btn-${variant} btn-${size} ${loading ? 'loading' : ''} ${className}`.trim();
  return (
    <button className={combinedClass} disabled={disabled || loading} {...rest}>
      {loading ? <span className="spinner" aria-hidden="true" /> : children}
    </button>
  );
};

