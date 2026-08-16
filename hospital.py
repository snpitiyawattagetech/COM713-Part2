# hospital.py
# ============================================================
# Hospital class – models a single hospital node in the
# supply-chain network.
#
# Data structures used:
#   • dict  (HashMap) – O(1) average get/set for inventory
#   • collections.deque – O(1) append/pop for transaction log
# ============================================================

from __future__ import annotations
from collections import deque
from typing import Dict, Optional


class Hospital:
    """
    Represents a hospital node in the Sri Lanka medicine
    supply-chain network.

    Attributes
    ----------
    name         : str   – unique hospital name / node ID
    inventory    : dict  – {medicine_name: quantity}  (HashMap)
    min_stock    : dict  – {medicine_name: threshold} (HashMap)
    history      : deque – last MAX_HISTORY transactions
    """

    MAX_HISTORY = 50  # keep only the last 50 log entries

    def __init__(self, name: str, default_min_stock: int = 50):
        """
        Initialise a Hospital node.

        Parameters
        ----------
        name              : hospital name (acts as graph key)
        default_min_stock : fallback minimum-stock threshold
        """
        self.name = name
        self.inventory: Dict[str, int] = {}          # HashMap: O(1) access
        self.min_stock: Dict[str, int] = {}          # HashMap: minimum thresholds
        self._default_min = default_min_stock
        self.history: deque = deque(maxlen=self.MAX_HISTORY)  # circular buffer

    # ----------------------------------------------------------
    # Inventory management
    # ----------------------------------------------------------

    def add_medicine(self, medicine: str, quantity: int,
                     min_stock: Optional[int] = None) -> None:
        """
        Add / overwrite a medicine entry in the inventory.

        Time complexity  : O(1) – HashMap insertion
        Space complexity : O(1) – single key-value pair

        Parameters
        ----------
        medicine  : medicine name
        quantity  : stock quantity
        min_stock : optional alert threshold (defaults to
                    default_min_stock set at construction)
        """
        self.inventory[medicine] = quantity
        self.min_stock[medicine] = (
            min_stock if min_stock is not None else self._default_min
        )
        self.history.append(
            f"[ADD] {medicine}: set to {quantity} units"
        )

    def get_stock(self, medicine: str) -> int:
        """
        Return current stock of a medicine.

        Time complexity : O(1) – HashMap lookup
        """
        return self.inventory.get(medicine, 0)

    def update_stock(self, medicine: str, quantity: int) -> None:
        """
        Update stock level for a medicine and log the change.

        Time complexity : O(1) – HashMap update
        """
        old = self.inventory.get(medicine, 0)
        self.inventory[medicine] = quantity
        delta = quantity - old
        sign = "+" if delta >= 0 else ""
        self.history.append(
            f"[UPDATE] {medicine}: {old} → {quantity} ({sign}{delta})"
        )

    # ----------------------------------------------------------
    # Stock-level helpers
    # ----------------------------------------------------------

    def get_min_stock(self, medicine: str) -> int:
        """
        Return the minimum-stock (safety-stock) threshold for a medicine,
        falling back to this hospital's default if none was set.

        Time complexity : O(1) – HashMap lookup
        """
        return self.min_stock.get(medicine, self._default_min)

    def is_low_stock(self, medicine: str) -> bool:
        """
        Return True if stock is at or below the minimum threshold.

        Time complexity : O(1)
        """
        return self.get_stock(medicine) <= self.get_min_stock(medicine)

    def get_shortage(self, medicine: str) -> int:
        """
        Return how many units are needed to reach minimum stock.
        Returns 0 if stock is adequate.

        Time complexity : O(1)
        """
        shortage = self.get_min_stock(medicine) - self.get_stock(medicine)
        return max(0, shortage)

    def urgency_score(self, medicine: str) -> float:
        """
        Compute an urgency score (lower = more urgent).
        Used by the min-heap alert and request-priority systems.

        Score = current_stock / min_stock_threshold
        A value < 1.0 means below threshold.

        Time complexity : O(1)
        """
        threshold = self.get_min_stock(medicine)
        if threshold == 0:
            return float('inf')
        return self.get_stock(medicine) / threshold

    # ----------------------------------------------------------
    # Display helpers
    # ----------------------------------------------------------

    def inventory_summary(self) -> str:
        """Return a formatted inventory table for this hospital."""
        lines = [f"  {'Medicine':<20} {'Stock':>6}  {'Min':>6}  {'Status'}"]
        lines.append("  " + "-" * 50)
        for med, qty in sorted(self.inventory.items()):
            threshold = self.min_stock.get(med, self._default_min)
            status = "⚠ LOW" if qty <= threshold else "OK"
            lines.append(f"  {med:<20} {qty:>6}  {threshold:>6}  {status}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return f"Hospital({self.name})"

    def __repr__(self) -> str:
        return (f"Hospital(name={self.name!r}, "
                f"medicines={list(self.inventory.keys())})")