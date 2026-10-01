## Wiren Board Python common library and helpers

### MQTTClient

`MQTTClient.start()` connects synchronously and raises if the broker is unavailable, which suits
one-shot tools. A long-running service calls `start(retry_first_connection=True)`: connection
attempts are repeated until the broker answers or `stop()` is called. For the default threaded
client the attempts run in paho's network thread, so `start()` returns before there is a
connection; the service does its subscriptions and publications in `on_connect`, which also covers
reconnects after a broker restart.

A service that publishes from its own loop instead calls `wait_for_connection(stop_requested)`
after `start()`: it blocks until the broker accepts the connection, `stop()` is called or the
service's own stop event is set (a rejected login reported to `on_connect`), and returns whether
the connection is up. Publishing before either of those is in place drops the messages. Clear your
retained topics before calling `stop()`.
