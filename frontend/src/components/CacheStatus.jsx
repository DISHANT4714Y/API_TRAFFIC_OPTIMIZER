import React from 'react';

/**
 * Cache Status panel displaying real memory cache properties from /cache/stats.
 */
export default function CacheStatus({ stats, isOnline }) {
  const currentEntries = stats?.current_entries ?? 0;
  const hits = stats?.hits ?? 0;
  const misses = stats?.misses ?? 0;
  const hitRatioPct = stats?.hit_ratio !== undefined ? (stats.hit_ratio * 100).toFixed(1) + '%' : '0.0%';

  return (
    <div className="card" id="cache-status-card">
      <div className="card-header">
        <span className="card-title">Cache Status</span>
        <span
          className="kpi-badge hit"
          style={{
            background: isOnline ? 'var(--success-subtle)' : 'var(--error-subtle)',
            color: isOnline ? 'var(--success)' : 'var(--error)',
          }}
        >
          {isOnline ? 'ACTIVE' : 'DISCONNECTED'}
        </span>
      </div>

      <table className="cache-stats-table">
        <tbody>
          <tr>
            <td>Layer Status</td>
            <td style={{ color: isOnline ? 'var(--success)' : 'var(--error)' }}>
              {isOnline ? 'IN-MEMORY READY' : 'OFFLINE'}
            </td>
          </tr>
          <tr>
            <td>Stored Entries</td>
            <td id="cache-entries-count">{currentEntries}</td>
          </tr>
          <tr>
            <td>Cache Hits</td>
            <td style={{ color: 'var(--success)' }}>{hits}</td>
          </tr>
          <tr>
            <td>Cache Misses</td>
            <td style={{ color: 'var(--warning)' }}>{misses}</td>
          </tr>
          <tr>
            <td>Hit Ratio</td>
            <td>{hitRatioPct}</td>
          </tr>
          <tr>
            <td>Storage Mechanism</td>
            <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              Dict + SHA-256 Key
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
