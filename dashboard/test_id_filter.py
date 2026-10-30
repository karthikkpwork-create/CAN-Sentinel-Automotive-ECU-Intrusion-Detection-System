from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from id_filter import IdFilterProxy

app = QCoreApplication([])


class FakeModel(QStandardItemModel):
    header = ["timestamp", "can_id", "dlc", "data", "extended"]


src = FakeModel()
for cid in ["0x123", "0x244", "0x123", "0x7df", "0x12a"]:
    src.appendRow([QStandardItem(x) for x in ("1.0", cid, "8", "11 22", "False")])

proxy = IdFilterProxy()
proxy.setSourceModel(src)


def shown(text):
    proxy.set_text(text)
    return [proxy.index(r, 1).data() for r in range(proxy.rowCount())]


print("no filter    :", len(shown("")), "rows")
print("0x123        :", shown("0x123"))
print("123          :", shown("123"))
print("0x12         :", shown("0x12"))
print("0x244, 0x7DF :", shown("0x244, 0x7DF"))
print("zzz          :", len(shown("zzz")), "rows")