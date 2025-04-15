#!/usr/bin/env python

from setuptools import find_packages, setup


def get_version():
    with open("debian/changelog", "r", encoding="utf-8") as f:
        return f.readline().split()[1][1:-1].split("~")[0]


setup(
    name="wb_common",
    version=get_version(),
    author="Evgeny Boger",
    maintainer="Wiren Board Team",
    maintainer_email="info@wirenboard.com",
    description="Common Python library for Wiren Board",
    license="MIT",
    url="https://github.com/wirenboard/wb-common",
    packages=find_packages(),
)
