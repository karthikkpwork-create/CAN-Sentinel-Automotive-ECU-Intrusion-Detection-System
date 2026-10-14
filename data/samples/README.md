# Sample data

`sample_sender_dry_run_seed42.csv` was produced by the simulator's **dry-run mode**:

```bash
python3 -m src.simulator.normal_traffic_simulator --dry-run --duration 3 \
  --output data/samples/sample_sender_dry_run_seed42.csv
```

* Config: `config/config.example.json`, seed 42, 3 seconds.
* Nothing was sent on any CAN interface and nothing was observed. These are *generated* records only (`status` = `dry_run`).
* Timestamps use a fixed virtual start time (`1700000000`) so the file is reproducible. Re-running the command should give a byte-identical file (test T20).
* Real captured data (observed by a monitor) belongs in `data/generated/` and is not committed.
