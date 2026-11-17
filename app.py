
import datetime
import decimal
import json
import time

import pymysql
import yaml
from flask import Flask, Response, request

app = Flask(__name__)

with open("config.yml", "r") as file:
    config = yaml.safe_load(file)
db_config = config["mysql"]
U = config["username"]
AUTH_TABLE = f"{U}_auth"
LOG_TABLE = f"{U}_api_logs"
DT_FORMAT = "%Y-%m-%d %H:%M:%S"
LIMIT = 500


# helper functions
def get_conn():
    return pymysql.connect(**db_config)


def to_json(obj):
    """json.dumps that understands datetime / Decimal from MySQL."""
    def default(o):
        if isinstance(o, datetime.datetime):
            return o.strftime(DT_FORMAT)
        if isinstance(o, decimal.Decimal):
            return float(o)
        return str(o)
    return json.dumps(obj, indent=4, default=default)


def auth(token):
    """True if the key exists in my auth table."""
    if not token:
        return False
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM `{AUTH_TABLE}` WHERE `token` = %s", (token,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def log(endpoint, res):
    """Write one row per request to my log table. Never breaks the request."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO `{LOG_TABLE}` "
                "(`dt`,`endpoint`,`token`,`params`,`code`,`msg`,`sqltime`,`ip`) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    datetime.datetime.now().strftime(DT_FORMAT),
                    endpoint,
                    request.args.get("key"),
                    json.dumps(request.args.to_dict()),
                    res.get("code"),
                    str(res.get("msg"))[:255],
                    res.get("sqltime"),
                    request.remote_addr,
                ),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print("logging failed:", e)


def respond(endpoint, res, status=200):
    log(endpoint, res)
    return Response(to_json(res), status=status, mimetype="application/json")


def fail(endpoint, msg, status=400):
    res = {"code": 0, "msg": msg, "req": endpoint, "sqltime": 0}
    return respond(endpoint, res, status)


def parse_dt(value):
    """Return a datetime or None if missing/invalid."""
    try:
        return datetime.datetime.strptime(value.strip(), DT_FORMAT)
    except (AttributeError, ValueError):
        return None


def check_key(endpoint):
    """Returns an error Response if the key is bad, otherwise None."""
    if not auth(request.args.get("key")):
        return fail(endpoint, "auth error: invalid or missing key", 401)
    return None


def run_query(sql, params):
    """Runs a query, returns (rows, seconds_taken)."""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            t0 = time.time()
            cur.execute(sql, params)
            rows = cur.fetchall()
            return rows, time.time() - t0
    finally:
        conn.close()


# endpoints
@app.route("/", methods=["GET"])
def root():
    res = {
        "code": 0,
        "msg": "No endpoint specified. Use /getData, /countInPolygon or /getAvgSpeedByFlight",
        "req": "/",
        "sqltime": 0,
    }
    return respond("/", res, 404)


@app.route("/getData", methods=["GET"])
def get_data():
    ep = "getData"
    err = check_key(ep)
    if err:
        return err

    start = parse_dt(request.args.get("start"))
    end = parse_dt(request.args.get("end"))
    if start is None or end is None:
        return fail(ep, f"start and end are required, format YYYY-MM-DD HH:MM:SS")
    if start > end:
        return fail(ep, "start must be before end")

    sql = (
        "SELECT `dpid`,`date_time`,`hex`,`flight_num`,`squawk`,`lat`,`lon`,`fid`,"
        "`gs`,`alt_gps`,`alt_baro`,`cat`,`track`,`nav_heading` "
        "FROM `class_datapoints` WHERE `date_time` BETWEEN %s AND %s "
        f"ORDER BY `date_time` LIMIT {LIMIT}"
    )
    try:
        rows, sqltime = run_query(sql, (start, end))
    except Exception as e:
        return fail(ep, f"database error: {e}", 500)

    res = {
        "code": 1,
        "msg": "ok",
        "req": ep,
        "sqltime": sqltime,
        "start": start.strftime(DT_FORMAT),
        "end": end.strftime(DT_FORMAT),
        "num_results": len(rows),
        "results": rows,
    }
    return respond(ep, res)


@app.route("/countInPolygon", methods=["GET"])
def count_in_polygon():
    ep = "countInPolygon"
    err = check_key(ep)
    if err:
        return err

    raw = request.args.get("polygon")
    if not raw:
        return fail(ep, "polygon is required, e.g. polygon=-74 42,-75 39,-74 41,-74 42")

    # parse "x y,x y,..." into floats (this also avoids SQL injection)
    points = []
    try:
        for pair in raw.split(","):
            x, y = pair.split()
            points.append((float(x), float(y)))
    except ValueError:
        return fail(ep, "polygon must be a list of 'lon lat' pairs separated by commas")

    if points[0] != points[-1]:
        points.append(points[0])  # close the ring automatically
    if len(points) < 4:
        return fail(ep, "polygon needs at least 3 distinct points")

    wkt = "POLYGON((" + ",".join(f"{x} {y}" for x, y in points) + "))"
    sql = (
        "SELECT COUNT(*) AS cnt FROM `class_datapoints` "
        "WHERE ST_Within(`geo_point`, ST_GeomFromText(%s, 0))"
    )
    try:
        rows, sqltime = run_query(sql, (wkt,))
    except Exception as e:
        return fail(ep, f"database error: {e}", 500)

    res = {
        "code": 1,
        "msg": "ok",
        "req": ep,
        "sqltime": sqltime,
        "polygon": [[x, y] for x, y in points],
        "count": rows[0]["cnt"],
    }
    return respond(ep, res)


@app.route("/getAvgSpeedByFlight", methods=["GET"])
def get_avg_speed_by_flight():
    ep = "getAvgSpeedByFlight"
    err = check_key(ep)
    if err:
        return err

    start_raw = request.args.get("start")
    end_raw = request.args.get("end")
    start = parse_dt(start_raw) if start_raw else None
    end = parse_dt(end_raw) if end_raw else None
    if (start_raw and start is None) or (end_raw and end is None):
        return fail(ep, f"start/end must use format YYYY-MM-DD HH:MM:SS")
    if start and end and start > end:
        return fail(ep, "start must be before end")

    where, params = [], []
    if start:
        where.append("`date_time` >= %s")
        params.append(start)
    if end:
        where.append("`date_time` <= %s")
        params.append(end)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = (
        "SELECT `flight_num`, AVG(`gs`) AS avg_gs, COUNT(*) AS num_points "
        f"FROM `class_datapoints` {where_sql} "
        f"GROUP BY `flight_num` ORDER BY `flight_num` LIMIT {LIMIT}"
    )
    try:
        rows, sqltime = run_query(sql, params)
    except Exception as e:
        return fail(ep, f"database error: {e}", 500)

    results = [
        {
            "flight_num": r["flight_num"],
            "avg_speed": round(float(r["avg_gs"]), 2),
            "num_points": r["num_points"],
        }
        for r in rows
    ]
    res = {
        "code": 1,
        "msg": "ok",
        "req": ep,
        "sqltime": sqltime,
        "start": start.strftime(DT_FORMAT) if start else None,
        "end": end.strftime(DT_FORMAT) if end else None,
        "num_results": len(results),
        "results": results,
    }
    return respond(ep, res)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
