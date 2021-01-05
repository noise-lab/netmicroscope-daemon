# [NetMicroscope Daemon](https://github.com/noise-lab/netmicroscope-daemon/)
NetMicroscope Backend Integration Daemon (Linux).

## 1. [NetMicroscope](https://netmicroscope.com)

About the NetMicroscope (NM for short): A Modularized Network Traffic Analyzer

### 1.1 Standard Application

NM can provide granular information about the traffic flowing from network devices to known applications and services. This is the standard built-in capability provided by the NM software. 
NM enables network operators to determine degradations in application quality as they happen, even when the traffic is encrypted.

![NetMicroscope Timeseries Congested Segment Example](https://github.com/noise-lab/netmicroscope-daemon/blob/master/docs/images/nm_congested_segment2.png?raw=true)

<!--[![NetMicroscope Real-Time Monitoring](https://img.youtube.com/vi/ix5GTHW4D3U/0.jpg)](https://www.youtube.com/watch?v=ix5GTHW4D3U)-->

<p align="center">
  <a href="https://www.youtube.com/watch?v=ix5GTHW4D3U"><img width="720" height="460" src="https://img.youtube.com/vi/ix5GTHW4D3U/0.jpg"></a>
</p>

### 1.2 Extended Applications

#### 1.2.1 Video Performace Monitoring

Network Microscope's ML Video Performace Inference Module is capable of inferring video streaming quality metrics in real time, such as startup delay or video resolution, by using just a handful of features extracted from passive traffic measurement. NM passively collects a corpus of network features about the traffic flows of interest in the network and directs those to a real-time analytics framework that can perform more complex inference tasks.

* Inferring Streaming Video Quality from Encrypted Traffic: Practical Models and Deployment Experience<br>
*F. Bronzino\*, P. Schmitt\*, S.Ayoubi, G. Martins, R. Teixeira, N. Feamster (\*Co-First Authors).*<br>
Proceedings of the ACM on Measurement and Analysis of Computing Systems (POMACS) and at ACM Sigmetrics 2020, Boston, USA, June 8-12, 2020.

![Video Inference](https://github.com/noise-lab/netmicroscope-daemon/blob/master/docs/images/nmcharts.png?raw=true)

#### 1.2.2 IoT Monitoring & Automation
TBD
#### 1.2.3 Network Security and DPI (Deep Packet Inspection)
TBD

### 1.3 Hardware Schematics

![NetMicroscope Hardware Schematics](https://github.com/noise-lab/netmicroscope-daemon/blob/master/docs/images/schematic_mirror_mode2.png?raw=true)

#### Install from .deb package (recommended). ####

1. download ```netmicroscope-daemon-v0.9.9.deb```
2. run ```sudo dpkg -i netmicroscope-daemon-v0.9.9.deb```
3. edit .env file and rename to <br>
```
cd /usr/local/src/netmicroscope-daemon/
vim env_template
mv env_template .env
```
4. run ```sudo nmd restart```
5. run ```tail -f /tmp/appmonitor.log``` and expect to see "OKs". <br>
That means data is being ingested into influxdb
```
2020-08-21T17:53:02.713 INFO {appmonitor} [printF] TAHandler /tmp/tmp.ta.743143071 is running.
2020-08-21T17:53:05.272 INFO {appmonitor} [printF] Unknown-192.168.XXX.XXX {'KbpsDw': 0.6875, 'KbpsUp': 0.65625, 'TsEnd': 1598050385}
2020-08-21T17:53:05.295 INFO {appmonitor} [printF] OK
2020-08-21T17:53:10.257 INFO {appmonitor} [printF] Unknown-192.168.XXX.XXX {'KbpsDw': 11.86875, 'KbpsUp': 10.7921875, 'TsEnd': 1598050390}
2020-08-21T17:53:10.289 INFO {appmonitor} [printF] OK
```

#### Manual installation from GitHub ####

```
sudo apt-get install python3-venv python3-dev -y
python3 -m venv venv
source venv/bin/activate
python3 -m pip install wheel
python3 -m pip install -r requirements.txt
```

#### Manual Crontab Setup ####

```
@reboot root cd /home/<user>/netmicroscope-daemon; sleep 30; ./nm.sh >/tmp/nm.sh.log 2>&1
```

where <b>nm.sh</b> should look like:
```
#!/bin/bash

## run netmicroscope
cd nm/src/github.com/noise-lab/netmicroscope/cmd/netmicroscope
./nm #netmicroscope binary with default nmconfig

## activate env 
cd -
cd nm/netmicroscope-daemon/
. venv/bin/activate

## run daemon as root (check /tmp/appmonitor.log for messages)
./nmd start

```

example named ```cron-netmicroscope``` can be used to start-up netmicroscope separated from the daemon.
