# netmicroscope-daemon
NetMicroscope Backend Integration Agent (linux daemon).

#### Install from GitHub ####

```
sudo apt-get install python3-venv python3-dev -y
python3 -m venv venv
source venv/bin/activate
python3 -m pip install wheel
python3 -m pip install -r requirements.txt
```

#### Crontab Setup ####

```
@reboot root cd /home/<user>/netmicroscope-daemon; sleep 30; ./nm.sh >/tmp/nm.sh.log 2>&1
```

where nm.sh should look like:
```
#!/bin/bash

## run netmicroscope
cd nm/src/github.com/noise-lab/netmicroscope/cmd/netmicroscope
./nm #netmicrscipe binary with default nmconfig

## activate env 
cd -
cd nm/netmicroscope-daemon/
. venv/bin/activate

## run daemon as root (check /tmp/appmonitor.log for messages)
./nmd start

```
