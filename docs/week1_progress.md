# Week 1 Progress Tracker

Update this as you work. A box is checked only when **you** have actually done and verified the item. Items marked "built" below refer to code that exists in this repo; "run by me" is about your own machine.

## Checklist

| # | Task | Built in repo | Run/verified by me | Notes |
|---|------|:---:|:---:|------|
| 1 | Development environment identified | n/a | [ ] | |
| 2 | Required software installed | n/a | [ ] | |
| 3 | Python virtual environment configured | n/a | [ ] | |
| 4 | CAN fundamentals understood (`docs/week1_fundamentals.md`) | [x] | [ ] | |
| 5 | `vcan0` created and verified | [x] script | [ ] | |
| 6 | Manual frame transmission works | n/a | [ ] | |
| 7 | Manual frame reception works | n/a | [ ] | |
| 8 | Python normal traffic simulator runs | [x] | [ ] | |
| 9 | Normal frames independently observed (`compare_logs`) | [x] | [ ] | |
| 10 | CAN IDs and payloads displayed correctly | [x] | [ ] | |
| 11 | Dataset / logs saved | [x] | [ ] | |
| 12 | Python monitor handles interruption | [x] | [ ] | |
| 13 | C capture implemented and tested | [x] | [ ] | |
| 14 | Error handling tested | [x] | [ ] | |
| 15 | README and setup documentation | [x] | [ ] reviewed | |
| 16 | Git repository has meaningful Week 1 commits | n/a | [ ] | |
| 17 | Week 1 summary updated with real results | template | [ ] | |

## Automated checks done while building the repo (NOT on a real vcan0)

* `make test`: 37 unit/in-process tests passed on a machine with no CAN support.
* `make c`: C program compiled with `-Wall -Wextra`, no warnings.
* Dry run: output byte-identical across two runs with the same seed.
* Error handling for bad config, refused non-virtual interface, and "no CAN support" confirmed from the command line.

These do **not** replace tests T03-T10, T13, T15, T17, T18 in `week1_testing.md`.

## Issues encountered
_(none recorded yet; add date, symptom, cause, fix)_

## Optional experiment
_(libpcap/tcpdump on vcan0, if you try it: record the command and what you saw)_

## Remaining work
* Run the manual test and the full test plan on your Linux machine; record results.
* Commit and push (`docs/week1_git.md`).
* Fill in `docs/week1_summary.md` with real results.
