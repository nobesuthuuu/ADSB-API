"""
Test client for the ADSB API. Start the server first (python app.py), then:
    python test_client.py
"""
import requests

BASE = "http://127.0.0.1:5000"
passed = failed = 0


def check(name, endpoint, params, expect_code):
    global passed, failed
    r = requests.get(BASE + endpoint, params=params)
    resp = r.json()
    ok = resp.get("code") == expect_code and all(k in resp for k in ("code", "msg", "req", "sqltime"))
    passed += ok
    failed += not ok
    extra = ""
    if "num_results" in resp:
        extra = f"num_results={resp['num_results']}"
    elif "count" in resp:
        extra = f"count={resp['count']}"
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: HTTP {r.status_code}, code={resp.get('code')}, "
          f"msg='{resp.get('msg')}', sqltime={resp.get('sqltime', 0):.4f}s {extra}")
    return resp


# --- auth
check("bad key", "/getData", {"key": "1234", "start": "2022-11-23 05:28:10", "end": "2022-11-23 05:28:15"}, 0)
check("missing key", "/getData", {"start": "2022-11-23 05:28:10", "end": "2022-11-23 05:28:15"}, 0)

# --- getData
resp = check("getData", "/getData", {"key": "123", "start": "2022-11-23 05:28:10", "end": "2022-11-23 05:28:15"}, 1)
if resp.get("results"):
    print("      first row:", resp["results"][0])
check("getData missing end", "/getData", {"key": "123", "start": "2022-11-23 05:28:10"}, 0)
check("getData bad date", "/getData", {"key": "123", "start": "yesterday", "end": "2022-11-23 05:28:15"}, 0)

# --- countInPolygon
check("countInPolygon", "/countInPolygon", {"key": "123", "polygon": "-74 42,-75 39,-74 41,-74 42"}, 1)
check("countInPolygon bad polygon", "/countInPolygon", {"key": "123", "polygon": "abc"}, 0)
check("countInPolygon missing", "/countInPolygon", {"key": "123"}, 0)

# --- getAvgSpeedByFlight
resp = check("avgSpeed with dates", "/getAvgSpeedByFlight",
             {"key": "123", "start": "2022-11-23 05:00:00", "end": "2022-11-23 08:00:00"}, 1)
if resp.get("results"):
    print("      first 3:", resp["results"][:3])
check("avgSpeed no dates", "/getAvgSpeedByFlight", {"key": "123"}, 1)
check("avgSpeed start only", "/getAvgSpeedByFlight", {"key": "123", "start": "2022-11-23 05:00:00"}, 1)

print(f"\n{passed} passed, {failed} failed")
