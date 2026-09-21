import React, { useState } from 'react';

export default function RequestSimulator({
  onSendRequest,
  isLoading,
  lastResponse,
  isOnline,
}) {
  const [resourceId, setResourceId] = useState('weather-ahmedabad');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!resourceId.trim() || isLoading) return;
    onSendRequest(resourceId.trim());
  };

  const handleChipClick = (presetId) => {
    setResourceId(presetId);
    if (!isLoading) {
      onSendRequest(presetId);
    }
  };

  return (
    <div className="card" id="request-simulator-card">
      <div className="card-header">
        <span className="card-title">Request Simulator</span>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Real Live Request to /proxy/data/:id
        </span>
      </div>

      <form className="simulator-form" onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="resource-input" className="input-label">
            Target Resource ID
          </label>
          <div className="input-row">
            <input
              id="resource-input"
              type="text"
              className="text-input"
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              placeholder="e.g. weather-ahmedabad"
              disabled={isLoading || !isOnline}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading || !resourceId.trim() || !isOnline}
              id="btn-send-request"
            >
              {isLoading ? <span className="spinner"></span> : null}
              <span>{isLoading ? 'Sending request...' : 'SEND REQUEST'}</span>
            </button>
          </div>
        </div>

        <div className="chips-row">
          <span className="chip-label">Quick Presets:</span>
          {['weather-ahmedabad', 'weather-delhi', 'weather-mumbai'].map((preset) => (
            <button
              key={preset}
              type="button"
              className="chip"
              onClick={() => handleChipClick(preset)}
              disabled={isLoading || !isOnline}
            >
              {preset}
            </button>
          ))}
        </div>
      </form>

      {/* Response Preview */}
      {lastResponse && (
        <div className="response-container" id="response-preview">
          <div className="response-header">
            <div className="response-meta">
              <span
                className={`tag-status ${
                  lastResponse.status >= 200 && lastResponse.status < 300
                    ? 's-200'
                    : 's-error'
                }`}
              >
                Status: {lastResponse.status || 'ERROR'}
              </span>

              {lastResponse.xCache === 'HIT' ? (
                <span className="tag-cache-hit">● CACHE HIT</span>
              ) : lastResponse.xCache === 'MISS' ? (
                <span className="tag-cache-miss">● CACHE MISS → EXTERNAL API</span>
              ) : (
                <span className="kpi-badge default">● {lastResponse.xCache}</span>
              )}

              <span className="latency-badge">
                Latency: <strong>{lastResponse.latencyMs} ms</strong>
              </span>
            </div>

            {lastResponse.mockDelay && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Upstream Delay: {lastResponse.mockDelay}ms
              </span>
            )}
          </div>

          <pre className="response-body">
            {JSON.stringify(lastResponse.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
