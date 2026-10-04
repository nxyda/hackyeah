"""Generate an interactive HTML report for random Kraków route samples."""

import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from sqlalchemy import func, select

from app.database.session import SessionFactory
from app.models.road_segment import RoadSegment


OUTPUT_PATH = Path(__file__).with_name("krakow-random-routes-report.html")
API_URL = "http://127.0.0.1:8000/v1/route"
ROUTE_COUNT = 5
RANDOM_SEED = 20261004
SAFETY_WEIGHT = 0.9
DEPARTURE_TIME = "2026-10-04T03:00:00+02:00"
KRAKOW_BOUNDS = (19.85, 20.05, 49.98, 50.12)


@dataclass(frozen=True)
class RouteSample:
    """One reproducible pair of points sampled from a road geometry."""

    start: dict[str, float]
    end: dict[str, float]


async def load_road_points(seed: int, count: int) -> list[RouteSample]:
    """Sample endpoint pairs from the current road-segment geometries."""

    min_lon, max_lon, min_lat, max_lat = KRAKOW_BOUNDS
    async with SessionFactory() as session:
        result = await session.execute(
            select(RoadSegment.geom)
            .where(
                func.ST_X(func.ST_Centroid(RoadSegment.geom)).between(min_lon, max_lon),
                func.ST_Y(func.ST_Centroid(RoadSegment.geom)).between(min_lat, max_lat),
            )
            .limit(10_000)
        )
        geometries = [to_shape(value) for (value,) in result.all()]

    if len(geometries) < count * 2:
        raise RuntimeError(
            f"Only {len(geometries)} Kraków road geometries available; "
            f"cannot sample {count} routes."
        )

    rng = random.Random(seed)
    samples: list[RouteSample] = []
    attempts = 0
    while len(samples) < count and attempts < count * 100:
        attempts += 1
        first, second = rng.sample(geometries, 2)
        start = first.interpolate(rng.random(), normalized=True)
        end = second.interpolate(rng.random(), normalized=True)
        if start.distance(end) < 0.008:
            continue
        samples.append(
            RouteSample(
                start={"lat": start.y, "lon": start.x},
                end={"lat": end.y, "lon": end.x},
            )
        )
    if len(samples) != count:
        raise RuntimeError("Could not sample sufficiently separated Kraków route endpoints.")
    return samples


def build_request(sample: RouteSample) -> dict[str, object]:
    """Create the public routing request for one sampled pair."""

    return {
        "start": sample.start,
        "end": sample.end,
        "departure_time": DEPARTURE_TIME,
        "safety_weight": SAFETY_WEIGHT,
        "profile": "walking",
    }


async def fetch_routes(samples: list[RouteSample]) -> list[dict[str, object]]:
    """Run the production API for every sample and fail on the first bad result."""

    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=180) as client:
        for index, sample in enumerate(samples, start=1):
            request = build_request(sample)
            response = await client.post(API_URL, json=request)
            if response.is_error:
                raise RuntimeError(
                    f"Route {index} failed with HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )
            payload = response.json()
            if not payload.get("fastest") or not payload.get("safest"):
                raise RuntimeError(f"Route {index} returned no fastest/safest route.")
            results.append({"index": index, "request": request, "response": payload})
    return results


def render_report(results: list[dict[str, object]]) -> str:
    """Render route payloads, active maps, charts, findings and methodology."""

    payload = json.dumps(results, separators=(",", ":"))
    metrics = []
    for item in results:
        response = item["response"]
        fastest = response["fastest"]
        safest = response["safest"]
        metrics.append(
            {
                "index": item["index"],
                "fastest_distance": fastest["distance_m"],
                "safest_distance": safest["distance_m"],
                "fastest_duration": fastest["duration_s"],
                "safest_duration": safest["duration_s"],
                "fastest_score": fastest["safety_score"],
                "safest_score": safest["safety_score"],
                "alternatives": len(response["alternatives"]),
                "coverage": response["meta"]["data_coverage"],
            }
        )
    metrics_json = json.dumps(metrics, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Safe Route — Kraków random route evaluation</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; background: #f3f5f7; color: #17202a; }}
    main {{ max-width: 1280px; margin: auto; padding: 24px; }}
    h1, h2 {{ margin-top: 0; }}
    .intro, .card {{ background: white; border-radius: 10px; padding: 18px; margin-bottom: 18px; box-shadow: 0 1px 5px #ccd2d8; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
    .metric strong {{ display: block; font-size: 1.55rem; }}
    .route-card {{ overflow: hidden; }}
    .map {{ height: 430px; }}
    .details {{ padding: 14px 18px; }}
    .swatch {{ display: inline-block; width: 28px; border-top: 5px solid; margin-right: 6px; vertical-align: middle; }}
    .risk-chart {{ display: flex; align-items: end; height: 80px; gap: 2px; margin-top: 10px; }}
    .risk-bar {{ flex: 1; min-width: 2px; background: #4caf50; }}
    .risk-bar.medium {{ background: #f6b73c; }}
    .risk-bar.high {{ background: #d64545; }}
    code {{ background: #eef1f3; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <section class="intro">
    <h1>Random Kraków route evaluation</h1>
    <p>Five reproducible route pairs were sampled from the current <code>road_segments</code>
    geometries and evaluated through the production <code>POST /v1/route</code> endpoint.</p>
    <p><b>Seed:</b> {RANDOM_SEED} · <b>Safety weight:</b> {SAFETY_WEIGHT:.0%} ·
    <b>Departure:</b> {DEPARTURE_TIME}</p>
    <p>The maps are interactive: click a route to highlight it, hover over a line,
    and use the layer control to toggle the risk segments.</p>
  </section>
  <section class="card">
    <h2>Summary</h2>
    <div id="summary" class="grid"></div>
    <div id="comparison" class="grid"></div>
  </section>
  <section class="card">
    <h2>Method and reasoning</h2>
    <ol>
      <li>Endpoint pairs were sampled on real database road geometries inside a Kraków bounding box;
      no synthetic route geometry was inserted.</li>
      <li>Each pair was sent to the same live API used by the frontend. Mapbox supplied baseline
      candidates, while the local graph and scoring pipeline evaluated database segments.</li>
      <li>Safety-aware features include lighting, reports and confirmations, crime exposure,
      cameras, safe places, tunnels, road type, surface, incline, crossings, stairs and access
      where the database contains them.</li>
      <li><code>fastest</code> and <code>safest</code> were selected by the backend; alternatives
      are all remaining unique candidates returned by that calculation.</li>
      <li>Segment colors use the API's <code>risk_level</code>: green below 30, amber from 30
      to 60, and red above 60.</li>
    </ol>
  </section>
  <section id="routes"></section>
  <section class="card">
    <h2>Conclusions</h2>
    <div id="conclusions"></div>
  </section>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const samples = {payload};
const metrics = {metrics_json};
const routeColors = {{ fastest: "#1976d2", safest: "#16803c", alternative: "#e67e22" }};

function riskClass(value) {{
  return value < 30 ? "" : value <= 60 ? "medium" : "high";
}}
function routeLine(map, route, color, label, weight, layers) {{
  const line = L.geoJSON({{type: "Feature", geometry: route.geometry}}, {{
    style: {{color, weight, opacity: 0.88, dashArray: label === "alternative" ? "7 6" : null}}
  }}).bindPopup(`<b>${{label}}</b><br>${{route.distance_m.toFixed(1)}} m ·
    ${{route.duration_s.toFixed(1)}} s · safety ${{route.safety_score.toFixed(1)}}/100<br>
    ${{route.explanation}}`);
  line.on("click", () => {{
    layers.forEach(item => item.setStyle({{weight: 3, opacity: 0.28}}));
    line.setStyle({{weight: 10, opacity: 1}});
    line.bringToFront();
  }});
  line.on("mouseover", () => line.setStyle({{weight: 10, opacity: 1}}));
  line.addTo(map);
  layers.push(line);
}}
function addRiskSegments(map, route, riskLayer) {{
  route.segments.forEach(segment => {{
    const color = segment.risk_level < 30 ? "#43a047" :
      segment.risk_level <= 60 ? "#f9a825" : "#d32f2f";
    L.geoJSON({{type: "Feature", geometry: segment.geometry}}, {{
      style: {{color, weight: 7, opacity: 0.75}}
    }}).bindPopup(`risk level: ${{segment.risk_level.toFixed(1)}}/100`).addTo(riskLayer);
  }});
}}
function renderRoute(item) {{
  const response = item.response;
  const request = item.request;
  const section = document.createElement("section");
  section.className = "card route-card";
  section.innerHTML = `<h2>Route ${{item.index}}</h2>
    <div class="details"><b>Start:</b> ${{request.start.lat.toFixed(5)}}, ${{request.start.lon.toFixed(5)}} ·
    <b>End:</b> ${{request.end.lat.toFixed(5)}}, ${{request.end.lon.toFixed(5)}}<br>
    <span class="swatch" style="border-color:${{routeColors.fastest}}"></span>fastest
    ${{response.fastest.distance_m.toFixed(0)}} m / ${{response.fastest.safety_score.toFixed(1)}} safety
    <span class="swatch" style="border-color:${{routeColors.safest}}"></span>safest
    ${{response.safest.distance_m.toFixed(0)}} m / ${{response.safest.safety_score.toFixed(1)}} safety
    <div class="risk-chart" id="risk-${{item.index}}"></div></div>`;
  const mapElement = document.createElement("div");
  mapElement.className = "map";
  section.insertBefore(mapElement, section.querySelector(".details"));
  document.querySelector("#routes").appendChild(section);
  const map = L.map(mapElement).setView([request.start.lat, request.start.lon], 14);
  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
    {{maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"}}).addTo(map);
  const layers = [];
  routeLine(map, response.fastest, routeColors.fastest, "fastest", 6, layers);
  routeLine(map, response.safest, routeColors.safest, "safest", 6, layers);
  response.alternatives.forEach(route => routeLine(map, route, routeColors.alternative, "alternative", 4, layers));
  const riskLayer = L.layerGroup().addTo(map);
  addRiskSegments(map, response.safest, riskLayer);
  L.control.layers(null, {{"safest risk segments": riskLayer}}).addTo(map);
  const allBounds = L.latLngBounds([]);
  layers.forEach(layer => allBounds.extend(layer.getBounds()));
  map.fitBounds(allBounds.pad(0.12));
  const chart = section.querySelector(`#risk-${{item.index}}`);
  response.safest.segments.forEach(segment => {{
    const bar = document.createElement("div");
    bar.className = `risk-bar ${{riskClass(segment.risk_level)}}`;
    bar.style.height = `${{Math.max(4, segment.risk_level)}}%`;
    bar.title = `risk ${{segment.risk_level.toFixed(1)}}`;
    chart.appendChild(bar);
  }});
}}
metrics.forEach(() => {{}});
const averageFastest = metrics.reduce((sum, item) => sum + item.fastest_score, 0) / metrics.length;
const averageSafest = metrics.reduce((sum, item) => sum + item.safest_score, 0) / metrics.length;
const different = metrics.filter(item => item.fastest_distance !== item.safest_distance).length;
document.querySelector("#summary").innerHTML = `
  <div class="metric">Routes evaluated<strong>${{metrics.length}}</strong></div>
  <div class="metric">Average fastest safety<strong>${{averageFastest.toFixed(1)}}/100</strong></div>
  <div class="metric">Average safest safety<strong>${{averageSafest.toFixed(1)}}/100</strong></div>
  <div class="metric">Different fastest/safest<strong>${{different}} / ${{metrics.length}}</strong></div>`;
document.querySelector("#comparison").innerHTML = metrics.map(item =>
  `<div><b>Route ${{item.index}}</b>: fastest ${{item.fastest_distance.toFixed(0)}} m,
  safest ${{item.safest_distance.toFixed(0)}} m, ${{item.alternatives}} alternatives,
  coverage <code>${{item.coverage}}</code></div>`).join("");
document.querySelector("#conclusions").innerHTML = `
  <p>Across this sample, the safety-aware selection had an average score of
  <b>${{averageSafest.toFixed(1)}}</b>, compared with <b>${{averageFastest.toFixed(1)}}</b>
  for the fastest selection.</p>
  <p>The fastest and safest candidates differed in ${{different}} of ${{metrics.length}}
  samples. This is an observation of the current data and weights, not a statistical
  benchmark of Kraków-wide routing quality.</p>
  <p>Interpretation should account for <code>data_coverage</code>: missing nullable
  infrastructure values are neutral in scoring and reduce confidence in conclusions.</p>`;
samples.forEach(renderRoute);
</script>
</body>
</html>
"""


async def main() -> None:
    """Generate the five-route report from the live database and API."""

    samples = await load_road_points(RANDOM_SEED, ROUTE_COUNT)
    results = await fetch_routes(samples)
    OUTPUT_PATH.write_text(render_report(results), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"evaluated routes: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
