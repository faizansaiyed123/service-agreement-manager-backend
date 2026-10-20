from types import SimpleNamespace

import app.core.rate_limit as rate_limit


def test_rate_limiter_bucket_storage_is_bounded(monkeypatch):
    rate_limit.clear_rate_limit_state()
    monkeypatch.setattr(rate_limit, "_MAX_TRACKED_BUCKETS", 5)
    monkeypatch.setattr(rate_limit, "_EVICT_BUCKETS", 2)
    try:
        for index in range(20):
            request = SimpleNamespace(client=SimpleNamespace(host=f"192.0.2.{index}"))
            rate_limit.enforce_rate_limit(
                request, scope="test-ip", limit=50, window_seconds=60
            )
        assert len(rate_limit._attempts) <= 5
    finally:
        rate_limit.clear_rate_limit_state()
