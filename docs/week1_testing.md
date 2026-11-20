# Week 1 Test Plan and Results

Fill in **Actual result** and **Pass/Fail** yourself after running each test.
Nothing here is pre-marked as passed. A test is Pass only if the expected result happened exactly as described.

Notes:
- Outputs are examples; spacing and wording vary across Linux versions.
- Tests T03-T06, T07-T10, T13, T15, T17, T18 need a Linux machine with a working `vcan` module.
- Run commands from the repository root. Use the virtual environment from docs/week1_setup.md if you created one.

## How to check that messages were independently observed

"Transmitted" only means the kernel accepted a frame. Evidence of reception is a **different process** reading it:

1. Start a receiver first (`can_monitor.py`, `can_capture`, or `candump vcan0`).
2. Run the simulator.
3. Run `python3 -m src.utils.compare_logs --config config/config.example.json`. It matches every transmitted (CAN ID, payload) pair in `sender_log.csv` against the monitor's dataset and prints `generated`-side vs `observed`-side counts per ID. `scripts/run_demo.sh` does all three steps.

## Summary table

| ID | Test | Result (Pass / Fail / Not run) |
|----|------|-------------------------------|
| T01 | Python installation | Not run |
| T02 | Required tools and modules available | Not run |
| T03 | vcan0 creation | Not run |
| T04 | Interface status | Not run |
| T05 | Manual message transmission | Not run |
| T06 | Manual message reception | Not run |
| T07 | Simulator startup | Not run |
| T08 | Normal message generation | Not run |
| T09 | Reception by an independent monitor | Not run |
| T10 | Correct CAN ID display | Not run |
| T11 | Correct payload length | Not run |
| T12 | Dataset generation | Not run |
| T13 | Graceful interruption | Not run |
| T14 | Invalid configuration handling | Not run |
| T15 | Missing interface handling | Not run |
| T16 | C program compilation | Not run |
| T17 | C monitor reception | Not run |
| T18 | Shutdown and resource cleanup | Not run |
| T19 | Automated unit tests (extra) | Not run |
| T20 | Dry-run reproducibility (extra) | Not run |

---

## T01 - Python installation

**Purpose:** Confirm a usable Python 3 is installed.

**Prerequisites:** None.

**Steps:**

```bash
python3 --version
```

**Expected result:** Prints `Python 3.8` or newer (3.10+ on Ubuntu 22.04).

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Command not found: `sudo apt install python3`. Version too old: use a newer Ubuntu release or install a newer Python.

---

## T02 - Required tools and modules available

**Purpose:** Confirm every tool the project needs exists, and that Python has SocketCAN support.

**Prerequisites:** Ubuntu/Debian packages installed (see docs/week1_setup.md).

**Steps:**

```bash
python3 -c "import socket; print('AF_CAN:', hasattr(socket, 'AF_CAN'))"
which ip candump cansend gcc make git
python3 -m venv --help > /dev/null && echo "venv OK"
```

**Expected result:** `AF_CAN: True`, and a path printed for each of the six tools, then `venv OK`.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Missing `ip`: `sudo apt install iproute2`. Missing `candump`/`cansend`: `sudo apt install can-utils`. Missing venv: `sudo apt install python3-venv`. `AF_CAN: False` means a non-Linux Python.

---

## T03 - vcan0 creation

**Purpose:** Create the virtual CAN interface.

**Prerequisites:** T02 passed; sudo rights; `vcan` kernel module available (`modinfo vcan`).

**Steps:**

```bash
sudo scripts/setup_vcan.sh up
```

**Expected result:** A line like `vcan0  UNKNOWN  <NOARP,UP,LOWER_UP>` (a vcan interface normally reports state UNKNOWN; that is fine). Exact text varies by Linux version.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** 'could not load the vcan kernel module': see docs/week1_troubleshooting.md, 'Kernel module unavailable'. 'Operation not permitted': run with sudo. 'already exists': the script reuses it.

---

## T04 - Interface status

**Purpose:** Confirm vcan0 exists, is a vcan device, and is up.

**Prerequisites:** T03 done.

**Steps:**

```bash
ip -details link show vcan0
ip -brief link show type vcan
```

**Expected result:** Output contains `vcan` and the flags include `UP`. `ip -brief link show type vcan` lists vcan0.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** 'Device does not exist': repeat T03. Flags show DOWN: `sudo ip link set up vcan0`.

---

## T05 - Manual message transmission

**Purpose:** Send one frame with a standard tool.

**Prerequisites:** T04 passed. Two terminals.

**Steps:**

```bash
# Terminal 1 (start FIRST):
candump vcan0

# Terminal 2:
cansend vcan0 123#DEADBEEF
echo "cansend exit code: $?"
```

**Expected result:** `cansend` prints nothing and exits with code 0.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** 'No such device': vcan0 is missing (T03). 'Network is down': `sudo ip link set up vcan0`. `cansend` not found: install can-utils.

---

## T06 - Manual message reception

**Purpose:** See that frame in the receiver, then confirm several frames work.

**Prerequisites:** T05 steps; Terminal 1 still running candump.

**Steps:**

```bash
# Terminal 2:
cansend vcan0 123#DEADBEEF
for i in 1 2 3 4 5; do cansend vcan0 123#0$i; done
```

**Expected result:** Terminal 1 shows `vcan0  123   [4]  DE AD BE EF` (spacing may differ), then five lines with `[1]  01` ... `05`. Meaning: ID `123`, length 4, payload bytes DE AD BE EF.

**Note:** Do not continue to T07 until T05 and T06 pass.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Nothing shown: the receiver must be running BEFORE you send (candump does not replay history); both terminals must use the same interface name. Confirm with `ip -details link show vcan0`.

---

## T07 - Simulator startup

**Purpose:** Simulator loads the config, validates it and starts.

**Prerequisites:** T04 passed; repo root; run from the repo root.

**Steps:**

```bash
python3 -m src.simulator.normal_traffic_simulator --config config/config.example.json --duration 5
```

**Expected result:** A line `starting: sending on vcan0, 4 message types, seed=42, runtime=5.0s ...`, no ERROR lines, then `Simulation finished (runtime reached).`

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** `No module named src`: you are not in the repo root. `CONFIG ERROR`: read the message; it names the bad setting. `cannot create a CAN socket` or `interface ... does not exist`: see T03/T15.

---

## T08 - Normal message generation

**Purpose:** Frames are generated and accepted by the kernel at the configured rates.

**Prerequisites:** T07.

**Steps:**

```bash
python3 -m src.simulator.normal_traffic_simulator --duration 10
wc -l data/generated/sender_log.csv
head -5 data/generated/sender_log.csv
```

**Expected result:** Summary shows generated == transmitted, failed 0. Roughly 100 frames for 0x100, 50 for 0x200, 20 for 0x300 and 10 for 0x400 (within a few). `sender_log.csv` has one header line plus one line per frame, `status` = `transmitted`.

**Note:** 'transmitted' only means the kernel accepted the frame. T09 is what proves reception.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** failed > 0: read the logged reason (`ip link show vcan0`; interface may be down). Counts far off: the machine was heavily loaded; re-run.

---

## T09 - Reception by an independent monitor

**Purpose:** Prove every transmitted frame was seen by a different process.

**Prerequisites:** T04 passed.

**Steps:**

```bash
scripts/run_demo.sh 10
```

**Expected result:** The compare table ends with `RESULT: every transmitted frame was independently observed.` and the `missing` column is 0 for every ID.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Missing frames: the monitor must start first (the script does this). Monitor exits early: vcan0 not up. `unexpected` > 0: something else is writing to vcan0 (for example a leftover `cangen`).

---

## T10 - Correct CAN ID display

**Purpose:** Monitor shows IDs that match the config and the independent candump tool.

**Prerequisites:** T04 passed. Two terminals.

**Steps:**

```bash
# Terminal 1:
candump vcan0
# Terminal 2:
python3 -m src.capture.can_monitor --config config/config.example.json --count 12
# Terminal 3 (after both are running):
python3 -m src.simulator.normal_traffic_simulator --duration 5
```

**Expected result:** Both programs show only IDs 100, 200, 300, 400 (the monitor prints `0x100` etc.), with ECU/message names next to them.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Different IDs: another source is on vcan0. No names shown: pass `--config`.

---

## T11 - Correct payload length

**Purpose:** dlc is 0-8 and matches the number of payload bytes and the config.

**Prerequisites:** T09 produced data/generated/observed_normal_traffic.csv.

**Steps:**

```bash
python3 - <<'EOF'
import csv, json
cfg = {int(m["can_id"], 0): m["dlc"] for e in json.load(open("config/config.example.json"))["ecus"] for m in e["messages"]}
bad = 0
for r in csv.DictReader(open("data/generated/observed_normal_traffic.csv")):
    ok = int(r["dlc"]) <= 8 and len(r["payload_hex"]) == 2 * int(r["dlc"]) and cfg[int(r["can_id"])] == int(r["dlc"])
    bad += not ok
print("rows with wrong length:", bad)
EOF
```

**Expected result:** `rows with wrong length: 0`.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** KeyError: an ID not in the config appeared (see T10). Nonzero count: save the offending row and investigate.

---

## T12 - Dataset generation

**Purpose:** Both CSV files exist, have the documented header and contain data.

**Prerequisites:** T09.

**Steps:**

```bash
head -3 data/generated/sender_log.csv
head -3 data/generated/observed_normal_traffic.csv
wc -l data/generated/*.csv
```

**Expected result:** Sender header: `timestamp,ecu_name,message_name,can_id,can_id_hex,dlc,payload_hex,interval_s,status,source`. Observed header: `observed_timestamp,can_id,can_id_hex,ecu_name,message_name,dlc,payload_hex,inter_arrival_s,frame_flags,source`. Both have more than one line.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Empty or header-only file: the program stopped before any frame was written; check `logs/*.log`. Missing folder: the programs create it; check permissions.

---

## T13 - Graceful interruption

**Purpose:** Ctrl+C stops both programs cleanly and leaves complete files.

**Prerequisites:** T04 passed.

**Steps:**

```bash
# Terminal 1:
python3 -m src.capture.can_monitor --config config/config.example.json --save --quiet
# Terminal 2:
python3 -m src.simulator.normal_traffic_simulator --duration 60
# After ~5 seconds press Ctrl+C in Terminal 2, then in Terminal 1.
echo "exit code: $?"
tail -2 data/generated/sender_log.csv
```

**Expected result:** Terminal 2 prints `stop requested ... finishing cleanly`, then `Simulation finished (interrupted by user).` with counts. Terminal 1 prints `Monitor stopped (interrupted).` with counts. No Python traceback. The last CSV lines are complete rows.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Traceback on Ctrl+C: record it and report it. The process hangs: press Ctrl+C again, then `pkill -f normal_traffic_simulator`.

---

## T14 - Invalid configuration handling

**Purpose:** A bad config is rejected with a clear message before any socket opens.

**Prerequisites:** None (works without vcan0).

**Steps:**

```bash
sed 's/"0x100"/"0x900"/' config/config.example.json > /tmp/bad_config.json
python3 -m src.simulator.normal_traffic_simulator --config /tmp/bad_config.json --dry-run
echo "exit code: $?"
```

**Expected result:** `CONFIG ERROR: ecus[0].messages[0].can_id: CAN ID 0x900 is outside the 11-bit range 0x000-0x7FF` and `exit code: 2`.

**Note:** Also try `--interface can0`: it must be refused (virtual interfaces only).

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** No error shown: the sed pattern did not match; open the file and check.

---

## T15 - Missing interface handling

**Purpose:** Programs fail clearly, not with a traceback, when vcan0 does not exist.

**Prerequisites:** T03 done, then remove vcan0.

**Steps:**

```bash
sudo scripts/setup_vcan.sh down
python3 -m src.simulator.normal_traffic_simulator --duration 2
echo "exit code: $?"
python3 -m src.capture.can_monitor
echo "exit code: $?"
# recreate it afterwards:
sudo scripts/setup_vcan.sh up
```

**Expected result:** Each program prints an ERROR saying interface 'vcan0' does not exist and suggests `sudo scripts/setup_vcan.sh up`; exit code 1; no traceback.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** `Address family not supported`: your kernel has no CAN support at all (different problem; see troubleshooting).

---

## T16 - C program compilation

**Purpose:** can_capture.c compiles without warnings.

**Prerequisites:** gcc and make installed.

**Steps:**

```bash
make c
ls -l bin/can_capture
```

**Expected result:** The compile line prints with no warnings or errors and `bin/can_capture` exists.

**Note:** Build-sandbox note: compiled cleanly with `-Wall -Wextra` on the author's build machine. Re-run on yours.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** 'linux/can.h: No such file': `sudo apt install linux-libc-dev`. Warnings: record them.

---

## T17 - C monitor reception

**Purpose:** The C program receives simulator frames and saves them.

**Prerequisites:** T04, T16.

**Steps:**

```bash
# Terminal 1:
./bin/can_capture -i vcan0 -o data/generated/observed_c.csv
# Terminal 2:
python3 -m src.simulator.normal_traffic_simulator --duration 5
# Then Ctrl+C in Terminal 1, and compare:
python3 -m src.utils.compare_logs --sent data/generated/sender_log.csv --observed data/generated/observed_c.csv
```

**Expected result:** Terminal 1 prints lines like `12:00:01.123  0x100  [8]  03 52 ...  +100.2ms`; on Ctrl+C it prints `Capture stopped (interrupted)` with counts; compare reports every transmitted frame observed.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** `cannot bind`/`does not exist`: vcan0 missing. No output: start the capture BEFORE the simulator.

---

## T18 - Shutdown and resource cleanup

**Purpose:** No leftover processes, files are closed, vcan0 can be removed cleanly.

**Prerequisites:** T13 or T17 done.

**Steps:**

```bash
pgrep -af 'can_monitor|normal_traffic_simulator|can_capture' || echo "no leftover processes"
tail -1 data/generated/observed_normal_traffic.csv
sudo scripts/setup_vcan.sh down
ip link show vcan0
```

**Expected result:** `no leftover processes`; the CSV's last line is a complete row; `Removed vcan0.`; the last command reports the device does not exist.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Leftover process: `pkill -INT -f <name>` and report why Ctrl+C did not stop it.

---

## T19 - Automated unit tests (extra)

**Purpose:** Config validation, frame packing, payload determinism, dry-run and an in-process pipeline test.

**Prerequisites:** Repo root. No vcan0 needed.

**Steps:**

```bash
make test
```

**Expected result:** `Ran 37 tests ... OK`.

**Note:** Build-sandbox note: 37 tests passed on the author's build machine, which has no CAN support. These tests do not exercise SocketCAN or vcan0.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Import errors: run from the repo root. A failing test: copy its output and investigate before continuing.

---

## T20 - Dry-run reproducibility (extra)

**Purpose:** The same seed produces byte-identical output.

**Prerequisites:** None.

**Steps:**

```bash
python3 -m src.simulator.normal_traffic_simulator --dry-run --duration 3 --output /tmp/a.csv --log-level ERROR
python3 -m src.simulator.normal_traffic_simulator --dry-run --duration 3 --output /tmp/b.csv --log-level ERROR
diff /tmp/a.csv /tmp/b.csv && echo IDENTICAL
diff /tmp/a.csv data/samples/sample_sender_dry_run_seed42.csv && echo "MATCHES SAMPLE"
```

**Expected result:** `IDENTICAL` and `MATCHES SAMPLE`.

**Actual result:** _(fill in after running)_

**Pass/Fail:** [ ] Pass  [ ] Fail  (not yet run)

**Troubleshooting:** Differences: check you did not change the config or seed.

---
