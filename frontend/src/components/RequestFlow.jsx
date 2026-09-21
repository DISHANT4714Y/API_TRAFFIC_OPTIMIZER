import React from 'react';

/**
 * Visual architecture pipeline for demonstrating request flow to professors:
 * CLIENT → OPTIMIZER → NORMALIZER → CACHE → (HIT: Response | MISS: Mock API → Cache)
 */
export default function RequestFlow({ activeState = 'IDLE', lastLatency = null }) {
  const isHit = activeState === 'HIT';
  const isMiss = activeState === 'MISS';
  const isPending = activeState === 'PENDING';

  return (
    <section className="flow-section">
      <div className="flow-container">
        <div className="card-header">
          <span className="card-title">Request / Optimization Flow</span>
          {activeState !== 'IDLE' && (
            <span
              className={`kpi-badge ${isHit ? 'hit' : isMiss ? 'miss' : 'default'}`}
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {isPending
                ? 'PROCESSING...'
                : isHit
                ? `LAST PATH: CACHE HIT (${lastLatency}ms)`
                : `LAST PATH: CACHE MISS → UPSTREAM (${lastLatency}ms)`}
            </span>
          )}
        </div>

        <div className="flow-steps">
          {/* 1. Client */}
          <div className={`flow-node ${isPending || isHit || isMiss ? 'active-neutral' : ''}`}>
            <span className="flow-node-title">Client</span>
            <span className="flow-node-desc">Browser / App</span>
          </div>

          <div className={`flow-connector ${isHit ? 'active-hit' : isMiss ? 'active-miss' : ''}`}>
            →
          </div>

          {/* 2. Optimizer */}
          <div className={`flow-node ${isPending || isHit || isMiss ? 'active-neutral' : ''}`}>
            <span className="flow-node-title">Optimizer</span>
            <span className="flow-node-desc">Port 8000 Proxy</span>
          </div>

          <div className={`flow-connector ${isHit ? 'active-hit' : isMiss ? 'active-miss' : ''}`}>
            →
          </div>

          {/* 3. Normalizer */}
          <div className={`flow-node ${isPending || isHit || isMiss ? 'active-neutral' : ''}`}>
            <span className="flow-node-title">Normalizer</span>
            <span className="flow-node-desc">SHA-256 Key</span>
          </div>

          <div className={`flow-connector ${isHit ? 'active-hit' : isMiss ? 'active-miss' : ''}`}>
            →
          </div>

          {/* 4. In-Memory Cache */}
          <div
            className={`flow-node ${
              isHit ? 'active-hit' : isMiss ? 'active-miss' : isPending ? 'active-neutral' : ''
            }`}
          >
            <span className="flow-node-title">In-Memory Cache</span>
            <span className="flow-node-desc">Lookup & TTL</span>
          </div>
        </div>

        {/* Dual Branch Outcomes */}
        <div className="flow-branches">
          <div className={`flow-branch hit ${isHit ? 'active' : ''}`}>
            <span className="branch-badge hit">CACHE HIT</span>
            <span className="branch-desc">
              Entry found in memory. Served instantly without contacting upstream API (sub-5ms).
            </span>
          </div>

          <div className={`flow-branch miss ${isMiss ? 'active' : ''}`}>
            <span className="branch-badge miss">CACHE MISS</span>
            <span className="branch-desc">
              Not in cache. Forwards to Mock External API (Port 8001), captures response, and populates cache.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
