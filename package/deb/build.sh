#!/bin/bash

mv *.deb backup/
version_pyc=$(cat ../../nmd | grep "__version__" | grep -Po '\d.\d.\d')
version_deb=$(cat netmicroscope-daemon/DEBIAN/control| grep "Version:" | grep -Po '\d.\d.\d')
echo "python version:" ${version_pyc}
echo "debian version:" ${version_deb}
#cp ../../cron-netmicroscope-daemon netmicroscope-daemon/etc/cron.d/
cp ../../nmd netmicroscope-daemon/usr/local/src/netmicroscope-daemon/
cp ../../env_template netmicroscope-daemon/usr/local/src/netmicroscope-daemon/
cp ../../appmonitor.py netmicroscope-daemon/usr/local/src/netmicroscope-daemon/
cp -R ../../appmonitor/ netmicroscope-daemon/usr/local/src/netmicroscope-daemon/
cp -R ../../venv/ netmicroscope-daemon/usr/local/src/netmicroscope-daemon/
sed -i 's/'${version_deb}'/'${version_pyc}'/g' netmicroscope-daemon/DEBIAN/control
fakeroot dpkg-deb --build netmicroscope-daemon
mv netmicroscope-daemon.deb netmicroscope-daemon-v${version_pyc}.deb
