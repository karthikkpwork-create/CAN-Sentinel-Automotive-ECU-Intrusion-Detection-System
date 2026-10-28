"""Simple rule-based detector for virtual CAN frames."""

import time


def parse_data(text):
    """Convert '11 22 AA' into [17, 34, 170]."""
    try:
        return [int(value, 16) for value in str(text).split()]
    except ValueError:
        return []


class RuleDetector:
    def __init__(self, cooldown=2.0):
        self.mode = "off"
        self.cooldown = cooldown
        self.reset()

    def reset(self):
        self.stats = {}
        self.mean_interval = {}
        self.last_ts = {}
        self.last_seen = {}
        self.last_alert = {}
        self.unknown_reported = set()
        self.missing_reported = set()

    def start_learning(self):
        self.reset()
        self.mode = "learning"

    def finish_learning(self):
        """Finish learning normal traffic and enable detection."""
        if not self.stats:
            return False

        for can_id, stats in self.stats.items():
            if stats["count"] >= 3:
                self.mean_interval[can_id] = (
                    stats["total_dt"] / (stats["count"] - 1)
                )

        now = time.time()
        for can_id in self.stats:
            self.last_seen[can_id] = now

        self.mode = "on"
        return True

    def stop(self):
        self.mode = "off"

    def _learn(self, can_id, timestamp, dlc, values):
        stats = self.stats.setdefault(
            can_id,
            {
                "count": 0,
                "total_dt": 0.0,
                "dlcs": set(),
                "min": [],
                "max": [],
            },
        )

        if can_id in self.last_ts:
            stats["total_dt"] += max(
                0.0, timestamp - self.last_ts[can_id]
            )

        stats["count"] += 1
        stats["dlcs"].add(dlc)

        for index, value in enumerate(values):
            if index >= len(stats["min"]):
                stats["min"].append(value)
                stats["max"].append(value)
            else:
                stats["min"][index] = min(
                    stats["min"][index], value
                )
                stats["max"][index] = max(
                    stats["max"][index], value
                )

        self.last_ts[can_id] = timestamp

    def _allowed(self, can_id, kind, timestamp):
        """Limit repeated alerts for the same ID and alert type."""
        key = (can_id, kind)
        previous = self.last_alert.get(key)

        if previous is not None:
            if timestamp - previous < self.cooldown:
                return False

        self.last_alert[key] = timestamp
        return True

    def check(self, frame):
        """Check one frame and return [(attack_type, score), ...]."""
        if self.mode == "off":
            return []

        can_id = str(frame.get("can_id", ""))

        try:
            timestamp = float(frame.get("timestamp", 0))
            dlc = int(frame.get("dlc", 0))
        except (TypeError, ValueError):
            return []

        values = parse_data(frame.get("data", ""))

        if self.mode == "learning":
            self._learn(can_id, timestamp, dlc, values)
            return []

        self.last_seen[can_id] = time.time()
        self.missing_reported.discard(can_id)

        # Unknown CAN ID
        if can_id not in self.stats:
            if can_id not in self.unknown_reported:
                self.unknown_reported.add(can_id)
                return [("unknown ID", 0.9)]
            return []

        stats = self.stats[can_id]
        found = []

        # Injection: frames arriving much faster than normal
        mean = self.mean_interval.get(can_id)

        if can_id in self.last_ts and mean and mean > 0:
            interval = timestamp - self.last_ts[can_id]

            if (
                interval >= 0
                and interval < 0.3 * mean
                and self._allowed(can_id, "injection", timestamp)
            ):
                score = min(
                    1.0,
                    max(0.5, round(1 - interval / mean, 2)),
                )
                found.append(("injection", score))

        self.last_ts[can_id] = timestamp

        # Payload tampering: unexpected length or byte values
        odd_length = dlc not in stats["dlcs"]
        odd_values = any(
            value < stats["min"][index]
            or value > stats["max"][index]
            for index, value in enumerate(values)
            if index < len(stats["min"])
        )

        if (
            (odd_length or odd_values)
            and self._allowed(can_id, "payload tampering", timestamp)
        ):
            found.append(("payload tampering", 0.8))

        return found

    def check_missing(self):
        """Return missing-message alerts once per silent period."""
        if self.mode != "on":
            return []

        now = time.time()
        found = []

        for can_id, mean in self.mean_interval.items():
            limit = max(2.0, 5 * mean)
            last_seen = self.last_seen.get(can_id, now)

            if (
                now - last_seen > limit
                and can_id not in self.missing_reported
            ):
                self.missing_reported.add(can_id)
                found.append((can_id, "missing message", 0.6))

        return found