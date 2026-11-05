import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: ReactNode;
  variant?: 'default' | 'agri' | 'gold' | 'danger' | 'info';
  badge?: string;
}

export function StatCard({
  label,
  value,
  subtext,
  icon,
  variant = 'default',
  badge,
}: StatCardProps) {
  return (
    <div className={`stat-card ${variant}`}>
      <div className="stat-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="stat-label">{label}</span>
          {badge && <span className="system-tag">{badge}</span>}
        </div>
        <span className="stat-value">{value}</span>
        {subtext && <div className="stat-subtext">{subtext}</div>}
      </div>
      <div className="stat-icon-wrapper">{icon}</div>
    </div>
  );
}
