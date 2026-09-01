import logging
import random
import string
import threading
from urllib.parse import urlparse

from paho.mqtt import client as _client

DEFAULT_BROKER_URL = "unix:///var/run/mosquitto/mosquitto.sock"
CONNECT_RETRY_INTERVAL_S = 1

logger = logging.getLogger(__name__)


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
        self._connect_failure_reported = False
        kwargs["client_id"] = self.generate_client_id(client_id_prefix)
        kwargs["transport"] = {"ws": "websockets", "unix": "unix"}.get(self._broker_url.scheme, "tcp")
        kwargs["callback_api_version"] = _client.CallbackAPIVersion.VERSION1
        super().__init__(*args, **kwargs)
        # Paho stores the callback in an instance attribute named
        # _on_connect_fail, so the handler itself must have a different name.
        self.on_connect_fail = self._handle_connect_fail
        self.reconnect_delay_set(CONNECT_RETRY_INTERVAL_S, CONNECT_RETRY_INTERVAL_S)

    @staticmethod
    def generate_client_id(client_id_prefix: str, suffix_length: int = 8) -> str:
        random_suffix = "".join(random.sample(string.ascii_letters + string.digits, suffix_length))
        return f"{client_id_prefix}-{random_suffix}"

    def start(self) -> None:
        self._stop_requested.clear()
        scheme = self._broker_url.scheme

        if self._broker_url.username:
            self.username_pw_set(self._broker_url.username, self._broker_url.password)

        if scheme == "ws" and self._broker_url.path:
            self.ws_set_options(self._broker_url.path)

        if scheme == "unix":
            host, port = self._broker_url.path, None
        elif scheme in ["mqtt-tcp", "tcp", "ws"]:
            if not self._broker_url.port:
                raise Exception("No port specified")  # pylint:disable=broad-exception-raised
            host, port = self._broker_url.hostname, self._broker_url.port
        else:
            raise Exception("Unknown mqtt url scheme: " + scheme)  # pylint:disable=broad-exception-raised

        if self._is_threaded:
            # loop_start() invokes loop_forever(retry_first_connection=True), so an
            # unavailable broker is retried by Paho's network thread. Keeping the
            # main thread free is important: service signal handlers must remain
            # able to stop a process which has not connected yet.
            self.connect_async(host, port or 1883)
            self.loop_start()
        else:
            self._connect_forever(host, port)

    def _handle_connect_fail(self, _client, _userdata) -> None:
        if not self._connect_failure_reported:
            logger.warning("MQTT broker %s is unreachable, waiting for it", self._broker_url.geturl())
            self._connect_failure_reported = True

    def _connect_forever(self, host, port) -> None:
        reported = False
        while not self._stop_requested.is_set():
            try:
                if port is None:
                    self.connect(host)
                else:
                    self.connect(host, port)
                if reported:
                    logger.info("MQTT broker %s is up, connected", self._broker_url.geturl())
                return
            except OSError as error:
                if not reported:
                    logger.warning(
                        "MQTT broker %s is unreachable (%s), waiting for it",
                        self._broker_url.geturl(),
                        error,
                    )
                    reported = True
                self._stop_requested.wait(CONNECT_RETRY_INTERVAL_S)

    def stop(self) -> None:
        self._stop_requested.set()
        if self._is_threaded:
            self.loop_stop()
        self.disconnect()
