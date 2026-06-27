from app.request_utils import client_ip


def _make_request(headers=None):
    """Минимальный объект Request-подобной заглушки для client_ip."""
    class _Req:
        def __init__(self, h):
            self.headers = h or {}
            self.client = None
    return _Req(headers or {})


def test_client_ip_from_x_forwarded_for():
    req = _make_request({"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
    assert client_ip(req) == "203.0.113.5"


def test_client_ip_from_x_real_ip():
    req = _make_request({"x-real-ip": "198.51.100.7"})
    assert client_ip(req) == "198.51.100.7"


def test_client_ip_x_forwarded_for_takes_priority_over_x_real_ip():
    req = _make_request({"x-forwarded-for": "203.0.113.5", "x-real-ip": "198.51.100.7"})
    assert client_ip(req) == "203.0.113.5"


def test_client_ip_fallback_to_client_host():
    class _Req:
        headers = {}
        client = type("C", (), {"host": "192.0.2.1"})()
    assert client_ip(_Req()) == "192.0.2.1"


def test_client_ip_fallback_to_zero_when_nothing():
    assert client_ip(_make_request()) == "0.0.0.0"
