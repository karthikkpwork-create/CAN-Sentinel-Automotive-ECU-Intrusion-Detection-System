# Week 1 Troubleshooting Guide

Each entry: **Identify** the cause, **Fix** it, **Verify** the fix. None of these require deleting system files or changing unrelated settings.

## `ip` command missing
Identify: `ip: command not found`. Fix: `sudo apt install iproute2`. Verify: `ip -V`.

## `can-utils` not installed
Identify: `candump: command not found`. Fix: `sudo apt install can-utils`. Verify: `which candump cansend`.

## Python import error (`No module named src` / `No module named ...`)
Identify: the error text. `src` errors mean you are not in the repository root or you ran the file directly. Fix: `cd CAN-Sentinel` and run with `python3 -m src.simulator.normal_traffic_simulator ...` (note `-m` and dots). Verify: `python3 -m src.utils.compare_logs --help` prints usage.

## Virtual environment not activated
Identify: prompt lacks `(.venv)`; `which python3` points to `/usr/bin`. Fix: `source .venv/bin/activate`. Verify: `which python3` shows `.venv`. (Week 1 needs no pip packages, so it will usually still run.)

## `vcan0` not found
Identify: `ip link show vcan0` says "does not exist"; programs say "interface 'vcan0' does not exist". Fix: `sudo scripts/setup_vcan.sh up`. Verify: `ip -brief link show vcan0`. Note: a reboot removes `vcan0`.

## Permission denied / Operation not permitted
Identify: error from `ip link add`, `modprobe` or bind. Fix: creating interfaces needs root: use `sudo` (the script does this). Reading/writing an existing `vcan0` normally needs no root. Verify: re-run the failing command.

## Kernel module unavailable
Identify: `modinfo vcan` says not found, or `modprobe vcan` fails. This is common in containers, restricted VMs and default WSL2 kernels. Fix: use a normal Ubuntu VM or native install (recommended). On Ubuntu, `sudo apt install linux-modules-extra-$(uname -r)` can provide the module if your kernel package split it out. Do not try to patch your kernel as a first step. Verify: `modinfo vcan | head -3` works, then `sudo modprobe vcan && lsmod | grep vcan`.

If programs say `Address family not supported by protocol`, the running kernel has no CAN support at all (not just no `vcan`). Same fix: use a CAN-capable Linux.

## Interface already exists
Identify: `RTNETLINK answers: File exists`. Fix: nothing; just bring it up: `sudo ip link set up vcan0` (the script does this). Verify: `ip -brief link show vcan0`.

## Interface exists but is down
Identify: `Network is down` errors; flags lack `UP`. Fix: `sudo ip link set up vcan0`. Verify: flags include `UP`.

## No messages received
Identify, in order: (1) Was the receiver started **before** sending? (2) Same interface name in both terminals? (3) Is `vcan0` UP? (4) Does `cansend vcan0 123#DEADBEEF` exit 0? Fix: start the receiver first; correct the name; bring the interface up. Verify: `candump vcan0` in one terminal and `cansend` in another shows the frame.

## Invalid CAN ID
Identify: `CONFIG ERROR ... outside the 11-bit range` or `cansend` complaining about the frame. Fix: use IDs `0x000`-`0x7FF` (at most 3 hex digits for `cansend`). Verify: `--dry-run` starts without a config error.

## Payload too long
Identify: `dlc ... out of range` or `payload is N bytes`. Fix: Classical CAN allows at most 8 bytes; reduce `dlc` and move signals. Verify: dry-run starts.

## Python simulator exits unexpectedly
Identify: the last ERROR line, and `logs/simulator.log` (it contains DEBUG detail). Common causes: interface missing/down (50 consecutive send failures abort with a clear message), unwritable output path. Fix: address the message. Verify: `python3 -m src.simulator.normal_traffic_simulator --duration 3`.

## C compilation error
Identify: the first error line. `linux/can.h: No such file or directory`: `sudo apt install linux-libc-dev`. `gcc: command not found`: `sudo apt install build-essential`. Verify: `make c` completes and `bin/can_capture` exists.

## Missing libpcap headers
Week 1 does not use libpcap. If you experiment with it: `sudo apt install libpcap-dev`. Verify: `pcap-config --version`.

## Capture method incompatible with the interface
Identify: a tool (for example a libpcap-based one) reports it cannot open `vcan0`, or sees no frames. Fix: use the SocketCAN-based tools provided here (`can_monitor.py`, `can_capture`, `candump`). Verify: the same traffic is visible with `candump vcan0`.

## Empty or incomplete log/CSV file
Identify: `wc -l` shows only the header; or the last line is cut off. Causes: no frames arrived (monitor started late or wrong interface), or the process was killed with `kill -9`/power loss before flushing. Fix: start the monitor first; stop with Ctrl+C or `kill -INT`, not `kill -9`. Rows are flushed every 20 frames and on exit. Verify: `tail -2 file.csv` shows full rows.

## Application interrupted without clean shutdown
Identify: Python traceback on Ctrl+C, or `pgrep -af 'can_monitor|normal_traffic|can_capture'` still lists processes. Fix: `pkill -INT -f <name>` and wait a second; only then `pkill -f <name>`. Report any traceback as a bug. Verify: `pgrep` prints nothing and the CSV ends in a complete row.
