# API Traffic Optimizer — Prototype Dashboard

A lightweight, dark-mode observability dashboard for monitoring and demonstrating the Intelligent API Traffic Optimizer prototype (Phase 5).

## Tech Stack
- **React 18**
- **Vite**
- **Vanilla CSS** (custom dark system adhering to strict color tokens)

## Setup & Running

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy environment file (if customization needed):
   ```bash
   cp .env.example .env
   ```
   Default `VITE_API_BASE_URL` is `http://127.0.0.1:8000`.

3. Start development server:
   ```bash
   npm run dev
   ```

4. Build production bundle:
   ```bash
   npm run build
   ```

## Architecture & Features
- **Real-Time Backend Health**: Reflects `GET /health` with `● SYSTEM ONLINE` or `● SYSTEM OFFLINE`.
- **KPI Cards**: Live data for Total Requests, Cache Hits, Cache Misses, and External Calls.
- **Optimization Metrics**: Live calculated API Call Reduction and Cache Hit Ratio.
- **Request Flow Visualizer**: Interactive pipeline highlighting Cache Hit vs Cache Miss / External API routes.
- **Request Simulator**: Send actual requests to `/proxy/data/{resource_id}` and inspect HTTP status, latency, `X-Cache` header, and response payload.
- **Cache Performance Chart**: Clean SVG/CSS comparison of hits vs misses.
- **Recent Requests Table**: Session log of the last 15–20 simulated requests.
