from api import ratelimit


def test_consume_blocks_after_limit():
    key = "test:limit"
    ratelimit._WINDOWS.pop(key, None)

    assert ratelimit._consume(key, 2, 60) is True
    assert ratelimit._consume(key, 2, 60) is True
    assert ratelimit._consume(key, 2, 60) is False


def test_consume_resets_after_window(monkeypatch):
    key = "test:window"
    ratelimit._WINDOWS.pop(key, None)
    clock = {"now": 1000.0}
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock["now"])

    assert ratelimit._consume(key, 1, 10) is True
    assert ratelimit._consume(key, 1, 10) is False

    clock["now"] += 11
    assert ratelimit._consume(key, 1, 10) is True
