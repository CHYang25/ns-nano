# Neurosynth Backend

A lightweight Flask backend that exposes **functional dissociation** endpoints on top of a Neurosynth-backed PostgreSQL database.

The service provides two APIs that return studies mentioning one concept/coordinate **but not** the other (A \ B). You can also query the opposite direction (B \ A).

---

## HW8 notes

What I implemented on top of the template:

- `/terms/<term>/studies` and `/locations/<x_y_z>/studies` now actually query the database.
- `/dissociate/terms/<term_a>/<term_b>`: studies with `term_a` minus studies with `term_b`, done with SQL `EXCEPT`. A study counts as mentioning a term if its tf-idf weight is > 0.001 (Neurosynth's default).
- `/dissociate/locations/<x1_y1_z1>/<x2_y2_z2>`: same idea, but a study counts for a location if it has a peak within 6 mm (PostGIS `ST_3DDWithin`). Radius can be changed with `?r=10`.
- Every endpoint returns `{"a", "b", "count", "studies": [{study_id, title, authors, journal, year}]}`. Terms can use spaces or `_`.
- Fixed `create_db.py`: term columns are named like `terms_abstract_tfidf__amygdala`, and the old regex didn't strip the prefix, so term lookups returned nothing.
- Pinned `SQLAlchemy<2.1`, because 2.1 uses psycopg 3 by default for `postgresql://` URLs and the code here uses psycopg2.

Sanity checks (local PostGIS, same data): `amygdala` gives 1579 studies (same number as neurosynth.org), PCC \ vmPFC = 897, vmPFC \ PCC = 283, `0_-52_26` \ `-2_50_-6` = 406, `-2_50_-6` \ `0_-52_26` = 424.

---

## Table of Contents

- [Endpoints](#endpoints)
  - [Dissociate by terms](#dissociate-by-terms)
  - [Dissociate by MNI coordinates](#dissociate-by-mni-coordinates)
- [Quick Start](#quick-start)
  - [1) Provision PostgreSQL](#1-provision-postgresql)
  - [2) Verify the connection](#2-verify-the-connection)
  - [3) Populate the database](#3-populate-the-database)
  - [4) Run the Flask service](#4-run-the-flask-service)
  - [5) Smoke tests](#5-smoke-tests)
- [Environment Variables](#environment-variables)
- [Example Requests](#example-requests)
- [Requirements](#requirements)
- [Notes](#notes)
- [License](#license)

---

## Endpoints

### Dissociate by terms

```
GET /dissociate/terms/<term_a>/<term_b>
```

Returns studies that mention **`term_a`** but **not** `term_b`.

**Examples**

```
/dissociate/terms/posterior cingulate/ventromedial prefrontal
/dissociate/terms/ventromedial prefrontal/posterior cingulate
```

---

### Dissociate by MNI coordinates

```
GET /dissociate/locations/<x1_y1_z1>/<x2_y2_z2>
```

Coordinates are passed as `x_y_z` (underscores, not commas).  
Returns studies that mention **`[x1, y1, z1]`** but **not** `[x2, y2, z2]`.

**Default Mode Network test case**

```
/dissociate/locations/0_-52_26/-2_50_-6
/dissociate/locations/-2_50_-6/0_-52_26
```

> Tip: You may design a single endpoint that returns **both directions** in one response (A–B **and** B–A) if that better suits your client.

---

## Quick Start

### 1) Provision PostgreSQL

Create a PostgreSQL database (e.g., on Render).

### 2) Verify the connection

```bash
python check_db.py --url "postgresql://<USER>:<PASSWORD>@<HOST>:5432/<DBNAME>"
```

### 3) Populate the database

```bash
python create_db.py --url "postgresql://<USER>:<PASSWORD>@<HOST>:5432/<DBNAME>"
```

### 4) Run the Flask service

Deploy `app.py` as a Web Service (e.g., on Render) and set the environment variable:

- `DB_URL=postgresql://<USER>:<PASSWORD>@<HOST>:5432/<DBNAME>`

Use a production server such as Gunicorn as your start command:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

### 5) Smoke tests

After deployment, check the basic endpoints:

- Images: `https://<your-app>.onrender.com/img`
- DB connectivity: `https://<your-app>.onrender.com/test_db`

---

## Environment Variables

- **`DB_URL`** – Full PostgreSQL connection string used by the app.  
  Example: `postgresql://<USER>:<PASSWORD>@<HOST>:5432/<DBNAME>`

> **Security note:** Never commit real credentials to version control. Use environment variables or your hosting provider’s secret manager.

---

## Example Requests

**By terms**

```bash
curl https://<your-app>.onrender.com/dissociate/terms/posterior cingulate/ventromedial prefrontal
curl https://<your-app>.onrender.com/dissociate/terms/ventromedial prefrontal/posterior cingulate
```

**By coordinates**

```bash
curl https://<your-app>.onrender.com/dissociate/locations/0_-52_26/-2_50_-6
curl https://<your-app>.onrender.com/dissociate/locations/-2_50_-6/0_-52_26
```

---

## Requirements

- Python 3.10+
- PostgreSQL 12+
- Python dependencies (typical):
  - `Flask`
  - `SQLAlchemy`
  - PostgreSQL driver (e.g., `psycopg2-binary`)
  - Production WSGI server (e.g., `gunicorn`)

---

## Notes

- Path parameters use underscores (`_`) between coordinates: `x_y_z`.
- Term strings should be URL-safe (e.g., `posterior cingulate`, `ventromedial prefrontal`). Replace spaces with underscores on the client if needed.
- The term/coordinate pairs above illustrate a **Default Mode Network** dissociation example. Adjust for your analysis.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
