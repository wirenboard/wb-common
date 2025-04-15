import random
import string
from urllib.parse import urlparse

from paho.mqtt import client as _client

DEFAULT_BROKER_URL = "unix:///var/run/mosquitto/mosquitto.sock"


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
        kwargs["client_id"] = self.generate_client_id(client_id_prefix)
        kwargs["transport"] = {"ws": "websockets", "unix": "unix"}.get(self._broker_url.scheme, "tcp")
        kwargs["callback_api_version"] = _client.CallbackAPIVersion.VERSION1
        super().__init__(*args, **kwargs)

    @staticmethod
    def generate_client_id(client_id_prefix: str, suffix_length: int = 8) -> str:
        random_suffix = "".join(random.sample(string.ascii_letters + string.digits, suffix_length))
        return f"{client_id_prefix}-{random_suffix}"

    def start(self) -> None:
        scheme = self._broker_url.scheme

        if self._broker_url.username:
            self.username_pw_set(self._broker_url.username, self._broker_url.password)

        if scheme == "ws" and self._broker_url.path:
            self.ws_set_options(self._broker_url.path)

        if scheme == "unix":
            self.connect(self._broker_url.path)
        elif scheme in ["mqtt-tcp", "tcp", "ws"]:
            if not self._broker_url.port:
                raise Exception("No port specified")  # pylint:disable=broad-exception-raised
            self.connect(self._broker_url.hostname, self._broker_url.port)
        else:
            raise Exception("Unknown mqtt url scheme: " + scheme)  # pylint:disable=broad-exception-raised

        if self._is_threaded:
            self.loop_start()

    def stop(self) -> None:
        if self._is_threaded:
            self.loop_stop()
        self.disconnect()
