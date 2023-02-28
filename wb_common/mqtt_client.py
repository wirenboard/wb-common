import random
import string
from urllib.parse import urlparse

import paho_socket


class MQTTClient(paho_socket.Client):
    def __init__(self, client_id_prefix: str, broker_url: str = "unix:///var/run/mosquitto/mosquitto.sock"):
        self._broker_url = urlparse(broker_url)
        client_id = self.generate_client_id(client_id_prefix)
        transport = "websockets" if self._broker_url.scheme == "ws" else "tcp"
        super().__init__(client_id=client_id, transport=transport)

    @staticmethod
    def generate_client_id(client_id_prefix: str, suffix_length: int = 8) -> str:
        random_suffix = "".join(random.sample(string.ascii_letters + string.digits, suffix_length))
        return "%s-%s" % (client_id_prefix, random_suffix)

    def connect(self) -> None:
        scheme = self._broker_url.scheme
        if scheme == "unix":
            self.sock_connect(self._broker_url.path)
        elif scheme in ["mqtt-tcp", "tcp"]:
            if self._broker_url.username:
                self.username_pw_set(self._broker_url.username, self._broker_url.password)
            super().connect(self._broker_url.hostname, self._broker_url.port)
        elif scheme == "ws":
            if self._broker_url.path:
                self.ws_set_options(self._broker_url.path)
            super().connect(self._broker_url.hostname, self._broker_url.port)
        else:
            raise Exception("Unkown mqtt url scheme: " + scheme)

        self.loop_start()

    def disconnect(self) -> None:
        self.loop_stop()
        super().disconnect()
