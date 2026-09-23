# Tests

Run from the repository root:

```sh
python3 -m pytest tests/
```

Needs `python3-paho-mqtt` and `python3-pytest`; no broker, controller or hardware is
required. Paho's network calls are mocked, only `MQTTClient` logic is exercised.
The Debian build runs the same suite through pybuild.

## Coverage

`test_mqtt_client.py` — `wb_common/mqtt_client.py`:

| Test | Verifies |
| --- | --- |
| `test_start_connects_synchronously_by_default` | `start()` keeps the synchronous `connect()` + `loop_start()` sequence |
| `test_start_raises_when_broker_unavailable_by_default` | one-shot callers still get an exception when the broker is down |
| `test_threaded_retry_leaves_connecting_to_network_loop` | `retry_first_connection=True` uses `connect_async()` so paho's thread retries; tcp and unix URLs |
| `test_unthreaded_retry_is_interrupted_by_stop` | non-threaded retry loop exits on `stop()`, logs the unavailable broker once and never the credentials from its URL |
| `test_wait_for_connection_returns_once_connected` | returns True as soon as the broker accepts the connection |
| `test_wait_for_connection_gives_up_on_the_daemon_stop_event` | a never-connecting client (rejected login) ends the wait with False on the daemon's own event |
| `test_wait_for_connection_gives_up_on_stop` | `stop()` ends the wait with False |
| `test_stop_stops_the_loop_before_disconnecting` | `stop()` calls `loop_stop()` before `disconnect()` |
