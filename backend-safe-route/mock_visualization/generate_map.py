"""Generate a self-contained Leaflet map from one live Kraków route request."""

import asyncio
import json
from pathlib import Path

import httpx
from shapely import wkb
from sqlalchemy import func, select

from app.database.session import SessionFactory
from app.config import get_settings
from app.integrations.mapbox_directions_client import MapboxDirectionsClient
from app.schemas.route import Coordinate
from app.models.crime_event import CrimeEvent


OUTPUT_PATH = Path(__file__).with_name("krakow_routes.html")
RESULTS_PATH = Path(__file__).with_name("dworzec-mariacki-results.json")
API_URL = "http://127.0.0.1:8000/v1/route"
REQUEST = {
    "start": {"lat": 50.0687, "lon": 19.9450},
    "end": {"lat": 50.06160, "lon": 19.93900},
    "departure_time": "2026-10-04T02:03:50+02:00",
    "safety_weight": 0.9,
    "profile": "walking",
}


async def fetch_crime_events(route_response: dict) -> list[dict]:
    """Fetch crime events inside the corridor covered by the displayed routes."""

    coordinates = [
        coordinate
        for route in [route_response["fastest"], route_response["safest"], *route_response["alternatives"]]
        for coordinate in route["geometry"]["coordinates"]
    ]
    min_lon = min(coordinate[0] for coordinate in coordinates)
    max_lon = max(coordinate[0] for coordinate in coordinates)
    min_lat = min(coordinate[1] for coordinate in coordinates)
    max_lat = max(coordinate[1] for coordinate in coordinates)
    async with SessionFactory() as session:
        stmt = select(CrimeEvent).where(
            func.ST_X(CrimeEvent.geom).between(min_lon - 0.03, max_lon + 0.03),
            func.ST_Y(CrimeEvent.geom).between(min_lat - 0.03, max_lat + 0.03),
        )
        result = await session.execute(stmt)
        events = []
        for event in result.scalars().all():
            shape = wkb.loads(bytes(event.geom.data))
            events.append(
                {
                    "id": event.id,
                    "category": getattr(event.category, "value", str(event.category)),
                    "occurred_at": event.occurred_at.isoformat(),
                    "severity": event.severity,
                    "coordinates": [shape.x, shape.y],
                }
            )
        return events


def render_map(route_response: dict, crimes: list[dict], mapbox_routes: list[dict]) -> str:
    """Render route and crime data into a readable Leaflet HTML document."""

    payload = json.dumps(
        {"routes": route_response, "crimes": crimes, "mapbox_routes": mapbox_routes},
        separators=(",", ":"),
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Safe Route — Kraków mock visualization</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; }}
    #map {{ height: 100vh; }}
    .legend {{ background: white; padding: 12px 14px; line-height: 1.55; box-shadow: 0 1px 5px #777; border-radius: 4px; min-width: 220px; }}
    .legend h4 {{ margin: 0 0 6px; }}
    .swatch {{ display: inline-block; width: 24px; height: 4px; margin-right: 6px; vertical-align: middle; }}
    .dashed {{ height: 0; border-top: 3px dashed; }}
    .route-summary {{ margin-top: 8px; font-size: 12px; }}
  </style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const data = {payload};
const map = L.map("map").setView([50.056, 19.94], 14);
L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
  {{ maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }}).addTo(map);

const colors = {{
  mapbox: "#111111",
  fastest: "#1976d2",
  safest: "#16803c",
  alternatives: ["#f57c00", "#8e24aa", "#c62828", "#00838f", "#6d4c41", "#5e35b1"]
}};
const layers = [];
let selectedLayer = null;
function routeLine(route, color, label, weight) {{
  const line = L.geoJSON({{type: "Feature", geometry: route.geometry}}, {{
    style: {{color, weight, opacity: 0.88, dashArray: label === "alternative" ? "7 6" : null}}
  }}).bindPopup(`<b>${{label}}</b><br>distance: ${{route.distance_m.toFixed(1)}} m<br>
    duration: ${{route.duration_s.toFixed(1)}} s<br>safety score: ${{route.safety_score.toFixed(2)}}`);
  line.on("click", () => {{
    selectedLayer = line;
    layers.forEach(other => other.setStyle({{weight: other === line ? 10 : 3, opacity: other === line ? 1 : 0.28}}));
    line.bringToFront();
  }});
  line.on("mouseover", () => line.setStyle({{weight: 10, opacity: 1}}));
  line.on("mouseout", () => {{
    if (selectedLayer !== line) line.setStyle({{weight, opacity: 0.88}});
  }});
  line.addTo(map); layers.push(line);
}}
function mapboxLine(route, index) {{
  const line = L.geoJSON({{type: "Feature", geometry: {{type: "LineString", coordinates: route.geometry}}}}, {{
    style: {{color: colors.mapbox, weight: 3, opacity: 0.72, dashArray: "3 7"}}
  }}).bindPopup(`<b>Mapbox baseline #${{index + 1}}</b><br>
    distance: ${{route.distance_m.toFixed(1)}} m<br>duration: ${{route.duration_s.toFixed(1)}} s`);
  line.addTo(mapboxLayer);
}}
const mapboxLayer = L.layerGroup().addTo(map);
data.mapbox_routes.forEach(mapboxLine);
routeLine(data.routes.fastest, colors.fastest, "fastest", 6);
routeLine(data.routes.safest, colors.safest, "safest", 6);
data.routes.alternatives.forEach((route, index) =>
  routeLine(route, colors.alternatives[index % colors.alternatives.length], "alternative", 4));

const crimeLayer = L.layerGroup();
data.crimes.forEach(crime => {{
  const marker = L.circleMarker([crime.coordinates[1], crime.coordinates[0]], {{
    radius: 7, color: "#b71c1c", fillColor: "#e53935", fillOpacity: 0.8, weight: 2
  }}).bindPopup(`<b>Crime #${{crime.id}}</b><br>category: ${{crime.category}}<br>
    occurred: ${{crime.occurred_at}}<br>severity: ${{crime.severity ?? "n/a"}}`);
  marker.addTo(crimeLayer);
}});
crimeLayer.addTo(map);
L.control.layers(null, {{"Mapbox baseline": mapboxLayer, "crime events": crimeLayer}}).addTo(map);
const legend = L.control({{position: "bottomleft"}});
legend.onAdd = function() {{
  const div = L.DomUtil.create("div", "legend");
  const alternatives = data.routes.alternatives.length;
  div.innerHTML = `<h4>Dworzec Główny → Kościół Mariacki</h4>
    <span class="swatch" style="background:${{colors.mapbox}}"></span>Mapbox baseline (dashed)<br>
    <span class="swatch" style="background:${{colors.fastest}}"></span>fastest<br>
    <span class="swatch" style="background:${{colors.safest}}"></span>safest<br>
    <span class="swatch dashed" style="border-color:#f57c00"></span>alternatives (${{alternatives}})<br>
    <span style="color:#e53935">●</span> historical crime (${{data.crimes.length}})<br>
    <div class="route-summary">Safety weight: <b>${{(data.routes.meta.safety_weight * 100).toFixed(0)}}%</b><br>
    Click a route to highlight it.</div>`;
  return div;
}};
legend.addTo(map);
const bounds = L.latLngBounds([]);
layers.forEach(layer => bounds.extend(layer.getBounds()));
mapboxLayer.eachLayer(layer => bounds.extend(layer.getBounds()));
map.fitBounds(bounds.pad(0.08));
</script>
</body>
</html>
"""


async def main() -> None:
    """Call the live API, load crimes, and write the visualization HTML."""

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(API_URL, json=REQUEST)
        response.raise_for_status()
        route_response = response.json()
    crimes = await fetch_crime_events(route_response)
    settings = get_settings()
    mapbox = MapboxDirectionsClient(
        settings.mapbox_secret_token.get_secret_value()
    )
    try:
        mapbox_routes_raw = await asyncio.to_thread(
            mapbox.get_walking_routes,
            Coordinate(**REQUEST["start"]),
            Coordinate(**REQUEST["end"]),
            True,
        )
    finally:
        mapbox.close()
    mapbox_routes = [
        {
            "route_index": route.route_index,
            "geometry": route.geometry,
            "duration_s": route.duration_s,
            "distance_m": route.distance_m,
        }
        for route in mapbox_routes_raw
    ]
    route_response["meta"]["safety_weight"] = REQUEST["safety_weight"]
    RESULTS_PATH.write_text(
        json.dumps(
            {"request": REQUEST, "mapbox_routes": mapbox_routes, "route_response": route_response, "crimes": crimes},
            indent=2,
        ),
        encoding="utf-8",
    )
    OUTPUT_PATH.write_text(render_map(route_response, crimes, mapbox_routes), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"wrote {RESULTS_PATH}")
    print(f"mapbox routes: {len(mapbox_routes)}, alternatives: {len(route_response['alternatives'])}, crimes: {len(crimes)}")


if __name__ == "__main__":
    asyncio.run(main())
