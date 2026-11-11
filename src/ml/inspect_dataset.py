import csv
import sys
from collections import Counter


def inspect_csv(path):
    row_count = 0
    missing_counts = Counter()
    can_ids = Counter()
    labels = Counter()
    timestamp_examples = []
    payload_examples = []

    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)

            if not reader.fieldnames:
                print("The CSV is empty or has no header row.")
                return False

            columns = reader.fieldnames
            print("Columns:", columns)

            for row in reader:
                row_count += 1

                for column in columns:
                    if not (row.get(column) or "").strip():
                        missing_counts[column] += 1

                can_id = row.get("can_id")
                if can_id and can_id.strip():
                    can_ids[can_id.strip()] += 1

                for label_column in ("label", "attack_type", "class"):
                    value = row.get(label_column)
                    if value and value.strip():
                        labels[value.strip()] += 1
                        break

                if len(timestamp_examples) < 5:
                    timestamp = (
                        row.get("observed_timestamp")
                        or row.get("timestamp")
                    )
                    if timestamp:
                        timestamp_examples.append(timestamp)

                if len(payload_examples) < 5:
                    payload = row.get("payload_hex")
                    if payload:
                        payload_examples.append(payload)

    except OSError as error:
        print(f"Could not open the CSV: {error}")
        return False
    except csv.Error as error:
        print(f"Could not read the CSV: {error}")
        return False

    print(f"\nTotal rows: {row_count}")

    print("\nMissing or empty values:")
    for column in columns:
        print(f"  {column}: {missing_counts[column]}")

    print("\nMost common CAN IDs:")
    for can_id, count in can_ids.most_common(10):
        print(f"  {can_id}: {count} frames")
    if not can_ids:
        print("  No non-empty can_id values found.")

    print("\nTimestamp examples:")
    print(timestamp_examples or "No recognized timestamp column found.")

    print("\nPayload examples:")
    print(payload_examples or "No payload_hex column found.")

    print("\nLabels:")
    print(dict(labels) if labels else
          "No non-empty label values found; labels are not verified.")

    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python .\\src\\ml\\inspect_dataset.py "
            "PATH_TO_CSV"
        )
        sys.exit(2)

    if not inspect_csv(sys.argv[1]):
        sys.exit(1)