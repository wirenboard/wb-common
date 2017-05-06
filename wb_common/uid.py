from __future__ import print_function
import re
import os

# get_mac() has been moved to test_suite, because it uses wb-gen-serial,
# which depends on this (wb-common) package (avoid circular dependency)


def get_cpuinfo_serial():
    data = open('/proc/cpuinfo').read()
    matches = re.findall('^Serial\s+: ([0-9a-f]+)$', data, re.M)
    if len(matches) > 0:
        return matches[0]
    return None


def get_mmc_serial():
    mmc_prefix = '/sys/class/mmc_host/mmc0/'
    if os.path.exists(mmc_prefix):
        for entry in os.listdir(mmc_prefix):
            if entry.startswith('mmc'):
                serial_fname = mmc_prefix + entry + '/serial'
                if os.path.exists(serial_fname):
                    serial = open(serial_fname).read().strip()
                    if serial.startswith('0x'):
                        serial = serial[2:]
                    return serial
    return None

def get_eth_mac(num = 0):
    netdev_path = os.path.realpath("/sys/class/net/eth" + str(num))
    of_node_path = os.path.realpath(netdev_path + "/../../of_node")

    mac_path = of_node_path + "/local-mac-address"
    if os.path.exists(mac_path):
        mac = bytearray(open(mac_path).read(6))
        return ''.join(map(lambda b: format(b, "02x"), mac))

    return None

if __name__ == '__main__':
    print("/proc/cpuinfo serial: ", get_cpuinfo_serial())
    #print "WB serial (eth mac): ", get_mac()
