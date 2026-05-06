"use client";

import { useCallback, useMemo, useRef } from "react";
import ReactMap, { 
  Layer,
  MapRef,
  Popup,
  Source,
  NavigationControl,
  FullscreenControl,
  ScaleControl,
} from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

import { useAppStore } from "@/store";
import { DisasterEvent } from "@/types";
import { HEATMAP_COLOR_GRADIENT, eventsToGeoJSON } from "@/lib/mapUtils";
import { EventPopup } from "./EventPopup";

// const MAP_STYLE =
//   process.env.NEXT_PUBLIC_MAPTILER_STYLE ||
//   'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const MAP_STYLE =
  (process.env.NEXT_PUBLIC_MAPTILER_STYLE ?? "").trim() || "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
interface DisasterMapProps {
  events: DisasterEvent[];
  heatmapPoints?: Array<{ lat: number; lon: number; weight: number }>;
}

export function DisasterMap({ events, heatmapPoints = [] }: DisasterMapProps) {
  const mapRef = useRef<MapRef>(null);
  const {
    viewState,
    setViewState,
    selectedEvent,
    setSelectedEvent,
    showHeatmap,
    liveEvents,
  } = useAppStore();

  // Merge API events + live WS events (deduplicate by ID).
  // Fix 1: "Map" import shadowed the JS global — renamed import to ReactMap
  //         and use globalThis.Map here to be explicit.
  const allEvents = useMemo(() => {
    const eventMap = new globalThis.Map<string, DisasterEvent>();
    events.forEach((e) => eventMap.set(e.id, e));
    // Fix 2: liveEvents may be typed as unknown[] in the store — cast each item
    (liveEvents as DisasterEvent[]).forEach((e) => eventMap.set(e.id, e));
    return Array.from(eventMap.values());
  }, [events, liveEvents]);

  const geojson = useMemo(() => eventsToGeoJSON(allEvents), [allEvents]);

  const heatmapGeojson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: heatmapPoints.map((p) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] },
        properties: { weight: p.weight },
      })),
    }),
    [heatmapPoints],
  );

  // Fix 3: Layer <onClick> prop does not exist — handle ALL clicks on the map
  //         level and discriminate by queried layer name.
  const handleClick = useCallback(
    (e: maplibregl.MapMouseEvent) => {
      const glMap = mapRef.current?.getMap();
      if (!glMap) return;

      // Check for cluster click first
      const clusterFeatures = glMap.queryRenderedFeatures(e.point, {
        layers: ["clusters"],
      });
      if (clusterFeatures.length > 0) {
        const clusterId = clusterFeatures[0].properties?.cluster_id as number;
        const source = glMap.getSource("disasters") as maplibregl.GeoJSONSource;

        // Fix 4: newer maplibre getClusterExpansionZoom returns a Promise (1 arg),
        //         old callback form (2 args) was removed.
        source
          .getClusterExpansionZoom(clusterId)
          .then((zoom) => {
            const coords = (clusterFeatures[0].geometry as GeoJSON.Point)
              .coordinates as [number, number];
            glMap.easeTo({ center: coords, zoom });
          })
          .catch(() => {});
        return;
      }

      // Check for individual event marker click
      const eventFeatures = glMap.queryRenderedFeatures(e.point, {
        layers: ["unclustered-point", "critical-pulse"],
      });
      if (eventFeatures.length > 0) {
        const id = eventFeatures[0].properties?.id as string | undefined;
        const event = allEvents.find((ev) => ev.id === id);
        if (event) {
          setSelectedEvent(event);
          return;
        }
      }

      // Click on empty area — close popup
      setSelectedEvent(null);
    },
    [allEvents, setSelectedEvent],
  );

  const handleMouseEnter = useCallback(() => {
    const glMap = mapRef.current?.getMap();
    if (glMap) glMap.getCanvas().style.cursor = "pointer";
  }, []);

  const handleMouseLeave = useCallback(() => {
    const glMap = mapRef.current?.getMap();
    if (glMap) glMap.getCanvas().style.cursor = "";
  }, []);

  return (
    <ReactMap
      ref={mapRef}
      {...viewState}
      onMove={(evt) => setViewState(evt.viewState)}
      mapStyle={MAP_STYLE}
      style={{ width: "100%", height: "100%" }}
      onClick={handleClick}
      interactiveLayerIds={["clusters", "unclustered-point", "critical-pulse"]}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      attributionControl={false}
    >
      <NavigationControl position="top-right" />
      <FullscreenControl position="top-right" />
      <ScaleControl position="bottom-right" />

      {/* ── Disaster Events Source (clustered) ── */}
      <Source
        id="disasters"
        type="geojson"
        data={geojson}
        cluster={true}
        clusterMaxZoom={8}
        clusterRadius={50}
      >
        {/* Cluster circles — no onClick prop; handled by map-level handleClick */}
        <Layer
          id="clusters"
          type="circle"
          filter={["has", "point_count"]}
          paint={{
            "circle-color": [
              "step",
              ["get", "point_count"],
              "#22C55E",
              10,
              "#EAB308",
              30,
              "#F97316",
              60,
              "#EF4444",
            ],
            "circle-radius": [
              "step",
              ["get", "point_count"],
              18,
              10,
              24,
              30,
              30,
              60,
              36,
            ],
            "circle-opacity": 0.85,
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(255,255,255,0.2)",
          }}
        />

        {/* Cluster count labels */}
        <Layer
          id="cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": "{point_count_abbreviated}",
            "text-font": ["Open Sans Bold"],
            "text-size": 13,
          }}
          paint={{ "text-color": "#fff" }}
        />

        {/* Individual event circles */}
        <Layer
          id="unclustered-point"
          type="circle"
          filter={["!", ["has", "point_count"]]}
          paint={{
            "circle-color": ["get", "color"],
            "circle-radius": ["get", "radius"],
            "circle-opacity": 0.9,
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(255,255,255,0.6)",
          }}
        />

        {/* Severity pulse ring for critical events */}
        <Layer
          id="critical-pulse"
          type="circle"
          filter={["==", ["get", "severity"], "critical"]}
          paint={{
            "circle-color": "transparent",
            "circle-radius": 28,
            "circle-stroke-width": 3,
            "circle-stroke-color": "#EF4444",
            "circle-stroke-opacity": 0.5,
          }}
        />
      </Source>

      {/* ── Heatmap Layer ── */}
      {showHeatmap && (
        <Source id="heatmap-source" type="geojson" data={heatmapGeojson}>
          <Layer
            id="heatmap-layer"
            type="heatmap"
            paint={{
              "heatmap-weight": [
                "interpolate",
                ["linear"],
                ["get", "weight"],
                0,
                0,
                1,
                1,
              ],
              "heatmap-intensity": [
                "interpolate",
                ["linear"],
                ["zoom"],
                0,
                1,
                9,
                3,
              ],
              "heatmap-color": HEATMAP_COLOR_GRADIENT as any,
              "heatmap-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                0,
                20,
                9,
                40,
              ],
              "heatmap-opacity": 0.7,
            }}
          />
        </Source>
      )}

      {/* ── Event Popup ── */}
      {selectedEvent && (
        <Popup
          longitude={selectedEvent.longitude}
          latitude={selectedEvent.latitude}
          anchor="bottom"
          onClose={() => setSelectedEvent(null)}
          closeButton={true}
          maxWidth="320px"
          className="disaster-popup"
        >
          <EventPopup event={selectedEvent} />
        </Popup>
      )}
    </ReactMap>
  );
}
