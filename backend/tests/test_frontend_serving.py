from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_backend_serves_built_frontend_and_keeps_api(monkeypatch, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    icons = dist / "icons"
    assets.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)

    (dist / "index.html").write_text("<!doctype html><html><body>Asya Frontend</body></html>", encoding="utf-8")
    (dist / "manifest.webmanifest").write_text('{"name":"Asya"}', encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (dist / "sitemap.xml").write_text(
        "<?xml version='1.0' encoding='UTF-8'?><urlset></urlset>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (icons / "asya-icon.svg").write_text("<svg></svg>", encoding="utf-8")

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVE_FRONTEND", "true")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(dist))
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        root = client.get("/")
        assert root.status_code == 200
        assert "Asya Frontend" in root.text

        request_access = client.get("/request-access")
        assert request_access.status_code == 200
        assert "Asya Frontend" in request_access.text

        privacy = client.get("/privacy")
        assert privacy.status_code == 200
        assert "Asya Frontend" in privacy.text

        terms = client.get("/terms")
        assert terms.status_code == 200
        assert "Asya Frontend" in terms.text

        data_policy = client.get("/data-policy")
        assert data_policy.status_code == 200
        assert "Asya Frontend" in data_policy.text

        manifest = client.get("/manifest.webmanifest")
        assert manifest.status_code == 200
        assert manifest.json()["name"] == "Asya"

        robots = client.get("/robots.txt")
        assert robots.status_code == 200

        sitemap = client.get("/sitemap.xml")
        assert sitemap.status_code == 200

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200

        spa_fallback = client.get("/chat")
        assert spa_fallback.status_code == 200
        assert "Asya Frontend" in spa_fallback.text

        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
    finally:
        get_settings.cache_clear()
