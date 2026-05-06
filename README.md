# 🌍 Real-Time Disaster Monitor

A production-ready, full-stack geospatial web application tracking earthquakes, floods, and wildfires worldwide — with real-time WebSocket updates, PostGIS spatial queries, and an interactive MapLibre map.

---

## 📁 Folder Structure

```
disaster-monitor/
├── backend/
│   ├── core/
│   │   └── config.py              # Pydantic settings, env vars
│   ├── db/
│   │   ├── database.py            # Async SQLAlchemy engine, session factory
│   │   └── schema.sql             # Raw SQL schema + PostGIS setup + indexes
│   ├── models/
│   │   └── disaster.py            # SQLAlchemy ORM models (PostGIS GEOGRAPHY)
│   ├── schemas/
│   │   └── disaster.py            # Pydantic v2 request/response schemas
│   ├── routers/
│   │   ├── disasters.py           # REST API endpoints
│   │   └── websocket.py           # WebSocket endpoint
│   ├── services/
│   │   ├── disaster_service.py    # Business logic + PostGIS queries
│   │   └── ingestion_service.py   # USGS fetch + mock generator + broadcast
│   ├── websocket/
│   │   └── manager.py             # Connection manager (broadcast, proximity alerts)
│   ├── tests/
│   │   └── test_api.py            # pytest + pytest-asyncio unit + integration tests
│   ├── main.py                    # FastAPI app entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx          # Root layout + font
│       │   ├── page.tsx            # Main dashboard page
│       │   ├── providers.tsx       # TanStack Query provider
│       │   └── globals.css         # Tailwind + MapLibre overrides
│       ├── components/
│       │   ├── map/
│       │   │   ├── DisasterMap.tsx # MapLibre map + layers + clustering
│       │   │   └── EventPopup.tsx  # Marker popup
│       │   ├── sidebar/
│       │   │   └── Sidebar.tsx     # Filter panel
│       │   ├── notifications/
│       │   │   └── NotificationPanel.tsx
│       │   ├── timeline/
│       │   │   └── Timeline.tsx    # Historical playback slider
│       │   └── Navbar.tsx          # Top bar + WS status
│       ├── hooks/
│       │   └── useWebSocket.ts     # WS client with auto-reconnect
│       ├── lib/
│       │   ├── api.ts              # API client + TanStack Query keys
│       │   └── mapUtils.ts         # Colors, icons, GeoJSON helpers
│       ├── store/
│       │   └── index.ts            # Zustand global store
│       └── types/
│           └── index.ts            # TypeScript interfaces
│
├── docker-compose.yml              # Local dev (PostGIS + backend)
└── .github/workflows/ci.yml        # GitHub Actions CI/CD
```

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS (Browser)                         │
│   Next.js App (Vercel)                                           │
│   ┌──────────────┐  HTTP/REST    ┌─────────────────────────┐   │
│   │ TanStack     │──────────────▶│                         │   │
│   │ Query        │               │     FastAPI Backend      │   │
│   └──────────────┘               │     (Railway/Render)     │   │
│   ┌──────────────┐  WebSocket    │                         │   │
│   │ useWebSocket │◀─────────────▶│  /ws/disasters          │   │
│   │ Hook         │               │                         │   │
│   └──────────────┘               └────────────┬────────────┘   │
│   ┌──────────────┐                             │               │
│   │ MapLibre GL  │                             │ asyncpg        │
│   │ (Map UI)     │               ┌─────────────▼────────────┐  │
│   └──────────────┘               │   PostgreSQL + PostGIS   │  │
│   ┌──────────────┐               │   (Neon DB — Serverless) │  │
│   │ Zustand      │               └──────────────────────────┘  │
│   │ Store        │                             ▲               │
│   └──────────────┘               ┌─────────────┴────────────┐  │
│                                  │   Background Ingestion   │  │
│                                  │   - USGS Earthquake API  │  │
│                                  │   - Mock Generator       │  │
│                                  │   (asyncio loop, 60s)   │  │
│                                  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ WebSocket Flow

```
Client                           Server
  │                                │
  │──── WS Connect ────────────────▶
  │◀─── {type: "connected"} ───────│
  │                                │
  │──── {type: "subscribe",        │
  │      payload: {lat, lon, r}} ──▶  Manager.update_subscription()
  │◀─── {type: "subscribed"} ──────│
  │                                │
  │           [Background ingestion fetches new event]
  │                                │
  │◀─── {type: "new_event", ───────│  manager.broadcast_event()
  │      payload: DisasterEvent}   │
  │                                │
  │◀─── {type: "nearby_alert"} ────│  manager.send_proximity_alerts()
  │      (only if within radius)   │  (Haversine distance check)
  │                                │
  │◀─── {type: "heartbeat"} ───────│  Every 30 seconds
  │──── {type: "ping"} ────────────▶
  │◀─── {type: "pong"} ────────────│
```

---

## 🗄️ Data Flow

```
External APIs / Mock Generator
         │
         ▼
ingestion_service.py (asyncio background task, 60s interval)
         │ fetch USGS earthquakes
         │ generate mock floods/fires
         ▼
DisasterService.create_event()
         │ Deduplication via external_id
         │ Build GEOGRAPHY POINT from lat/lon
         │ INSERT into disaster_events
         ▼
PostgreSQL + PostGIS (Neon DB)
         │
         ▼
ConnectionManager.broadcast_event()  ←── broadcasts to ALL clients
ConnectionManager.send_proximity_alerts()  ←── targeted by Haversine
         │
         ▼
WebSocket clients receive new_event / nearby_alert
         │
         ▼
Zustand store (addLiveEvent, addNotification)
         │
         ▼
Map re-renders with merged events (API + live)
```

---

## 🚀 Quick Start (Local Development)

### 1. Clone & Start Backend + Database

```bash
git clone <repo>
cd disaster-monitor

# Start PostGIS + backend
docker-compose up -d

# Backend runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 2. Start Frontend

```bash
cd frontend
cp .env.local.example .env.local
# Edit .env.local: set NEXT_PUBLIC_API_URL=http://localhost:8000

npm install
npm run dev
# App at http://localhost:3000
```

### 3. Initialize Database Schema

```bash
# Via Docker
docker exec -i disaster-monitor-postgres-1 psql -U disaster -d disaster_monitor < backend/db/schema.sql
```

---

## 🌐 Production Deployment

### Backend → Railway / Render

```bash
# 1. Build image
docker build -t disaster-monitor-api ./backend

# 2. Push to registry (GitHub Packages, DockerHub, ECR)
docker push your-registry/disaster-monitor-api

# 3. Set environment variables in Railway/Render:
DATABASE_URL=postgresql://...neon.tech/disaster_monitor
SECRET_KEY=your-long-random-secret
ALLOWED_ORIGINS=["https://your-app.vercel.app"]
ENVIRONMENT=production
```

### Database → Neon DB

```bash
# 1. Create project at console.neon.tech
# 2. Enable PostGIS in Neon SQL editor:
CREATE EXTENSION IF NOT EXISTS postgis;

# 3. Run schema
psql $DATABASE_URL < backend/db/schema.sql

# 4. Connection string format:
# postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/disaster_monitor
```

### Frontend → Vercel

```bash
cd frontend

# Install Vercel CLI
npm i -g vercel

# Set env vars
vercel env add NEXT_PUBLIC_API_URL     # https://your-api.railway.app
vercel env add NEXT_PUBLIC_WS_URL      # wss://your-api.railway.app

# Deploy
vercel --prod
```

---

## 🔑 Key PostGIS Queries

### Find events within radius (ST_DWithin)
```sql
-- Uses GIST index — O(log n)
SELECT *, ST_Distance(location, ST_MakePoint(139.69, 35.69)::geography) / 1000 AS km
FROM disaster_events
WHERE ST_DWithin(
    location,
    ST_SetSRID(ST_MakePoint(139.69, 35.69), 4326)::geography,
    200000  -- 200km in meters
)
ORDER BY km;
```

### Find users near a disaster (for notifications)
```sql
SELECT u.id, u.email,
       ST_Distance(u.home_location, e.location) / 1000 AS distance_km
FROM users u
CROSS JOIN disaster_events e
WHERE e.id = $1
  AND ST_DWithin(u.home_location, e.location, u.notification_radius_km * 1000);
```

---

## ⚡ Performance Optimizations

| Area | Technique | Impact |
|------|-----------|--------|
| **DB — Spatial** | GIST index on `location` column | ST_DWithin: O(log n) vs O(n) |
| **DB — Reads** | Denormalized `latitude`/`longitude` | Avoids ST_X/ST_Y on every read |
| **DB — Filtering** | Composite indexes (type+severity, occurred_at) | Fast filter queries |
| **DB — Dedup** | `external_id` unique constraint + early return | No duplicate events |
| **DB — Pool** | asyncpg connection pooling (size=10) | No connection storm |
| **API** | GZip middleware | ~70% payload reduction |
| **API** | Async everywhere (no blocking I/O) | Max concurrency |
| **WebSocket** | In-process Haversine for proximity | No extra DB round-trip |
| **Frontend** | MapLibre clustering (clusterMaxZoom=8) | No lag with 1000+ markers |
| **Frontend** | TanStack Query deduplication + cache | Minimal re-fetches |
| **Frontend** | Dynamic import for Map (no SSR) | Faster initial load |
| **Frontend** | Zustand (no re-renders) | Targeted state updates |
| **Frontend** | Event deduplication by ID | API + WS events merged cleanly |

---

## 🔐 Security

- **Pydantic v2 validation** on all inputs (coordinates, strings, enums)
- **CORS** restricted to allowed origins
- **GZip** middleware (no content sniffing)
- **Rate limiting** via slowapi (60 req/min default)
- **Non-root Docker user** (`appuser`)
- **Security headers** in Next.js config (X-Frame-Options, CSP, etc.)
- **PostGIS parameterized queries** via SQLAlchemy (no SQL injection)

---

## 🧪 Running Tests

```bash
cd backend

# Install test deps
pip install pytest pytest-asyncio httpx

# Run all tests with coverage
pytest tests/ -v --cov=. --cov-report=html

# Run specific test class
pytest tests/test_api.py::TestWebSocket -v
```

---

## ❗ Common Pitfalls & Solutions

| Pitfall | Solution |
|---------|----------|
| **PostGIS ST_MakePoint takes (lon, lat)** — opposite of common expectation | Always pass `(longitude, latitude)` — documented in code |
| **GEOGRAPHY vs GEOMETRY** — wrong type causes inaccurate distances | Use `GEOGRAPHY` for real-world distance (spherical); GEOMETRY is planar |
| **MapLibre SSR crash** — `window` not defined in Next.js | `dynamic(() => import(...), { ssr: false })` |
| **WebSocket disconnects on Vercel** — no WS support | Backend must be on Railway/Render/Fly, not Vercel |
| **Neon DB cold starts** — serverless DB sleeps | Use `pool_pre_ping=True` + `pool_recycle=300` |
| **WS reconnect storm** — all clients reconnect at once after outage | Exponential backoff with jitter (implemented in useWebSocket) |
| **Event deduplication** — USGS feed repeats events | `external_id` UNIQUE constraint + early return in service |
| **Heatmap on dark maps** — invisible colors | Use high-contrast gradient starting from transparent |
| **Missing PostGIS extension** — "type geography does not exist" | Run `CREATE EXTENSION postgis;` BEFORE creating tables |

---

## 📈 Scaling Strategy

```
Current (Single Instance):
  1 FastAPI process → handles ~1000 concurrent WS connections

Scale Horizontally:
  → Add Redis Pub/Sub between multiple FastAPI instances
  → Each instance subscribes to "disaster_events" Redis channel
  → Any instance can publish; all instances broadcast to their clients
  → Use Redis as shared session store for WS client state

Load Balancer → [API-1] [API-2] [API-3]
                    ↑       ↑       ↑
                    └───────┴───────┘
                          Redis
                            ↑
                        PostgreSQL
```

**Database scaling:**
- Neon DB auto-scales read replicas
- Add `pg_partman` to partition `disaster_events` by `occurred_at` (monthly)
- Add read replica for heatmap/historical queries

---

## 🧰 Tech Choices Explained

| Choice | Why |
|--------|-----|
| **FastAPI** | Async-native, auto OpenAPI docs, Pydantic integration, WebSocket support |
| **PostGIS GEOGRAPHY** | Spherical distance calculations accurate to <0.5% anywhere on Earth |
| **asyncpg** | 3-5x faster than psycopg2 for async workloads |
| **MapLibre GL** | Open-source (no Mapbox token required for basic use), WebGL-powered |
| **TanStack Query** | Caching, deduplication, background refetch, DevTools |
| **Zustand** | Lightweight, no boilerplate, selector-based re-renders |
| **Neon DB** | Serverless PostgreSQL with PostGIS, free tier, auto-scaling, branching |
