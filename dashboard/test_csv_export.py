import os
from csv_export import FrameRecorder

rec = FrameRecorder()
for i in range(250):
    rec.add({"timestamp": 1792933400 + i * 0.05, "can_id": "0x123" if i % 5 else "0x244",
             "dlc": 8, "data": "11 22 33 44 55 66 77 88", "extended": False})

print("Summary:", rec.summary())
saved = rec.save("captures/test_output.csv")
print("Saved rows:", saved)
print("File exists:", os.path.exists("captures/test_output.csv"))
print(open("captures/test_output.csv").read().splitlines()[:3])