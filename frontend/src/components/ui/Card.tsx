import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
}

export const Card: React.FC<CardProps> = ({ glass = false, className = '', children, ...props }) => {
  const baseClass = glass ? 'glass-panel' : 'glass-card';
  return (
    <div className={`${baseClass} p-6 ${className}`} {...props}>
      {children}
    </div>
  );
};
