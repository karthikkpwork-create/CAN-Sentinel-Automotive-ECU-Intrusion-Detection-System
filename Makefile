CC      ?= gcc
CFLAGS  ?= -Wall -Wextra -O2 -std=gnu11
PYTHON  ?= python3

.PHONY: all c test dry-run clean

all: c

c: bin/can_capture

bin/can_capture: c_src/can_capture.c
	mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $<

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

dry-run:
	$(PYTHON) -m src.simulator.normal_traffic_simulator --dry-run --duration 3 --output data/generated/dry_run.csv

clean:
	rm -rf bin
