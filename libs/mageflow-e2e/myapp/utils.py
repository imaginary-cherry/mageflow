import base64
import json


# Provide default environment variables so the module can be imported in
# development and test environments that don't have a live Hatchet server.
# In production, set HATCHET_CLIENT_TOKEN to a real token instead.
def _make_dev_token() -> str:
    """Build a minimal JWT-shaped token with local server addresses."""
    claims = {
        "sub": "dev-tenant",
        "server_url": "http://localhost:8080",
        "grpc_broadcast_address": "localhost:7070",
    }
    header = (
        base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    )
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"{header}.{payload}.dev"
