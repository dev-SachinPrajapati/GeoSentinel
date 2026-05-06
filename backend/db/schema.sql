-- ============================================================
-- Disaster Monitor — PostgreSQL + PostGIS Schema
-- Run on Neon DB after enabling the PostGIS extension
-- ============================================================

-- PostGIS extension (required)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email                   VARCHAR(255) NOT NULL UNIQUE,
    name                    VARCHAR(255) NOT NULL,
    notification_radius_km  FLOAT NOT NULL DEFAULT 100.0,
    -- GEOGRAPHY stores coordinates on Earth's surface (spherical model)
    home_location           GEOGRAPHY(POINT, 4326),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
);

-- GIST index for spatial queries on user home locations
CREATE INDEX IF NOT EXISTS idx_users_home_location
    ON users USING GIST (home_location);

-- ── Disaster Events ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS disaster_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     VARCHAR(255) UNIQUE,           -- for deduplication from external APIs
    type            VARCHAR(50) NOT NULL,           -- earthquake | flood | fire | ...
    severity        VARCHAR(20) NOT NULL,           -- low | medium | high | critical
    title           VARCHAR(500) NOT NULL,
    description     VARCHAR(2000),
    -- PostGIS GEOGRAPHY POINT: stores (longitude, latitude) in WGS84
    -- GEOGRAPHY vs GEOMETRY: geography is spherical (accurate for large distances)
    location        GEOGRAPHY(POINT, 4326) NOT NULL,
    -- Denormalized for fast non-spatial queries
    latitude        FLOAT NOT NULL,
    longitude       FLOAT NOT NULL,
    country         VARCHAR(100),
    region          VARCHAR(200),
    occurred_at     TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    source          VARCHAR(100) NOT NULL DEFAULT 'manual',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT valid_latitude  CHECK (latitude  BETWEEN -90  AND 90),
    CONSTRAINT valid_longitude CHECK (longitude BETWEEN -180 AND 180),
    CONSTRAINT valid_type      CHECK (type IN ('earthquake','flood','fire','hurricane','tsunami')),
    CONSTRAINT valid_severity  CHECK (severity IN ('low','medium','high','critical'))
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Primary spatial index — powers ST_DWithin, ST_Distance, ST_Within
CREATE INDEX IF NOT EXISTS idx_disaster_location
    ON disaster_events USING GIST (location);

-- Compound index for common filter patterns
CREATE INDEX IF NOT EXISTS idx_disaster_type_severity
    ON disaster_events (type, severity);

-- Time-series index — powers historical queries and timeline slider
CREATE INDEX IF NOT EXISTS idx_disaster_occurred_at
    ON disaster_events (occurred_at DESC);

-- Country filter
CREATE INDEX IF NOT EXISTS idx_disaster_country
    ON disaster_events (country);

-- Partial index: only active (non-expired) events for live view
CREATE INDEX IF NOT EXISTS idx_disaster_active
    ON disaster_events (occurred_at DESC)
    WHERE expires_at IS NULL OR expires_at > NOW();

-- JSONB index for metadata queries (e.g., filter by magnitude)
CREATE INDEX IF NOT EXISTS idx_disaster_metadata
    ON disaster_events USING GIN (metadata);

-- ── Views ─────────────────────────────────────────────────────────────────────

-- Active events (useful for dashboard default view)
CREATE OR REPLACE VIEW active_disaster_events AS
SELECT *
FROM disaster_events
WHERE expires_at IS NULL OR expires_at > NOW()
ORDER BY occurred_at DESC;

-- ── Example PostGIS Queries ───────────────────────────────────────────────────

-- 1. Find all disasters within 200km of Mumbai (lat=19.076, lon=72.877)
-- ST_DWithin uses GIST index — very fast even with millions of rows
/*
SELECT id, type, severity, title, latitude, longitude,
       ST_Distance(location::geography, ST_MakePoint(72.877, 19.076)::geography) / 1000 AS distance_km
FROM disaster_events
WHERE ST_DWithin(
    location::geography,
    ST_MakePoint(72.877, 19.076)::geography,
    200000  -- radius in meters
)
ORDER BY distance_km;
*/

-- 2. Cluster events by 1-degree grid cells (for heatmap aggregation)
/*
SELECT
    round(latitude::numeric, 0)  AS lat_bucket,
    round(longitude::numeric, 0) AS lon_bucket,
    type,
    COUNT(*) AS event_count,
    MAX(CASE severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) AS max_severity_score
FROM disaster_events
GROUP BY lat_bucket, lon_bucket, type
ORDER BY event_count DESC;
*/

-- 3. Find users within notification distance of a new disaster event
/*
SELECT u.id, u.email, u.name,
       ST_Distance(u.home_location, e.location) / 1000 AS distance_km
FROM users u
CROSS JOIN disaster_events e
WHERE e.id = '<disaster_id>'
  AND ST_DWithin(u.home_location, e.location, u.notification_radius_km * 1000);
*/

-- ── Seed Data ─────────────────────────────────────────────────────────────────
-- Add sample events for testing
INSERT INTO disaster_events (type, severity, title, latitude, longitude, location, occurred_at, source, metadata)
VALUES
    ('earthquake', 'high',     'M6.2 Earthquake - Japan',     35.689,  139.692,
     ST_SetSRID(ST_MakePoint(139.692, 35.689), 4326)::geography, NOW() - INTERVAL '2 hours', 'seed',
     '{"magnitude": 6.2, "depth_km": 35}'),
    ('flood',      'critical', 'Flash Flood - Bangladesh',    23.685,   90.356,
     ST_SetSRID(ST_MakePoint(90.356, 23.685), 4326)::geography,  NOW() - INTERVAL '4 hours', 'seed',
     '{"water_level_m": 4.5, "affected_area_km2": 1200}'),
    ('fire',       'high',     'Wildfire - California, USA',  36.778, -119.418,
     ST_SetSRID(ST_MakePoint(-119.418, 36.778), 4326)::geography, NOW() - INTERVAL '1 hour', 'seed',
     '{"area_hectares": 8500, "containment_pct": 23}'),
    ('earthquake', 'medium',   'M4.8 Earthquake - Greece',   39.074,   21.824,
     ST_SetSRID(ST_MakePoint(21.824, 39.074), 4326)::geography,  NOW() - INTERVAL '6 hours', 'seed',
     '{"magnitude": 4.8, "depth_km": 12}'),
    ('flood',      'high',     'River Flooding - Philippines', 12.879,  121.774,
     ST_SetSRID(ST_MakePoint(121.774, 12.879), 4326)::geography, NOW() - INTERVAL '3 hours', 'seed',
     '{"water_level_m": 2.8, "evacuation_order": true}')
ON CONFLICT (external_id) DO NOTHING;
