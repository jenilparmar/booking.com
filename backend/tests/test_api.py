import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.main import create_app
from app.services.importer import import_file
from tests.conftest import FIXTURES

AS_OF = "2026-10-09T12:00:00+11:00"


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def seeded(db: Session) -> Session:
    import_file(
        db,
        "valid.csv",
        (FIXTURES / "valid.csv").read_bytes(),
        now=datetime(2026, 10, 9, tzinfo=UTC),
    )
    rows = [
        {
            "property_id": "venus-surry-hills",
            "source_review_id": f"SYNTH-api-{i}",
            "review_text": text,
            "rating": rating,
            "published_at": f"2026-10-0{d}T10:00:00+11:00",
        }
        for i, (text, rating, d) in enumerate(
            [
                ("Dirty bathroom and rude staff. Awful.", 2, 5),
                ("100% noisy, could hear traffic all night. Terrible.", 3, 6),
                ("Lovely clean room, friendly staff.", 9, 7),
                ("Great location near the station.", 8, 8),
            ]
        )
    ]
    import_file(db, "s.json", json.dumps(rows).encode(), now=datetime(2026, 10, 9, tzinfo=UTC))
    return db


def assert_error(resp, status: int, code: str) -> dict:  # type: ignore[no-untyped-def]
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert "Traceback" not in resp.text and "postgresql" not in resp.text.lower()
    return body["error"]


# ---------------------------------------------------------------- meta


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_openapi_lists_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for p in [
        "/api/health",
        "/api/properties",
        "/api/reviews",
        "/api/reviews/{review_id}",
        "/api/analytics/summary",
        "/api/analytics/properties",
        "/api/analytics/trends",
        "/api/analytics/topics",
        "/api/collection/runs",
        "/api/collection/health",
        "/api/collection/run/{property_id}",
        "/api/import/reviews",
    ]:
        assert p in paths


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    assert_error(client.get("/api/nope"), 404, "not_found")


def test_properties(client: TestClient, seeded: Session) -> None:
    body = client.get("/api/properties").json()
    assert len(body["items"]) == 4
    by = {p["id"]: p for p in body["items"]}
    assert by["venus-surry-hills"]["review_count"] == 5
    assert set(body["data_sources"]) == {"imported", "synthetic"}
    assert body["contains_synthetic"] is True


# ---------------------------------------------------------------- reviews


def test_reviews_default_sort_and_shape(client: TestClient, seeded: Session) -> None:
    body = client.get("/api/reviews").json()
    assert body["total"] == 9 and body["page"] == 1 and body["total_pages"] == 1
    dates = [i["published_at"] for i in body["items"]]
    dated = [d for d in dates if d]
    assert dated == sorted(dated, reverse=True)
    assert dates[-1] is None  # undated last
    item = body["items"][0]
    assert {"property_name", "data_source", "topic_labels", "sentiment_label"} <= set(item)


def test_reviews_combined_filters(client: TestClient, seeded: Session) -> None:
    r = client.get(
        "/api/reviews",
        params={
            "property_ids": "venus-surry-hills",
            "sentiment": "negative",
            "rating_max": 5,
            "topic": "Cleanliness",
        },
    ).json()
    assert r["total"] == 1
    assert r["items"][0]["review_text"].startswith("Dirty bathroom")
    assert r["filters"]["topic"] == "Cleanliness"
    assert r["data_sources"] == ["synthetic"]


def test_reviews_multiple_property_ids(client: TestClient, seeded: Session) -> None:
    a = client.get("/api/reviews?property_ids=olympic-paddington&property_ids=chateau-de-venus")
    b = client.get("/api/reviews?property_ids=olympic-paddington,chateau-de-venus")
    assert a.json()["total"] == b.json()["total"] == 3


def test_reviews_date_range_is_local_and_inclusive(client: TestClient, seeded: Session) -> None:
    r = client.get(
        "/api/reviews", params={"date_from": "2026-10-06", "date_to": "2026-10-06"}
    ).json()
    texts = {i["review_text"][:12] for i in r["items"]}
    # FX-1 (06 Oct 10:00 AEDT), FX-2 (06 Oct 21:30 AEDT), and the "100% noisy" synthetic row.
    assert r["total"] == 3, texts


def test_reviews_search_escapes_wildcards(client: TestClient, seeded: Session) -> None:
    assert client.get("/api/reviews", params={"q": "100%"}).json()["total"] == 1
    assert client.get("/api/reviews", params={"q": "%"}).json()["total"] == 1
    assert client.get("/api/reviews", params={"q": "SPOTLESS"}).json()["total"] == 1
    assert client.get("/api/reviews", params={"q": "_"}).json()["total"] == 0


def test_reviews_rating_filter_excludes_null(client: TestClient, seeded: Session) -> None:
    r = client.get("/api/reviews", params={"rating_min": 1}).json()
    assert all(i["rating"] is not None for i in r["items"])
    assert r["total"] == 8


def test_reviews_pagination_preserves_filters(client: TestClient, seeded: Session) -> None:
    params = {"rating_min": 2, "page_size": 3, "sort": "rating"}
    p1 = client.get("/api/reviews", params={**params, "page": 1}).json()
    p2 = client.get("/api/reviews", params={**params, "page": 2}).json()
    p3 = client.get("/api/reviews", params={**params, "page": 3}).json()
    assert p1["total"] == p2["total"] == p3["total"] == 8
    assert p1["total_pages"] == 3
    assert p1["filters"] == p2["filters"]
    ids = [i["id"] for p in (p1, p2, p3) for i in p["items"]]
    assert len(ids) == len(set(ids)) == 8
    ratings = [i["rating"] for p in (p1, p2, p3) for i in p["items"]]
    assert ratings == sorted(ratings, reverse=True)
    beyond = client.get("/api/reviews", params={**params, "page": 9}).json()
    assert beyond["items"] == [] and beyond["total"] == 8


def test_reviews_sort_oldest(client: TestClient, seeded: Session) -> None:
    items = client.get("/api/reviews", params={"sort": "oldest"}).json()["items"]
    dated = [i["published_at"] for i in items if i["published_at"]]
    assert dated == sorted(dated)


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"rating_min": 0},
        {"rating_max": 11},
        {"rating_min": 8, "rating_max": 3},
        {"sentiment": "angry"},
        {"topic": "Breakfast"},
        {"sort": "random"},
        {"date_from": "not-a-date"},
        {"date_from": "2026-10-09", "date_to": "2026-10-01"},
        {"property_ids": "does-not-exist"},
        {"q": "x" * 201},
    ],
)
def test_reviews_invalid_params_422_envelope(client: TestClient, params: dict) -> None:
    err = assert_error(client.get("/api/reviews", params=params), 422, "validation_error")
    assert isinstance(err["details"], list) and err["details"]
    assert all({"field", "message"} <= set(d) for d in err["details"])


def test_review_detail_and_404(client: TestClient, seeded: Session) -> None:
    first = client.get("/api/reviews").json()["items"][0]
    r = client.get(f"/api/reviews/{first['id']}")
    assert r.status_code == 200 and r.json()["id"] == first["id"]
    assert_error(client.get("/api/reviews/999999"), 404, "not_found")
    assert_error(client.get("/api/reviews/abc"), 422, "validation_error")


# ---------------------------------------------------------------- analytics


def test_analytics_summary(client: TestClient, seeded: Session) -> None:
    body = client.get("/api/analytics/summary", params={"as_of": AS_OF}).json()
    assert body["timezone"] == "Australia/Sydney"
    assert body["current"]["reviews"] == 6
    assert body["current"]["rated_reviews"] == 6  # unrated FX-3 is in the previous week
    assert body["previous"]["reviews"] == 2 and body["previous"]["rated_reviews"] == 1
    assert body["excluded_undated"] == 1
    assert body["contains_synthetic"] is True
    assert body["as_of"].startswith("2026-10-09T01:00:00")


def test_analytics_endpoints_shapes(client: TestClient, seeded: Session) -> None:
    p = client.get("/api/analytics/properties", params={"as_of": AS_OF, "weeks": 2}).json()
    assert len(p["properties"]) == 4 and p["window_weeks"] == 2
    t = client.get("/api/analytics/trends", params={"as_of": AS_OF, "weeks": 3}).json()
    assert len(t["overall"]) == 3 and len(t["by_property"]) == 4
    tp = client.get("/api/analytics/topics", params={"as_of": AS_OF}).json()
    assert tp["cleanliness_share_of_negative"]["negative_reviews"] == tp["negative_reviews"]
    for group in tp["examples"]:
        for ex in group["reviews"]:
            assert ex["data_source"] in {"imported", "synthetic"}


def test_analytics_filter_and_validation(client: TestClient, seeded: Session) -> None:
    body = client.get(
        "/api/analytics/summary", params={"as_of": AS_OF, "property_ids": "olympic-paddington"}
    ).json()
    assert body["current"]["reviews"] == 2
    assert_error(client.get("/api/analytics/trends?weeks=0"), 422, "validation_error")
    assert_error(client.get("/api/analytics/trends?weeks=53"), 422, "validation_error")
    assert_error(client.get("/api/analytics/summary?as_of=yesterday"), 422, "validation_error")


# ---------------------------------------------------------------- import & collection


def test_import_upload_csv(client: TestClient) -> None:
    content = (FIXTURES / "valid.csv").read_bytes()
    r = client.post("/api/import/reviews", files={"file": ("valid.csv", content, "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["inserted"], body["duplicates"], body["invalid"]) == (5, 0, 0)
    assert body["data_sources"] == ["imported"]
    again = client.post("/api/import/reviews", files={"file": ("valid.csv", content, "text/csv")})
    assert (again.json()["inserted"], again.json()["duplicates"]) == (0, 5)
    runs = client.get("/api/collection/runs").json()["items"]
    assert len(runs) == 8 and all(r["status"] == "success" for r in runs)


def test_import_upload_with_row_errors(client: TestClient) -> None:
    content = (FIXTURES / "bad_rows.csv").read_bytes()
    body = client.post(
        "/api/import/reviews", files={"file": ("bad.csv", content, "text/csv")}
    ).json()
    assert body["inserted"] == 1 and body["invalid"] == 7
    assert {"row", "field", "message"} <= set(body["errors"][0])


def test_import_rejects_wrong_type(client: TestClient) -> None:
    assert_error(
        client.post("/api/import/reviews", files={"file": ("x.txt", b"hello", "text/plain")}),
        415,
        "unsupported_file_type",
    )
    assert_error(
        client.post("/api/import/reviews", files={"file": ("x.csv", b"\x89PNG", "image/png")}),
        415,
        "unsupported_media_type",
    )


def test_import_rejects_oversize(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "import_max_bytes", 64)
    err = assert_error(
        client.post(
            "/api/import/reviews",
            files={"file": ("v.csv", (FIXTURES / "valid.csv").read_bytes(), "text/csv")},
        ),
        413,
        "file_too_large",
    )
    assert err["details"]["max_bytes"] == 64


def test_import_rejects_malformed(client: TestClient) -> None:
    assert_error(
        client.post(
            "/api/import/reviews", files={"file": ("x.json", b"{oops", "application/json")}
        ),
        400,
        "malformed_json",
    )


def test_import_requires_file(client: TestClient) -> None:
    assert_error(client.post("/api/import/reviews"), 422, "validation_error")


def test_collection_run_unsupported(client: TestClient) -> None:
    err = assert_error(
        client.post("/api/collection/run/olympic-paddington"), 501, "collection_unsupported"
    )
    assert "Terms of Service" in err["message"]
    assert_error(client.post("/api/collection/run/nope"), 404, "not_found")


def test_collection_health(client: TestClient, seeded: Session) -> None:
    body = client.get("/api/collection/health").json()
    assert body["live_collection_supported"] is False
    assert len(body["properties"]) == 4
    surry = next(p for p in body["properties"] if p["property_id"] == "venus-surry-hills")
    assert surry["latest_run"]["status"] == "success" and surry["last_success_at"]


def test_unhandled_error_is_generic_500(db: Session) -> None:
    app = create_app()

    def boom() -> Session:
        raise RuntimeError("secret connection string postgresql://u:p@h/db")

    app.dependency_overrides[get_db] = boom
    with TestClient(app, raise_server_exceptions=False) as c:
        err = assert_error(c.get("/api/properties"), 500, "internal_error")
    assert "secret" not in json.dumps(err)


def test_cors_headers(client: TestClient) -> None:
    r = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    r = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers
