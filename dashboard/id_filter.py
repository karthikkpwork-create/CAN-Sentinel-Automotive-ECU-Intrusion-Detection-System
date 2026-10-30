"""id_filter.py - filter the frames table by CAN ID (no window code here)."""
import re

from PyQt5.QtCore import Qt, QSortFilterProxyModel

# column names that can hold the CAN ID (the first one found is used)
ID_COLUMN_NAMES = ("can_id_hex", "can_id", "arbitration_id", "id")


def clean_id(text):
    """'0x7DF ' -> '7df' (lower case, no 0x, no spaces)."""
    text = str(text).strip().lower()
    return text[2:] if text.startswith("0x") else text


class IdFilterProxy(QSortFilterProxyModel):
    """Sits between the frames table model and the view.

    Shows only the rows whose CAN ID starts with one of the typed IDs.
    Several IDs can be typed, separated by commas or spaces.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.terms = []

    def set_text(self, text):
        """Set the filter text. An empty text shows every row."""
        self.terms = [clean_id(t) for t in re.split(r"[,\s]+", text) if t.strip()]
        self.invalidateFilter()          # check every row again

    def has_filter(self):
        return bool(self.terms)

    def id_column(self):
        """Column number of the CAN ID in the loaded table, or None."""
        header = getattr(self.sourceModel(), "header", [])
        lower = [str(h).strip().lower() for h in header]
        for name in ID_COLUMN_NAMES:
            if name in lower:
                return lower.index(name)
        return None

    def filterAcceptsRow(self, source_row, source_parent):
        if not self.terms:
            return True
        col = self.id_column()
        if col is None:
            return True                  # no ID column in this table: show everything
        model = self.sourceModel()
        index = model.index(source_row, col, source_parent)
        value = clean_id(model.data(index, Qt.DisplayRole) or "")
        return any(value.startswith(t) for t in self.terms)