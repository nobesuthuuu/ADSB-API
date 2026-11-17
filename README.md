# ADSB API (Flask + MySQL)

A Flask web service over the `class_datapoints` ADSB table.

## Files
| File | Purpose |
|---|---|
| `app.py` | The API (all endpoints, auth, logging) |
| `test_client.py` | Test client that calls every endpoint, including error cases |
| `setup_db.py` | One-time creation of `ngwenyn_auth` and `ngwenyn_api_logs`, registers key `123` |
| `config.yml` | DB credentials + table prefix (`username`) |

## Run
```bash
pip install flask pymysql pyyaml requests
python setup_db.py      # once
python app.py           # server on http://127.0.0.1:5000
python test_client.py   # in a second terminal
```

## Auth and logging
- Every request needs `key`. The key is checked against `ngwenyan_auth`, and only `123` is registered. A bad or missing key returns HTTP 401 with `code: 0`.
- Every request, successful or not, is written to `ngwenyan_api_logs` (time, endpoint, key, query params, code, msg, sqltime, client IP).

## Endpoints
| Endpoint | Params | Notes |
|---|---|---|
| `GET /getData` | `key`, `start`, `end` (required) | Datapoints between the two dates, LIMIT 500 |
| `GET /countInPolygon` | `key`, `polygon` (`lon lat,lon lat,...`) | Count of points inside the polygon. The ring is closed automatically |
| `GET /getAvgSpeedByFlight` | `key`, `start`, `end` (both optional) | Average ground speed per flight, LIMIT 500 |

Dates use the format `YYYY-MM-DD HH:MM:SS`.

## Response JSON schemas

### Common fields (every response, including errors)
```json
{
  "type": "object",
  "required": ["code", "msg", "req", "sqltime"],
  "properties": {
    "code":    {"type": "integer", "enum": [0, 1], "description": "1 = success, 0 = failed"},
    "msg":     {"type": "string",  "description": "'ok' or the reason the request failed"},
    "req":     {"type": "string",  "description": "Endpoint requested"},
    "sqltime": {"type": "number",  "description": "Seconds the SQL query took (time.time())"}
  }
}
```

### /getData
```json
{
  "type": "object",
  "required": ["code", "msg", "req", "sqltime", "start", "end", "num_results", "results"],
  "properties": {
    "code": {"const": 1}, "msg": {"type": "string"}, "req": {"const": "getData"}, "sqltime": {"type": "number"},
    "start": {"type": "string", "format": "YYYY-MM-DD HH:MM:SS"},
    "end":   {"type": "string", "format": "YYYY-MM-DD HH:MM:SS"},
    "num_results": {"type": "integer", "maximum": 500},
    "results": {
      "type": "array", "maxItems": 500,
      "items": {
        "type": "object",
        "properties": {
          "dpid": {"type": "integer"}, "date_time": {"type": "string"}, "hex": {"type": "string"},
          "flight_num": {"type": "string"}, "squawk": {"type": ["integer", "null"]},
          "lat": {"type": "number"}, "lon": {"type": "number"}, "fid": {"type": "integer"},
          "gs": {"type": "number"}, "alt_gps": {"type": ["integer", "null"]},
          "alt_baro": {"type": ["integer", "null"]}, "cat": {"type": ["string", "null"]},
          "track": {"type": ["number", "null"]}, "nav_heading": {"type": ["number", "null"]}
        }
      }
    }
  }
}
```

### /countInPolygon
```json
{
  "type": "object",
  "required": ["code", "msg", "req", "sqltime", "polygon", "count"],
  "properties": {
    "code": {"const": 1}, "msg": {"type": "string"}, "req": {"const": "countInPolygon"}, "sqltime": {"type": "number"},
    "polygon": {"type": "array", "minItems": 4,
                "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}},
    "count": {"type": "integer", "minimum": 0}
  }
}
```

### /getAvgSpeedByFlight
```json
{
  "type": "object",
  "required": ["code", "msg", "req", "sqltime", "start", "end", "num_results", "results"],
  "properties": {
    "code": {"const": 1}, "msg": {"type": "string"}, "req": {"const": "getAvgSpeedByFlight"}, "sqltime": {"type": "number"},
    "start": {"type": ["string", "null"]},
    "end":   {"type": ["string", "null"]},
    "num_results": {"type": "integer", "maximum": 500},
    "results": {
      "type": "array", "maxItems": 500,
      "items": {
        "type": "object",
        "required": ["flight_num", "avg_speed", "num_points"],
        "properties": {
          "flight_num": {"type": "string"},
          "avg_speed":  {"type": "number", "description": "AVG(gs) in knots, rounded to 2 dp"},
          "num_points": {"type": "integer"}
        }
      }
    }
  }
}
```

### Example
`GET /countInPolygon?key=123&polygon=-74 42,-75 39,-74 41,-74 42`
```json
{
    "code": 1,
    "msg": "ok",
    "req": "countInPolygon",
    "sqltime": 5.94,
    "polygon": [[-74.0, 42.0], [-75.0, 39.0], [-74.0, 41.0], [-74.0, 42.0]],
    "count": 9368
}
```
