import logging
import threading
from unittest.mock import patch

from wb_common.mqtt_client import MQTTClient


def test_threaded_start_uses_nonblocking_connection():
    client = MQTTClient("test", "tcp://localhost:1883")

    with patch.object(client, "connect_async") as connect_async, patch.object(
        client, "loop_start"
    ) as loop_start:
        client.start()

    connect_async.assert_called_once_with("localhost", 1883)
    loop_start.assert_called_once_with()


def test_threaded_connection_failure_is_reported_once(caplog):
    client = MQTTClient("test", "tcp://localhost:1883")
    callback = client.on_connect_fail
    assert callback is not None

    with caplog.at_level(logging.WARNING, logger="wb_common.mqtt_client"):
        callback(client, None)
        callback(client, None)

    records = [record for record in caplog.records if record.name == "wb_common.mqtt_client"]
    assert len(records) == 1
    assert records[0].message == "MQTT broker tcp://localhost:1883 is unreachable, waiting for it"


def test_non_threaded_initial_connection_can_be_stopped():
    client = MQTTClient("test", "tcp://localhost:1883", is_threaded=False)
    connect_attempted = threading.Event()

    def unavailable(*_args):
        connect_attempted.set()
        raise ConnectionRefusedError

    with patch.object(client, "connect", side_effect=unavailable):
        thread = threading.Thread(target=client.start)
        thread.start()
        assert connect_attempted.wait(1)
        client.stop()
        thread.join(2)

    assert not thread.is_alive()


def test_threaded_stop_disconnects_before_stopping_loop():
    client = MQTTClient("test", "tcp://localhost:1883")
    calls = []

    with patch.object(client, "disconnect", side_effect=lambda: calls.append("disconnect")), patch.object(
        client, "loop_stop", side_effect=lambda: calls.append("loop_stop")
    ):
        client.stop()

    assert calls == ["disconnect", "loop_stop"]
