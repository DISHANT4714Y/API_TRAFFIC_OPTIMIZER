import React from 'react';

/**
 * Reusable KPI card for the 4-card grid
 */
export function KpiCard({ label, value, badge, badgeType = 'default', id }) {
  return (
    <div className="kpi-card" id={id}>
      <span className="kpi-label">{label}</span>
      <div className="kpi-value-row">
        <span className="kpi-value">{value ?? '—'}</span>
        {badge && (
          <span className={`kpi-badge ${badgeType}`}>{badge}</span>
        )}
      </div>
    </div>
  );
}

/**
 * Large highlight card for Optimization Metrics (Hit Ratio, Reduction)
 */
export function HighlightMetricCard({ title, description, value, variant = 'accent', id }) {
  return (
    <div className="metric-highlight-card" id={id}>
      <div className="metric-highlight-info">
        <span className="metric-highlight-title">{title}</span>
        <span className="metric-highlight-desc">{description}</span>
      </div>
      <div className={`metric-highlight-value ${variant}`}>
        {value ?? '0.0%'}
      </div>
    </div>
  );
}
