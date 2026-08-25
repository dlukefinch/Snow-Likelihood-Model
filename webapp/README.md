# UK Snow Outlook -- webapp

FastAPI app: serves the reference-station map and a live, exact-location
postcode lookup (real Open-Meteo + model run per postcode, not an
approximation from the nearest fixed station).

The map itself is [MapLibre GL JS](https://maplibre.org/) (loaded from
unpkg's CDN in the page `<head>`) with two free, keyless tile sources:
[OpenFreeMap](https://openfreemap.org/) for the base vector style
(`positron`/`dark`, auto-switching with the visitor's OS theme) and
[AWS's public elevation-tiles-prod bucket](https://registry.opendata.aws/terrain-tiles/)
(terrarium-encoded raster-DEM) for the hillshade layer. Both are free
for any volume of use, no signup required -- no map API key to manage.

## Run locally

```bash
pip install -r requirements.txt
uvicorn webapp.app:app --reload --port 8000
```

Open http://127.0.0.1:8000/

## Deploy on a VPS

1. Clone the repo, create a venv, `pip install -r requirements.txt`.
2. Run behind a process manager, e.g. systemd:

   ```ini
   # /etc/systemd/system/snow-outlook.service
   [Unit]
   Description=UK Snow Outlook
   After=network.target

   [Service]
   User=youruser
   WorkingDirectory=/path/to/snow_likelihood_project
   ExecStart=/path/to/snow_likelihood_project/.venv/bin/uvicorn webapp.app:app --host 127.0.0.1 --port 8000 --workers 1
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

3. Put nginx (or similar) in front for TLS + the public domain, proxying to
   `127.0.0.1:8000`.

## Things to tune for real traffic

- **`STATION_REFRESH_INTERVAL_S`** (app.py) -- how often the 12 fixed
  stations refresh in the background. Each refresh is 12 x up to 5 live
  Open-Meteo calls (60 requests). 30 min is a reasonable default; the
  ensemble endpoint rate-limited us during dev after repeated manual runs,
  so don't set this too aggressively.
- **`POSTCODE_CACHE_TTL_S`** / **`POSTCODE_RATE_LIMIT`** -- per-postcode
  cache (30 min default) and per-IP rate limit (15/hour default) on
  `/api/postcode`. Both are in-memory, per-process. Stick to `--workers 1`
  (above) -- with more than one worker, each gets its own independent cache,
  rate-limit counters, and background station-refresh loop (multiplying
  Open-Meteo load), since nothing is shared across processes. Move to Redis
  first if you need more than one worker.
- Both Open-Meteo and postcodes.io are free, keyless APIs -- be a good
  citizen (the caching/rate-limiting above exists specifically for that).
