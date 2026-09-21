import React, { useState, useEffect, useCallback } from 'react';
import Header from '../components/Header';
import { KpiCard, HighlightMetricCard } from '../components/MetricCard';
import RequestFlow from '../components/RequestFlow';
import RequestSimulator from '../components/RequestSimulator';
import CacheStatus from '../components/CacheStatus';
import PerformanceChart from '../components/PerformanceChart';
import RecentRequests from '../components/RecentRequests';
import { checkHealth, getStats, sendRequest, resetExperiment } from '../services/api';

export default function Dashboard() {
  const [isOnline, setIsOnline] = useState(false);
  const [stats, setStats] = useState({
    total_requests: 0,
    hits: 0,
    misses: 0,
    hit_ratio: 0.0,
    current_entries: 0,
  });
  const [recentRequests, setRecentRequests] = useState([]);
  const [lastResponse, setLastResponse] = useState(null);
  const [flowState, setFlowState] = useState('IDLE');
  const [isLoadingRequest, setIsLoadingRequest] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Fetch health & stats from backend
  const loadBackendData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    setErrorMessage(null);

    const health = await checkHealth();
    setIsOnline(health.online);

    if (health.online) {
      try {
        const statsData = await getStats();
        setStats(statsData);
      } catch (err) {
        setErrorMessage('Failed to fetch cache statistics from optimizer.');
      }
    } else {
      setErrorMessage(
        'Unable to connect to optimizer. Make sure the FastAPI server is running on port 8000.'
      );
    }

    if (showRefreshing) {
      setTimeout(() => setIsRefreshing(false), 300);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadBackendData();
  }, [loadBackendData]);

  // Handle request simulation
  const handleSendRequest = async (resourceId) => {
    setIsLoadingRequest(true);
    setFlowState('PENDING');
    setErrorMessage(null);

    const res = await sendRequest(resourceId);

    setIsLoadingRequest(false);
    setLastResponse(res);

    if (res.xCache === 'HIT') {
      setFlowState('HIT');
    } else if (res.xCache === 'MISS') {
      setFlowState('MISS');
    } else {
      setFlowState('IDLE');
    }

    // Add to in-memory session history (max 20)
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    const newRecord = {
      time: timeStr,
      resourceId: res.resourceId,
      status: res.status,
      xCache: res.xCache,
      source: res.source,
      latencyMs: res.latencyMs,
    };

    setRecentRequests((prev) => [newRecord, ...prev].slice(0, 20));

    // Refresh stats from backend to reflect true state
    try {
      const updatedStats = await getStats();
      setStats(updatedStats);
      setIsOnline(true);
    } catch {
      // Ignore if stats fail
    }
  };

  // Handle reset experiment
  const handleReset = async () => {
    setIsResetting(true);
    setErrorMessage(null);
    try {
      await resetExperiment();
      setRecentRequests([]);
      setLastResponse(null);
      setFlowState('IDLE');
      const updatedStats = await getStats();
      setStats(updatedStats);
    } catch (err) {
      setErrorMessage('Failed to reset experiment on backend: ' + err.message);
    } finally {
      setIsResetting(false);
    }
  };

  // KPI calculations derived strictly from backend counters
  const totalRequests = stats?.total_requests ?? 0;
  const cacheHits = stats?.hits ?? 0;
  const cacheMisses = stats?.misses ?? 0;
  const externalCalls = stats?.misses ?? 0; // In Phase 5, every cache miss forwards to mock API

  const cacheHitRatioFormatted =
    totalRequests > 0
      ? ((cacheHits / totalRequests) * 100).toFixed(1) + '%'
      : '0.0%';

  const apiCallReductionFormatted =
    totalRequests > 0
      ? (((totalRequests - externalCalls) / totalRequests) * 100).toFixed(1) + '%'
      : '0.0%';

  return (
    <div className="app-container">
      <Header
        isOnline={isOnline}
        onRefresh={() => loadBackendData(true)}
        isRefreshing={isRefreshing}
        onReset={handleReset}
        isResetting={isResetting}
      />

      {errorMessage && (
        <div className="error-banner" id="error-banner">
          <span>{errorMessage}</span>
          <button
            className="btn btn-secondary"
            style={{ padding: '4px 8px', fontSize: '0.72rem' }}
            onClick={() => loadBackendData(true)}
          >
            Retry
          </button>
        </div>
      )}

      {/* Primary KPI Grid (4 Cards) */}
      <section className="kpi-grid" id="kpi-cards">
        <KpiCard
          label="Total Requests"
          value={totalRequests}
          id="kpi-total-requests"
        />
        <KpiCard
          label="Cache Hits"
          value={cacheHits}
          badge="HIT"
          badgeType="hit"
          id="kpi-cache-hits"
        />
        <KpiCard
          label="Cache Misses"
          value={cacheMisses}
          badge="MISS"
          badgeType="miss"
          id="kpi-cache-misses"
        />
        <KpiCard
          label="External API Calls"
          value={externalCalls}
          id="kpi-external-calls"
        />
      </section>

      {/* Optimization Metrics (2 Cards) */}
      <section className="metrics-grid" id="optimization-metrics">
        <HighlightMetricCard
          title="API Call Reduction"
          description="Traffic diverted away from external upstream service"
          value={apiCallReductionFormatted}
          variant="accent"
          id="metric-call-reduction"
        />
        <HighlightMetricCard
          title="Cache Hit Ratio"
          description="Percentage of requests served instantly from in-memory cache"
          value={cacheHitRatioFormatted}
          variant="success"
          id="metric-hit-ratio"
        />
      </section>

      {/* Request Flow Pipeline Diagram */}
      <RequestFlow
        activeState={flowState}
        lastLatency={lastResponse?.latencyMs}
      />

      {/* Split Grid: Request Simulator & Side Metrics */}
      <div className="main-split-grid">
        <RequestSimulator
          onSendRequest={handleSendRequest}
          isLoading={isLoadingRequest}
          lastResponse={lastResponse}
          isOnline={isOnline}
        />

        <div className="side-column">
          <CacheStatus stats={stats} isOnline={isOnline} />
          <PerformanceChart hits={cacheHits} misses={cacheMisses} />
        </div>
      </div>

      {/* Recent Requests In-Memory Log */}
      <RecentRequests requests={recentRequests} />
    </div>
  );
}
