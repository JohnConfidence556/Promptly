from app.services import progress


def test_emit_without_a_sink_does_nothing():
    progress.emit({"kind": "file"})


def test_emit_reaches_the_installed_sink_and_stops_after_reset():
    received = []

    token = progress.set_sink(received.append)
    progress.emit({"kind": "waiting"})
    progress.reset_sink(token)
    progress.emit({"kind": "ignored"})

    assert received == [{"kind": "waiting"}]