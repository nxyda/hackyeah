# Kraków route mock visualization

This directory contains a generated, local-only visualization of one live
route request. The map shows:

- the Mapbox/local routing candidates;
- the selected `fastest` route;
- the selected `safest` route;
- alternative routes;
- historical crime events found in the request corridor.

Generate the map while the API is running:

```bash
.venv/bin/python -m mock_visualization.generate_map
```

Then open [krakow_routes.html](./krakow_routes.html) in a browser.

The HTML uses Leaflet from its public CDN and is intended for development
demonstrations, not as a production frontend.

Route explanations include the score, data coverage, lighting, reports,
crime exposure, cameras, safe places, surface, incline, crossing, stairs and
access signals used for the candidate.

## Random-route evaluation report

To evaluate five reproducible route pairs sampled from the current Kraków
`road_segments` data, keep the API running and run:

```bash
.venv/bin/python -m mock_visualization.generate_random_routes_report
```

The command writes
[krakow-random-routes-report.html](./krakow-random-routes-report.html). It
contains five interactive Leaflet maps, fastest/safest/alternative routes,
clickable risk segments, summary metrics, the evaluation method and
conclusions. The report uses the live `POST /v1/route` endpoint and does not
save generated route results as a separate JSON artifact.

The route corridor is controlled by `ROUTING_CORRIDOR_BUFFER_M` in `.env`;
the default is 250 metres. This limits the spatial graph to a useful
alternative-route corridor when the database contains a large OSM import.
