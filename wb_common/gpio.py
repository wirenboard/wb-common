from __future__ import print_function

import select
import threading
from collections import defaultdict


class GPIOHandler:
    IN = "in"
    OUT = "out"
    RISING = "rising"
    FALLING = "falling"
    BOTH = "both"
    NONE = "none"

    HIGH = True
    LOW = False

    def __init__(self):
        self.event_callbacks = {}
        self.gpio_fds = {}

        self.epoll = select.epoll()

        self.polling_thread = threading.Thread(target=self.gpio_polling_thread)
        self.polling_thread.daemon = True
        self.polling_thread.start()

        self.gpio_first_event_fired = defaultdict(lambda: False)

    def gpio_polling_thread(self):
        while True:  # pylint:disable=too-many-nested-blocks
            events = self.epoll.poll()
            for fileno, _event in events:
                for gpio, fd in self.gpio_fds.items():
                    if fileno == fd.fileno():
                        if self.gpio_first_event_fired[gpio]:
                            # ~ print "fire callback"
                            cb = self.event_callbacks.get(gpio)
                            if cb is not None:
                                cb(gpio)
                        else:
                            self.gpio_first_event_fired[gpio] = True

    def export(self, gpio):
        with open("/sys/class/gpio/export", mode="wt", encoding="ascii") as file:
            file.write(f"{gpio}\n")

    def unexport(self, gpio):
        with open("/sys/class/gpio/unexport", mode="wt", encoding="ascii") as file:
            file.write(f"{gpio}\n")

    def setup(self, gpio, direction):
        self.export(gpio)
        with open(f"/sys/class/gpio/gpio{gpio}/direction", mode="wt", encoding="ascii") as file:
            file.write(f"{direction}\n")

    def _open(self, gpio):
        fd = open(  # pylint:disable=consider-using-with
            f"/sys/class/gpio/gpio{gpio}/value", mode="r+", encoding="ascii"
        )
        self.gpio_fds[gpio] = fd

    def _check_open(self, gpio):
        if gpio not in self.gpio_fds:
            self._open(gpio)

    def output(self, gpio, value):
        self._check_open(gpio)

        self.gpio_fds[gpio].seek(0)
        self.gpio_fds[gpio].write("1" if value else "0")
        self.gpio_fds[gpio].flush()

    def input(self, gpio):
        self._check_open(gpio)

        self.gpio_fds[gpio].seek(0)
        val = self.gpio_fds[gpio].read().strip()
        return val != "0"

    def request_gpio_interrupt(self, gpio, edge):
        with open(f"/sys/class/gpio/gpio{gpio}/edge", mode="wt", encoding="ascii") as file:
            file.write(f"{edge}\n")
        self._check_open(gpio)

    def add_event_detect(self, gpio, edge, callback):
        self.request_gpio_interrupt(gpio, edge)

        already_present = gpio in self.event_callbacks
        self.event_callbacks[gpio] = callback
        if not already_present:
            self.gpio_first_event_fired[gpio] = False
            self.epoll.register(self.gpio_fds[gpio], select.EPOLLIN | select.EPOLLET)

    def remove_event_detect(self, gpio):
        self.request_gpio_interrupt(gpio, self.NONE)
        ret = self.event_callbacks.pop(gpio, None)

        if ret is not None:
            self.epoll.unregister(self.gpio_fds[gpio])

    def wait_for_edge(self, gpio, edge, timeout=None):
        if timeout is None:
            timeout = 1e100

        event = threading.Event()
        event.clear()

        self.add_event_detect(gpio, edge, lambda x: event.set())
        # ~ print "wait for edge..."
        ret = event.wait(timeout)
        # ~ print "wait for edge done"
        self.remove_event_detect(gpio)

        return ret

    # ~ self.irq_gpio, GPIO.RISING, callback=self.interruptHandler)


GPIO = GPIOHandler()
