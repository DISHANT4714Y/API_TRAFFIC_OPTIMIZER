import React from 'react';

/**
 * In-memory recent request history table.
 * Capped at 15–20 recent requests executed during the active session.
 */
export default function RecentRequests({ requests = [] }) {
  return (
    <div className="card recent-requests-section" id="recent-requests-card">
      <div className="card-header">
        <span className="card-title">Recent Requests</span>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {requests.length} recorded session event{requests.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="table-wrap">
        {requests.length === 0 ? (
          <div className="empty-state">
            No requests executed yet in this session. Use the Request Simulator above to dispatch requests.
          </div>
        ) : (
          <table className="req-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Resource</th>
                <th>Result</th>
                <th>Source</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req, idx) => {
                const isHit = req.xCache === 'HIT';
                const isMiss = req.xCache === 'MISS';
                return (
                  <tr key={idx}>
                    <td className="req-time">{req.time}</td>
                    <td className="req-endpoint">/proxy/data/{req.resourceId}</td>
                    <td>
                      <span
                        className={`tag-status ${
                          req.status >= 200 && req.status < 300 ? 's-200' : 's-error'
                        }`}
                      >
                        {req.status}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`kpi-badge ${
                          isHit ? 'hit' : isMiss ? 'miss' : 'default'
                        }`}
                      >
                        {req.source}
                      </span>
                    </td>
                    <td className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {req.latencyMs} ms
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
