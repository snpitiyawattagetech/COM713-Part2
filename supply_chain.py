# supply_chain.py
# ============================================================
# SupplyChain – orchestrates the entire hospital network.
#
# Data structures used:
#   • dict  (HashMap)         – O(1) hospital/graph lookups
#   • heapq (Binary Min-Heap) – O(log N) low-stock alert queue
#   • collections.deque       – O(1) FIFO request queue
#   • list                    – adjacency graph storage
#
# Algorithms:
#   • Dijkstra's SSSP  – emergency routing
#   • Greedy selection – nearest adequate supplier
# ============================================================

import csv
import heapq
from collections import deque
from itertools import count

from hospital import Hospital
from dijkstra import dijkstra, reconstruct_path


# ── Short hospital name aliases ────────────────────────────────────────────────
# The CSV uses full names; the graph uses short keys for readability.
# Note: "Dambulla" deliberately has no entry here / no inventory CSV row.
# It appears only in hospital_routes.csv as a bare short name, so it is
# loaded purely as a graph routing waypoint (a regional distribution point
# per Part 1, Section 5.1: "V represents ... other relevant distribution
# points") rather than a hospital that holds its own medicine stock.
NAME_MAP = {
    "Kandy General Hospital":          "Kandy",
    "Matale District Hospital":        "Matale",
    "Kurunegala Teaching Hospital":    "Kurunegala",
    "Badulla General Hospital":        "Badulla",
    "Anuradhapura Teaching Hospital":  "Anuradhapura",
    "Polonnaruwa General Hospital":    "Polonnaruwa",
    "Nuwara Eliya District Hospital":  "Nuwara Eliya",
    "Ratnapura General Hospital":      "Ratnapura",
    "Monaragala District Hospital":    "Monaragala",
    "Hambantota General Hospital":     "Hambantota",
}
# Reverse map: short → full
FULL_NAME_MAP = {v: k for k, v in NAME_MAP.items()}


class SupplyChain:
    """
    Manages the decentralised hospital medicine supply-chain
    network for rural Sri Lanka.

    Internal state
    --------------
    hospitals : dict[str, Hospital]
        Maps short node name → Hospital object.  (HashMap)
    graph     : dict[str, dict[str, int]]
        Adjacency dict for the weighted hospital-route graph.
    _alert_heap : list
        Min-heap of (urgency_score, hospital_name, medicine)
        used to surface the most critical low-stock situations.
    _request_queue : deque
        FIFO arrival buffer for pending transfer requests loaded from
        CSV. Requests are drained from here into a priority (min-heap)
        queue at the start of process_requests(), so the *order they
        arrived in* and the *order they get served in* are tracked
        separately (see process_requests()).
    _transfer_log : list
        Ordered record of all completed transfers this session.
    """

    def __init__(self):
        self.hospitals: dict[str, Hospital] = {}       # HashMap
        self.graph: dict[str, dict[str, int]] = {}     # Adjacency dict
        self._alert_heap: list = []                    # Min-Heap
        self._request_queue: deque = deque()           # FIFO queue
        self._transfer_log: list = []                  # transfer audit trail

    # ──────────────────────────────────────────────────────────
    # Graph / Hospital management
    # ──────────────────────────────────────────────────────────

    def add_hospital(self, hospital: Hospital) -> None:
        """
        Register a hospital node in the network.

        Time complexity : O(1) – HashMap insert
        """
        self.hospitals[hospital.name] = hospital
        # Ensure node exists in graph (no edges yet)
        self.graph.setdefault(hospital.name, {})

    def add_route(self, node1: str, node2: str,
                  distance: int) -> None:
        """
        Add an undirected weighted edge between two nodes.

        Time complexity : O(1) – two HashMap inserts
        """
        self.graph.setdefault(node1, {})[node2] = distance
        self.graph.setdefault(node2, {})[node1] = distance

    # ──────────────────────────────────────────────────────────
    # CSV Loaders
    # ──────────────────────────────────────────────────────────

    def load_inventory_csv(self, filepath: str) -> None:
        """
        Load hospital inventory from a CSV file.

        Expected columns:
          Hospital, Paracetamol, Amoxicillin, Insulin,
          Salbutamol, ORS, Minimum Stock

        Time complexity : O(H × M) where H = hospitals, M = medicines
        Space complexity: O(H × M)
        """
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            medicine_cols = ['Paracetamol', 'Amoxicillin',
                             'Insulin', 'Salbutamol', 'ORS']
            for row in reader:
                full_name = row['Hospital'].strip()
                if not full_name:
                    continue
                # Resolve to short node name
                short_name = NAME_MAP.get(full_name, full_name)
                min_stock = int(row.get('Minimum Stock', 50) or 50)
                hospital = Hospital(short_name, default_min_stock=min_stock)
                for med in medicine_cols:
                    qty = int(row.get(med, 0) or 0)
                    hospital.add_medicine(med, qty, min_stock=min_stock)
                self.add_hospital(hospital)

    def load_routes_csv(self, filepath: str) -> None:
        """
        Load hospital routes from a CSV file.

        Expected columns: From, To, Distance (km)

        Time complexity : O(E) where E = number of route entries
        Space complexity: O(V + E) for the adjacency dict
        """
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = row['From'].strip()
                dst = row['To'].strip()
                dist_str = row['Distance (km)'].strip()
                if not src or not dst or not dist_str:
                    continue
                try:
                    dist = int(dist_str)
                except ValueError:
                    continue
                self.add_route(src, dst, dist)

    def load_requests_csv(self, filepath: str) -> None:
        """
        Load medicine requests into the FIFO request queue.

        Expected columns: Request ID, Hospital, Medicine, Quantity

        Each row is enqueued as a dict – requests are processed
        in order (FIFO).

        Time complexity : O(R) where R = number of request rows
        Space complexity: O(R)
        """
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                hospital_full = row['Hospital'].strip()
                if not hospital_full:
                    continue
                request = {
                    'id':       row['Request ID'].strip(),
                    'hospital': NAME_MAP.get(hospital_full, hospital_full),
                    'medicine': row['Medicine'].strip(),
                    'quantity': int(row['Quantity'].strip()),
                }
                self._request_queue.append(request)  # O(1) deque append

    # ──────────────────────────────────────────────────────────
    # Core algorithms
    # ──────────────────────────────────────────────────────────

    def find_supplier(self, requesting_hospital: str,
                      medicine: str,
                      quantity: int) -> tuple:
        """
        Find the nearest hospital that can supply the requested
        quantity using Dijkstra's algorithm.

        Algorithm
        ---------
        1. Run Dijkstra from requesting_hospital to get shortest
           distances and predecessor map.
        2. Filter all hospitals that:
             a. are not the requesting hospital
             b. can fulfil the request WITHOUT dropping their own
                stock below their own safety-stock threshold, i.e.
                    available_stock >= quantity + supplier_min_stock
                (Part 1, Section 5.5 – Surplus-Facility Selection).
                This stops the system from curing one hospital's
                shortage by creating a new one at the supplier.
        3. Among feasible candidates, select the one with minimum
           distance (greedy shortest-path selection).
        4. Reconstruct the full path using reconstruct_path().

        Time complexity : O((V + E) log V)  dominated by Dijkstra
        Space complexity: O(V + E)

        Returns
        -------
        (Hospital | None, float, list[str])
          Best supplier, distance in km, path as node list.
        """
        if requesting_hospital not in self.graph:
            return None, float('inf'), []

        # Run Dijkstra's – O((V+E) log V)
        distances, predecessors = dijkstra(self.graph,
                                           requesting_hospital)

        best_hospital = None
        best_distance = float('inf')

        # Greedy selection: iterate all hospitals O(H)
        for h_name, hospital in self.hospitals.items():
            if h_name == requesting_hospital:
                continue
            safety_stock = hospital.get_min_stock(medicine)         # O(1)
            if hospital.get_stock(medicine) >= quantity + safety_stock:  # O(1)
                dist = distances.get(h_name, float('inf'))
                if dist < best_distance:
                    best_distance = dist
                    best_hospital = hospital

        if best_hospital is None:
            return None, float('inf'), []

        # Reconstruct shortest path – O(V)
        path = reconstruct_path(predecessors,
                                requesting_hospital,
                                best_hospital.name)

        return best_hospital, best_distance, path

    def transfer(self, source: Hospital, destination: Hospital,
                 medicine: str, quantity: int) -> dict:
        """
        Execute a medicine transfer between two hospitals and
        log the transaction.

        Time complexity : O(1) – two HashMap updates
        Space complexity: O(1)

        Returns a summary dict for reporting.
        """
        src_before = source.get_stock(medicine)
        dst_before = destination.get_stock(medicine)

        source.update_stock(medicine, src_before - quantity)
        destination.update_stock(medicine, dst_before + quantity)

        record = {
            'source':            source.name,
            'destination':       destination.name,
            'medicine':          medicine,
            'quantity':          quantity,
            'src_before':        src_before,
            'src_after':         src_before - quantity,
            'dst_before':        dst_before,
            'dst_after':         dst_before + quantity,
        }
        self._transfer_log.append(record)
        return record

    # ──────────────────────────────────────────────────────────
    # Min-Heap alert system
    # ──────────────────────────────────────────────────────────

    def build_alert_heap(self) -> list:
        """
        Build a min-heap of (urgency_score, hospital, medicine)
        for all medicines that are at or below minimum stock.

        Lower urgency_score = more critical (needs supply sooner).

        Algorithm
        ---------
        For each hospital and each medicine:
          • Compute urgency_score = current_stock / min_threshold
          • If score ≤ 1.0 (at or below threshold), push onto heap

        heapify runs in O(N) time (Floyd's algorithm).
        Each subsequent push/pop is O(log N).

        Time complexity : O(H × M) to build, O(log N) per future push
        Space complexity: O(H × M) worst case

        Returns
        -------
        list of (score, hospital_name, medicine) tuples, min-heap ordered.
        """
        heap = []
        for h_name, hospital in self.hospitals.items():
            for medicine in hospital.inventory:
                score = hospital.urgency_score(medicine)  # O(1)
                if score <= 1.0:
                    # Push onto heap – O(log N)
                    heapq.heappush(heap, (score, h_name, medicine))
        self._alert_heap = heap
        return heap

    def get_low_stock_alerts(self) -> list[dict]:
        """
        Return a list of low-stock alerts sorted by urgency
        (most critical first).

        Time complexity : O(H × M × log(H×M)) – building the heap
        Space complexity: O(H × M)
        """
        self.build_alert_heap()
        alerts = []
        # Pop all items from heap in priority order – O(N log N)
        temp = list(self._alert_heap)
        heapq.heapify(temp)
        while temp:
            score, h_name, medicine = heapq.heappop(temp)
            hospital = self.hospitals[h_name]
            alerts.append({
                'hospital':   h_name,
                'medicine':   medicine,
                'stock':      hospital.get_stock(medicine),
                'min_stock':  hospital.min_stock.get(medicine, 0),
                'shortage':   hospital.get_shortage(medicine),
                'urgency':    round(score, 3),
            })
        return alerts

    # ──────────────────────────────────────────────────────────
    # Request queue processor
    # ──────────────────────────────────────────────────────────

    def process_requests(self) -> list[dict]:
        """
        Process all pending medicine requests in PRIORITY order rather
        than plain arrival (FIFO) order.

        Rationale (Part 1, Sections 3.3 & 5.3): a strict first-come,
        first-served queue can serve a mildly low hospital before a
        critically empty one that simply happened to be entered later.
        Instead, every pending request is scored with the requesting
        hospital's urgency_score() for that medicine (lower score =
        more critical) and processed from a min-heap, so the most
        urgent shortage is always served first regardless of arrival
        order.

        Algorithm
        ---------
        1. Drain the FIFO arrival deque – O(R)
        2. Push each request onto a min-heap keyed by
           (urgency_score, arrival_sequence, request) – O(R log R)
           The arrival_sequence tie-breaker preserves FIFO order
           between equally-urgent requests and stops heapq from ever
           comparing the request dicts directly.
        3. Pop requests in priority order – O(log R) each
        4. Find the nearest FEASIBLE supplier via Dijkstra – O((V+E) log V)
        5. Execute the transfer if a supplier was found – O(1)

        Total time complexity : O(R log R + R × (V+E) log V)
          where R = number of requests. The R log R heap overhead is
          negligible next to the R Dijkstra searches for any
          non-trivial hospital network, so this remains dominated by
          O(R × (V+E) log V), same as the previous FIFO version.
        Space complexity : O(R + V + E)

        Returns
        -------
        list[dict] – result record for every processed request,
        ordered by the priority in which they were actually served.
        """
        results = []

        # ── Step 1-2: drain FIFO arrivals into a priority min-heap ──
        priority_heap = []
        sequence = count()  # tie-breaker; also preserves arrival order
        while self._request_queue:
            req = self._request_queue.popleft()  # O(1)
            h_name = req['hospital']
            medicine = req['medicine']
            if h_name in self.hospitals:
                urgency = self.hospitals[h_name].urgency_score(medicine)  # O(1)
            else:
                # Unknown hospital: surface the data error immediately
                # rather than letting it hide behind real shortages.
                urgency = float('-inf')
            heapq.heappush(priority_heap,
                           (urgency, next(sequence), req))  # O(log R)

        # ── Step 3: process strictly in priority order ───────────────
        while priority_heap:
            _, _, req = heapq.heappop(priority_heap)  # O(log R)

            r_id       = req['id']
            h_name     = req['hospital']
            medicine   = req['medicine']
            quantity   = req['quantity']

            if h_name not in self.hospitals:
                results.append({
                    'request_id': r_id,
                    'status':     'FAILED – hospital not found',
                    'hospital':   h_name,
                    'medicine':   medicine,
                    'quantity':   quantity,
                })
                continue

            destination = self.hospitals[h_name]

            # Find nearest adequate supplier using Dijkstra
            supplier, distance, path = self.find_supplier(
                h_name, medicine, quantity
            )

            if supplier:
                transfer_record = self.transfer(
                    supplier, destination, medicine, quantity
                )
                results.append({
                    'request_id':  r_id,
                    'status':      'SUCCESS',
                    'hospital':    h_name,
                    'medicine':    medicine,
                    'quantity':    quantity,
                    'supplier':    supplier.name,
                    'distance_km': distance,
                    'path':        ' → '.join(path) if path else 'direct',
                    **transfer_record,
                })
            else:
                results.append({
                    'request_id': r_id,
                    'status':     'FAILED – no supplier found',
                    'hospital':   h_name,
                    'medicine':   medicine,
                    'quantity':   quantity,
                    'supplier':   None,
                    'distance_km': None,
                    'path':       None,
                })

        return results

    # ──────────────────────────────────────────────────────────
    # Reporting helpers
    # ──────────────────────────────────────────────────────────

    def network_summary(self) -> str:
        """
        Print a high-level summary of the hospital network.
        """
        lines = [
            "=" * 60,
            f"  HOSPITAL NETWORK SUMMARY",
            f"  Hospitals : {len(self.hospitals)}",
            f"  Routes    : {sum(len(v) for v in self.graph.values()) // 2}",
            "=" * 60,
        ]
        for name, hospital in sorted(self.hospitals.items()):
            lines.append(f"\n  {name}")
            lines.append(hospital.inventory_summary())
        return "\n".join(lines)

    def transfer_log_summary(self) -> str:
        """Format the transfer audit log as a readable table."""
        if not self._transfer_log:
            return "  No transfers recorded."
        lines = [
            f"  {'From':<15} {'To':<15} {'Medicine':<15} "
            f"{'Qty':>5}  {'Src Before':>10} {'Src After':>9}  "
            f"{'Dst Before':>10} {'Dst After':>9}"
        ]
        lines.append("  " + "-" * 95)
        for r in self._transfer_log:
            lines.append(
                f"  {r['source']:<15} {r['destination']:<15} "
                f"  {r['medicine']:<15} {r['quantity']:>5}  "
                f"{r['src_before']:>10} {r['src_after']:>9}  "
                f"{r['dst_before']:>10} {r['dst_after']:>9}"
            )
        return "\n".join(lines)