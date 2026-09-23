import logging
import random
import string
import threading
from typing import Optional
from urllib.parse import urlparse

from paho.mqtt import client as _client

DEFAULT_BROKER_URL = "unix:///var/run/mosquitto/mosquitto.sock"
CONNECT_RETRY_INTERVAL_S = 1
CONNECTION_POLL_INTERVAL_S = 0.1

logger = logging.getLogger(__name__)


def _without_credentials(broker_url) -> str:
    """
    The broker URL with the userinfo stripped.

    A broker URL may carry a password (wb-mqtt-welrok's config editor asks for
    tcp://user:password@host:1883), and everything logged here ends up in journald and in the
    wb-diag-collect archives customers send to support.
    """
    if broker_url.username:
        netloc = broker_url.hostname or ""
        if broker_url.port is not None:
            netloc = f"{netloc}:{broker_url.port}"
        broker_url = broker_url._replace(netloc=netloc)
    url = broker_url.geturl()
    if broker_url.netloc or not broker_url.path.startswith("/"):
        return url
    return url.replace(":", "://", 1)  # geturl() drops the empty authority of unix:///path


class MQTTClient(_client.Client):
    def __init__(  # pylint:disable=keyword-arg-before-vararg
        self,
        client_id_prefix: str,
        broker_url: str = DEFAULT_BROKER_URL,
        is_threaded: bool = True,
        *args,
        **kwargs,
    ):
        self._broker_url = urlparse(broker_url)
        self._is_threaded = is_threaded
        self._stop_requested = threading.Event()
        self._connect_failure_logged = False
        kwargs["client_id"] = self.generate_client_id(client_id_prefix)
        kwargs["transport"] = {"ws": "websockets", "unix": "unix"}.get(self._broker_url.scheme, "tcp")
        kwargs["callback_api_version"] = _client.CallbackAPIVersion.VERSION1
        super().__init__(*args, **kwargs)
        self.on_connect_fail = self._log_connect_failure

    @staticmethod
    def generate_client_id(client_id_prefix: str, suffix_length: int = 8) -> str:
        random_suffix = "".join(random.sample(string.ascii_letters + string.digits, suffix_length))
        return f"{client_id_prefix}-{random_suffix}"

    def start(self, retry_first_connection: bool = False) -> None:
        """
        Connect to the broker and, for a threaded client, start the network loop.

        By default the connection is made synchronously and an unavailable broker raises,
        which suits one-shot callers. Daemons pass retry_first_connection=True: connection
        attempts are then repeated until the broker answers or stop() is called.

        With retry_first_connection the two client kinds return differently. A threaded client
        hands the attempts to paho's network thread, so start() returns at once and there is no
        connection yet: publish from on_connect, or call wait_for_connection() first, otherwise
        the messages are dropped. A client built with is_threaded=False blocks here until the
        broker answers or stop() is called.
        """
        self._stop_requested.clear()
        self._connect_failure_logged = False
        scheme = self._broker_url.scheme

        if self._broker_url.username:
            self.username_pw_set(self._broker_url.username, self._broker_url.password)

        if scheme == "ws" and self._broker_url.path:
            self.ws_set_options(self._broker_url.path)

        if scheme == "unix":
            host, port = self._broker_url.path, 1883  # port is ignored by the unix transport
        elif scheme in ["mqtt-tcp", "tcp", "ws"]:
            if not self._broker_url.port:
                raise Exception("No port specified")  # pylint:disable=broad-exception-raised
            host, port = self._broker_url.hostname, self._broker_url.port
        else:
            raise Exception("Unknown mqtt url scheme: " + scheme)  # pylint:disable=broad-exception-raised

        if not retry_first_connection:
            self.connect(host, port)
        elif self._is_threaded:
            # loop_start() runs loop_forever(retry_first_connection=True), so the network
            # thread keeps retrying the first connection and the caller is not blocked.
            self.connect_async(host, port)
        else:
            self._connect_until_stopped(host, port)

        if self._is_threaded:
            self.loop_start()

    def stop(self) -> None:
        """
        Stop the network thread first, then disconnect. paho documents the opposite order, but
        this one gives two guarantees the documented one lacks: the thread exits only when the
        outgoing queue is empty, so everything published before stop() reaches the broker, and
        disconnect() without a running thread writes the DISCONNECT synchronously, so paho's
        keepalive check cannot close the socket while the packet is still queued.

        Also cancels a pending first-connection retry and any wait_for_connection(); safe to
        call from another thread.
        """
        self._stop_requested.set()
        if self._is_threaded:
            self.loop_stop()
        self.disconnect()

    def wait_for_connection(self, stop_requested: Optional[threading.Event] = None) -> bool:
        """
        Block until the broker accepts the connection; returns is_connected().

        Meant for a daemon after start(retry_first_connection=True): the network thread retries
        the broker meanwhile, and the daemon gets a live connection before it publishes. The wait
        ends early when stop() is called or when the daemon's own `stop_requested` event is set,
        which is how a rejected login reported to on_connect ends the wait.
        """
        while not self.is_connected() and not self._stop_requested.is_set():
            if stop_requested is not None and stop_requested.wait(CONNECTION_POLL_INTERVAL_S):
                break
            if stop_requested is None:
                self._stop_requested.wait(CONNECTION_POLL_INTERVAL_S)
        return self.is_connected()

    def _connect_until_stopped(self, host: str, port: int) -> None:
        while not self._stop_requested.is_set():
            try:
                self.connect(host, port)
                return
            except OSError:
                self._log_connect_failure(self, None)
                self._stop_requested.wait(CONNECT_RETRY_INTERVAL_S)

    def _log_connect_failure(self, _client, _userdata) -> None:
        if not self._connect_failure_logged:
            logger.warning("MQTT broker %s is unavailable, retrying", _without_credentials(self._broker_url))
            self._connect_failure_logged = True
