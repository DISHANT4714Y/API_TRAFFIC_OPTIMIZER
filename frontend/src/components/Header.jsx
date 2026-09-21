import React, { useState } from 'react';

export default function Header({
  isOnline,
  onRefresh,
  isRefreshing,
  onReset,
  isResetting,
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  const handleConfirmReset = () => {
    setShowConfirm(false);
    onReset();
  };

  return (
    <>
      <header className="header">
        <div className="header-title-area">
          <div className="header-title-row">
            <h1 className="header-title">Intelligent API Traffic Optimizer</h1>
            <span className="header-badge">Phase 5 In-Memory Cache</span>
          </div>
          <p className="header-subtitle">
            Adaptive middleware for reducing redundant API traffic
          </p>
        </div>

        <div className="header-actions">
          <div className={`status-pill ${isOnline ? 'online' : 'offline'}`} id="backend-status-pill">
            <span className="status-dot"></span>
            <span>{isOnline ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE'}</span>
          </div>

          <button
            className="btn btn-secondary"
            onClick={onRefresh}
            disabled={isRefreshing}
            id="btn-refresh"
            title="Refresh statistics from backend"
          >
            {isRefreshing ? <span className="spinner"></span> : null}
            <span>{isRefreshing ? 'Refreshing...' : 'REFRESH'}</span>
          </button>

          <button
            className="btn btn-danger"
            onClick={() => setShowConfirm(true)}
            disabled={isResetting || !isOnline}
            id="btn-reset-experiment"
            title="Flush cache and reset experiment metrics"
          >
            {isResetting ? <span className="spinner"></span> : null}
            <span>{isResetting ? 'Resetting...' : 'RESET EXPERIMENT'}</span>
          </button>
        </div>
      </header>

      {showConfirm && (
        <div className="modal-overlay" onClick={() => setShowConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">Reset Experiment Confirmation</h2>
            <p className="modal-body">
              Reset all current experiment statistics and clear the in-memory cache?
              This will return request counters and stored entries to zero.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleConfirmReset}
                id="btn-confirm-reset"
              >
                Yes, Reset Experiment
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
