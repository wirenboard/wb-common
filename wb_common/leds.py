from __future__ import print_function

SYS_PREFIX = "/sys/class/leds/"


def set_brightness(led, val):
    open(SYS_PREFIX + led + "/brightness", mode="wt", encoding="ascii").write(f"{val}\n")


def set_blink(led, delay_on=100, delay_off=100):
    open(SYS_PREFIX + led + "/trigger", mode="wt", encoding="ascii").write("timer\n")

    open(SYS_PREFIX + led + "/delay_on", mode="wt", encoding="ascii").write(f"{delay_on}\n")
    open(SYS_PREFIX + led + "/delay_off", mode="wt", encoding="ascii").write(f"{delay_off}\n")


def blink_fast(led):
    set_blink(led, 50, 50)
