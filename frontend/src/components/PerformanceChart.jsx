import React from 'react';

/**
 * Performance Chart: Cache Hits vs Cache Misses
 * Built with clean, accessible SVG/CSS without heavy charting libraries.
 * Driven strictly by real backend stats.
 */
export default function PerformanceChart({ hits = 0, misses = 0 }) {
  const total = hits + misses;
  const maxVal = Math.max(hits, misses, 1);

  // Calculate proportional bar heights (percentage of available 100px height, min 6%)
  const hitHeightPct = total === 0 ? 0 : Math.max(Math.round((hits / maxVal) * 100), 6);
  const missHeightPct = total === 0 ? 0 : Math.max(Math.round((misses / maxVal) * 100), 6);

  const hitRatio = total > 0 ? ((hits / total) * 100).toFixed(1) : '0.0';

  return (
    <div className="card" id="performance-chart-card">
      <div className="card-header">
        <span className="card-title">Cache Performance Comparison</span>
        <span className="kpi-badge hit">{hitRatio}% Hits</span>
      </div>

      <div className="chart-container">
        <div className="chart-bars-wrap">
          {/* HIT Bar */}
          <div className="chart-bar-group">
            <span className="chart-bar-count">{hits}</span>
            <div
              className="chart-bar hit"
              style={{ height: `${hitHeightPct}%` }}
              title={`Cache Hits: ${hits}`}
            ></div>
          </div>

          {/* MISS Bar */}
          <div className="chart-bar-group">
            <span className="chart-bar-count">{misses}</span>
            <div
              className="chart-bar miss"
              style={{ height: `${missHeightPct}%` }}
              title={`Cache Misses: ${misses}`}
            ></div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '24px', padding: '0 20px' }}>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <span className="chart-bar-label" style={{ color: 'var(--success)' }}>
              ● CACHE HITS
            </span>
          </div>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <span className="chart-bar-label" style={{ color: 'var(--warning)' }}>
              ● CACHE MISSES
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
