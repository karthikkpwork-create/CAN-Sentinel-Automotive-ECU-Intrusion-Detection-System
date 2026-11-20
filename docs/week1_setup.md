# Week 1 Setup Guide

> **Verification status:** The code and unit tests were checked on a build machine that has **no CAN kernel support**, so the `vcan0` steps below have **not** been run by the author. Treat expected outputs as typical examples; they vary by Linux version. Record your own results in `docs/week1_testing.md`.

## 1. Identify your environment

```bash
cat /etc/os-release       # distribution and version (Ubuntu 22.04 / 24.04 recommended)
uname -r                  # kernel version
python3 --version         # 3.8 or newer
id; sudo -v && echo "sudo OK"
systemd-detect-virt       # prints 'none' on bare metal, otherwise vm/container type
grep -qi microsoft /proc/version && echo "WSL detected"
```
* **Windows:** use an Ubuntu VM (VirtualBox/VMware). A PowerShell window cannot run SocketCAN. Default WSL2 kernels often lack `vcan`.
* **Container/Docker:** usually cannot load kernel modules; use a VM instead.

## 2. Check SocketCAN support

```bash
modinfo vcan | head -3       # module exists for this kernel? (error = unavailable)
lsmod | grep -E "^(can|vcan)"   # empty is fine before first use
```
If `modinfo` says the module is not found, see troubleshooting ("Kernel module unavailable").

## 3. Install packages

```bash
sudo apt update
sudo apt install -y build-essential git python3 python3-venv iproute2 can-utils linux-libc-dev
```

| Package | Why |
|---|---|
| `build-essential` | GCC and `make` (C program, Makefile) |
| `git` | version control |
| `python3`, `python3-venv` | the simulator/monitor and virtual environments |
| `iproute2` | the `ip` command that creates/inspects `vcan0` |
| `can-utils` | `candump`, `cansend`, `cangen`, manual tests |
| `linux-libc-dev` | kernel headers (`linux/can.h`) for the C program |

libpcap (`libpcap-dev`) is **not** installed: Week 1 does not use it (see fundamentals doc).

Check:
```bash
gcc --version | head -1; make --version | head -1; git --version
which ip candump cansend
```

## 4. Python virtual environment

```bash
cd CAN-Sentinel
python3 -m venv .venv
source .venv/bin/activate       # prompt shows (.venv); leave with: deactivate
pip install -r requirements.txt # Week 1 has no third-party packages
python3 -c "import socket; print(hasattr(socket,'AF_CAN'))"   # expect True
```
Run commands as a normal user inside the venv. Where `sudo` is needed (creating `vcan0`) the scripts call it themselves.

## 5. Virtual CAN interface (manual commands)

`scripts/setup_vcan.sh up` does all of this, but here is what each command does:

```bash
ip -brief link show                 # 1. list interfaces
modinfo vcan | head -3              # 2. is SocketCAN's vcan driver available?
sudo modprobe vcan                  # 3. load the driver (needs it to exist)
sudo ip link add dev vcan0 type vcan  # 4. create the virtual interface
sudo ip link set up vcan0           # 5. bring it up
ip -brief link show vcan0           # 6. verify; typical: vcan0  UNKNOWN  <NOARP,UP,LOWER_UP>
ip -details link show vcan0         # 7. details; should mention 'vcan'
sudo ip link set down vcan0         # 8. take it down...
sudo ip link delete vcan0           #    ...and remove it
```
`ip link add` fails with "File exists" if it is already created; that is harmless. State `UNKNOWN` is normal for vcan.

## 6. Manual CAN test (do this before the simulator)

Terminal 1 (receiver, start first):
```bash
candump vcan0
```
Terminal 2 (sender):
```bash
cansend vcan0 123#DEADBEEF
for i in 1 2 3 4 5; do cansend vcan0 123#0$i; done
```
Terminal 1 should show `vcan0  123   [4]  DE AD BE EF` and then five more lines. If nothing appears, see troubleshooting ("No messages received"). Do not continue until this works.

## 7. Configuration reference (`config/config.example.json`)

Copy to `config/config.json` for personal changes (git-ignored) and pass `--config config/config.json`.

| Setting | Meaning | Allowed / default |
|---|---|---|
| `interface` | virtual CAN interface | `vcan0`..`vcan999` only; `vcan0` |
| `runtime_seconds` | how long the simulator runs | 0.1-86400; 30 |
| `random_seed` | seed for reproducible payloads and timing | integer ≥ 0; 42 |
| `rate_scale` | speeds up (>1) or slows (<1) all messages | 0.1-10; 1.0 |
| `jitter_percent` | random ± variation in each interval | 0-20; 2.0 |
| `log_level` | console verbosity (the log file always records DEBUG) | DEBUG/INFO/WARNING/ERROR |
| `log_file` / `monitor_log_file` | rotating log files | `logs/simulator.log`, `logs/monitor.log` |
| `sender_log_path` | simulator CSV | `data/generated/sender_log.csv` |
| `observed_dataset_path` | monitor CSV used with `--save` | `data/generated/observed_normal_traffic.csv` |
| `ecus[].name` | synthetic ECU identity | unique string |
| `messages[].name` | synthetic message name | string |
| `messages[].can_id` | 11-bit ID, `"0x100"` or number | 0x000-0x7FF, unique |
| `messages[].interval_ms` | nominal period | 1-60000 |
| `messages[].dlc` | payload bytes | 0-8 |
| `messages[].counter_byte` | byte holding a rolling 0-255 counter (optional) | inside `dlc` |
| `signals[]` | `name, start_byte, size (1-2), initial, min, max, max_step`: a value stored big-endian that changes by at most `max_step` each message | must fit inside `dlc`, no overlapping bytes |

The config is validated before anything starts; errors name the exact setting.

## 8. Run

```bash
# Simulator (needs vcan0 up)
python3 -m src.simulator.normal_traffic_simulator --config config/config.example.json --duration 10
# Python monitor
python3 -m src.capture.can_monitor --config config/config.example.json --save
# C monitor
make c && ./bin/can_capture -i vcan0 -o data/generated/observed_c.csv
# Everything in one go
scripts/run_demo.sh 10
```
Always start the monitor **before** the simulator; a receiver cannot see frames sent before it was listening.

Why plain `socket.AF_CAN` instead of `python-can`/`cangen`? It needs no installs, is part of Python on Linux, and the sender is isolated in one small class (`SocketCanSender`) so the traffic source can be swapped later.
