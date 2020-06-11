#!/bin/sh
pip install -e /salt
dbus-uuidgen > /var/lib/dbus/machine-id
mkdir -p /var/run/dbus
dbus-daemon --config-file=/usr/share/dbus-1/system.conf
virtlogd -d
libvirtd -d
salt-minion
