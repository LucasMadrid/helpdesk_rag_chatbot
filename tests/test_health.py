from fastapi.testclient import TestClient

from helpdesk_rag_chatbot.main import create_app


def test_health_endpoint() -> None:
    """Test the /health endpoint."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
