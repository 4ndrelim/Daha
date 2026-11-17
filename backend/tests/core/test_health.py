from app.main import app


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_every_contract_endpoint_exists(client):
    """PLAN.md §7.3: every endpoint is registered (as a stub until its milestone lands)."""
    paths = app.openapi()["paths"]
    ops = {(m.upper(), p) for p, methods in paths.items() for m in methods}
    expected = {
        ("GET", "/api/health"),
        ("POST", "/api/auth/signup"),
        ("POST", "/api/auth/login"),
        ("GET", "/api/auth/demo-users"),
        ("POST", "/api/auth/demo-login"),
        ("GET", "/api/me"),
        ("PATCH", "/api/me"),
        ("GET", "/api/users/{user_id}"),
        ("GET", "/api/users/{user_id}/items"),
        ("GET", "/api/users/{user_id}/reviews"),
        ("GET", "/api/communities"),
        ("POST", "/api/communities"),
        ("GET", "/api/communities/{id_or_slug}"),
        ("POST", "/api/communities/{community_id}/join"),
        ("POST", "/api/communities/{community_id}/leave"),
        ("GET", "/api/communities/{community_id}/members"),
        ("GET", "/api/places"),
        ("POST", "/api/uploads"),
        ("POST", "/api/items"),
        ("POST", "/api/items/batch"),
        ("GET", "/api/items/{item_id}"),
        ("PATCH", "/api/items/{item_id}"),
        ("DELETE", "/api/items/{item_id}"),
        ("GET", "/api/me/items"),
        ("POST", "/api/items/{item_id}/borrow"),
        ("POST", "/api/requests"),
        ("GET", "/api/requests/{request_id}"),
        ("PATCH", "/api/requests/{request_id}"),
        ("GET", "/api/me/requests"),
        ("POST", "/api/requests/{request_id}/offers"),
        ("GET", "/api/transactions"),
        ("GET", "/api/transactions/{transaction_id}"),
        ("POST", "/api/transactions/{transaction_id}/actions"),
        ("POST", "/api/transactions/{transaction_id}/review"),
        ("GET", "/api/conversations"),
        ("POST", "/api/conversations"),
        ("GET", "/api/conversations/{conversation_id}"),
        ("GET", "/api/conversations/{conversation_id}/messages"),
        ("POST", "/api/conversations/{conversation_id}/messages"),
        ("POST", "/api/conversations/{conversation_id}/read"),
        ("GET", "/api/notifications"),
        ("GET", "/api/notifications/unread-count"),
        ("POST", "/api/notifications/read"),
        ("POST", "/api/events"),
        ("GET", "/api/search"),
        ("GET", "/api/feed/home"),
        ("GET", "/api/communities/{community_id}/feed"),
        ("GET", "/api/requests/{request_id}/matches"),
        ("GET", "/api/me/fulfillable"),
        ("POST", "/api/ai/parse-request"),
        ("POST", "/api/scans"),
        ("GET", "/api/scans/{scan_id}"),
        ("POST", "/api/scans/{scan_id}/publish"),
    }
    assert expected <= ops, f"missing: {sorted(expected - ops)}"
