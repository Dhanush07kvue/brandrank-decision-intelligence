import React from 'react';

type BadgeVariant = 
  | 'critical' 
  | 'high' 
  | 'medium' 
  | 'low' 
  | 'verified' 
  | 'experimental' 
  | 'blocked' 
  | 'provisional';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'medium', className = '', children, ...props }) => {
  return (
    <span className={`badge badge-${variant.toLowerCase()} ${className}`} {...props}>
      {children}
    </span>
  );
};
