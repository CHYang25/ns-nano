# app.py
from flask import Flask, jsonify, abort, send_file, request
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

_engine = None

# a study "mentions" a term if its tf-idf weight is above this (same default as Neurosynth/NiMARE)
TERM_THRESHOLD = 0.001
# a study "reports" a location if it has a peak within this many mm
DEFAULT_RADIUS = 6

TERM_SQL = "SELECT study_id FROM ns.annotations_terms WHERE term = :{p} AND weight > :thr"
LOC_SQL = """
    SELECT study_id FROM ns.coordinates
    WHERE ST_3DDWithin(geom, ST_SetSRID(ST_MakePoint(:{p}x, :{p}y, :{p}z), 4326), :r)
"""

def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("Missing DB_URL (or DATABASE_URL) environment variable.")
    # Normalize old 'postgres://' scheme to 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
    _engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )
    return _engine

def clean_term(term):
    # allow both "posterior cingulate" and "posterior_cingulate" in the url
    return term.replace("_", " ").strip().lower()

def parse_coords(coords):
    try:
        x, y, z = map(float, coords.split("_"))
    except ValueError:
        abort(400, description="coordinates should look like x_y_z, e.g. 0_-52_26")
    return x, y, z

def get_radius():
    return request.args.get("r", DEFAULT_RADIUS, type=float)

def find_studies(id_sql, params):
    # id_sql returns study_ids, attach the study info from metadata
    sql = f"""
        SELECT study_id, title, authors, journal, year
        FROM ns.metadata
        WHERE study_id IN ({id_sql})
        ORDER BY year DESC, study_id
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]

def result(a, b, studies):
    return jsonify({"a": a, "b": b, "count": len(studies), "studies": studies})

def create_app():
    app = Flask(__name__)

    @app.get("/", endpoint="health")
    def health():
        return "<p>Server working!</p>"

    @app.get("/img", endpoint="show_img")
    def show_img():
        return send_file("amygdala.gif", mimetype="image/gif")

    @app.get("/terms/<term>/studies", endpoint="terms_studies")
    def get_studies_by_term(term):
        term = clean_term(term)
        studies = find_studies(TERM_SQL.format(p="a"), {"a": term, "thr": TERM_THRESHOLD})
        return result(term, None, studies)

    @app.get("/locations/<coords>/studies", endpoint="locations_studies")
    def get_studies_by_coordinates(coords):
        x, y, z = parse_coords(coords)
        params = {"ax": x, "ay": y, "az": z, "r": get_radius()}
        studies = find_studies(LOC_SQL.format(p="a"), params)
        return result([x, y, z], None, studies)

    # studies that mention term_a but not term_b
    @app.get("/dissociate/terms/<term_a>/<term_b>", endpoint="dissociate_terms")
    def dissociate_terms(term_a, term_b):
        term_a, term_b = clean_term(term_a), clean_term(term_b)
        id_sql = TERM_SQL.format(p="a") + " EXCEPT " + TERM_SQL.format(p="b")
        params = {"a": term_a, "b": term_b, "thr": TERM_THRESHOLD}
        return result(term_a, term_b, find_studies(id_sql, params))

    # studies that report a peak near coords_a but not near coords_b
    @app.get("/dissociate/locations/<coords_a>/<coords_b>", endpoint="dissociate_locations")
    def dissociate_locations(coords_a, coords_b):
        xa, ya, za = parse_coords(coords_a)
        xb, yb, zb = parse_coords(coords_b)
        id_sql = LOC_SQL.format(p="a") + " EXCEPT " + LOC_SQL.format(p="b")
        params = {"ax": xa, "ay": ya, "az": za,
                  "bx": xb, "by": yb, "bz": zb, "r": get_radius()}
        return result([xa, ya, za], [xb, yb, zb], find_studies(id_sql, params))

    @app.get("/test_db", endpoint="test_db")
    
    def test_db():
        eng = get_engine()
        payload = {"ok": False, "dialect": eng.dialect.name}

        try:
            with eng.begin() as conn:
                # Ensure we are in the correct schema
                conn.execute(text("SET search_path TO ns, public;"))
                payload["version"] = conn.exec_driver_sql("SELECT version()").scalar()

                # Counts
                payload["coordinates_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.coordinates")).scalar()
                payload["metadata_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.metadata")).scalar()
                payload["annotations_terms_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.annotations_terms")).scalar()

                # Samples
                try:
                    rows = conn.execute(text(
                        "SELECT study_id, ST_X(geom) AS x, ST_Y(geom) AS y, ST_Z(geom) AS z FROM ns.coordinates LIMIT 3"
                    )).mappings().all()
                    payload["coordinates_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["coordinates_sample"] = []

                try:
                    # Select a few columns if they exist; otherwise select a generic subset
                    rows = conn.execute(text("SELECT * FROM ns.metadata LIMIT 3")).mappings().all()
                    payload["metadata_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["metadata_sample"] = []

                try:
                    rows = conn.execute(text(
                        "SELECT study_id, contrast_id, term, weight FROM ns.annotations_terms LIMIT 3"
                    )).mappings().all()
                    payload["annotations_terms_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["annotations_terms_sample"] = []

            payload["ok"] = True
            return jsonify(payload), 200

        except Exception as e:
            payload["error"] = str(e)
            return jsonify(payload), 500

    return app

# WSGI entry point (no __main__)
app = create_app()
