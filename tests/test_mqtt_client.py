import logging
import threading
from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from wb_common.mqtt_client import MQTTClient, without_credentials


def test_start_connects_synchronously_by_default():
    client = MQTTClient("test", "tcp://localhost:1883")

    with patch.object(client, "connect") as connect, patch.object(client, "loop_start") as loop_start:
        client.start()

    connect.assert_called_once_with("localhost", 1883)
    loop_start.assert_called_once_with()


def test_start_raises_when_broker_unavailable_by_default():
    client = MQTTClient("test", "tcp://localhost:1883")

    with (
        patch.object(client, "connect", side_effect=ConnectionRefusedError),
        patch.object(client, "loop_start"),
        pytest.raises(ConnectionRefusedError),
    ):
        client.start()


@pytest.mark.parametrize(
    "broker_url, expected_target",
    [
        ("tcp://localhost:1883", ("localhost", 1883)),
        ("unix:///tmp/mosquitto.sock", ("/tmp/mosquitto.sock", 1883)),
    ],
)
def test_threaded_retry_leaves_connecting_to_network_loop(broker_url, expected_target):
    client = MQTTClient("test", broker_url)

    with (
        patch.object(client, "connect") as connect,
        patch.object(client, "connect_async") as connect_async,
        patch.object(client, "loop_start") as loop_start,
    ):
        client.start(retry_first_connection=True)

    connect.assert_not_called()
    connect_async.assert_called_once_with(*expected_target)
    loop_start.assert_called_once_with()


def test_wait_for_connection_returns_once_connected():
    client = MQTTClient("test", "tcp://localhost:1883")

    # two polls while connecting, then connected (the last answer is the return value)
    with patch.object(client, "is_connected", side_effect=[False, False, True, True]):
        assert client.wait_for_connection() is True


def test_wait_for_connection_gives_up_on_the_daemon_stop_event():
    """
    A rejected login never connects: the daemon's on_connect sets its stop event and the wait
    ends with False instead of spinning forever.
    """
    client = MQTTClient("test", "tcp://localhost:1883")
    stop_requested = threading.Event()
    threading.Timer(0.05, stop_requested.set).start()

    with patch.object(client, "is_connected", return_value=False):
        assert client.wait_for_connection(stop_requested) is False


def test_wait_for_connection_gives_up_on_stop():
    client = MQTTClient("test", "tcp://localhost:1883")

    with (
        patch.object(client, "is_connected", return_value=False),
        patch.object(client, "loop_stop"),
        patch.object(client, "disconnect"),
    ):
        threading.Timer(0.05, client.stop).start()
        assert client.wait_for_connection() is False


def test_stop_stops_the_loop_before_disconnecting():
    """The order matters: see MQTTClient.stop()"""
    client = MQTTClient("test", "tcp://localhost:1883")
    calls = []

    with (
        patch.object(client, "loop_stop", side_effect=lambda: calls.append("loop_stop")),
        patch.object(client, "disconnect", side_effect=lambda: calls.append("disconnect")),
    ):
        client.stop()

    assert calls == ["loop_stop", "disconnect"]


@pytest.mark.parametrize(
    "broker_url, expected_log",
    [
        ("tcp://localhost:1883", "MQTT broker tcp://localhost:1883 is unavailable, retrying"),
        (
            "tcp://user:s3cr3t@broker.example.com:1883",
            "MQTT broker tcp://broker.example.com:1883 is unavailable, retrying",
        ),
    ],
    ids=["plain-url", "credentials-are-kept-out-of-the-journal"],
)
def test_unthreaded_retry_is_interrupted_by_stop(caplog, broker_url, expected_log):
    client = MQTTClient("test", broker_url, is_threaded=False)
    connect_attempted = threading.Event()

    def refuse(*_args):
        connect_attempted.set()
        raise ConnectionRefusedError

    with (
        patch.object(client, "connect", side_effect=refuse),
        patch.object(client, "disconnect"),
        caplog.at_level(logging.WARNING, logger="wb_common.mqtt_client"),
    ):
        starter = threading.Thread(target=client.start, kwargs={"retry_first_connection": True})
        starter.start()
        assert connect_attempted.wait(1)
        client.stop()
        starter.join(2)

    assert not starter.is_alive()
    assert [record.getMessage() for record in caplog.records] == [expected_log]


@pytest.mark.parametrize(
    "broker_url, expected",
    [
        ("tcp://user:s3cr3t@broker.example.com:1883", "tcp://broker.example.com:1883"),
        ("tcp://user:s3cr3t@broker.example.com", "tcp://broker.example.com"),
        ("tcp://broker.example.com:1883", "tcp://broker.example.com:1883"),
        ("unix:///var/run/mosquitto/mosquitto.sock", "unix:///var/run/mosquitto/mosquitto.sock"),
    ],
    ids=["with-port", "without-port", "no-credentials-is-kept-as-is", "unix-keeps-its-slashes"],
)
def test_without_credentials(broker_url, expected):
    assert without_credentials(urlparse(broker_url)) == expected
