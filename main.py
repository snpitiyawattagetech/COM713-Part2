# main.py
# ============================================================
# Demonstration entry point for the Medicine Supply Chain
# Optimisation System.
#
# Loads real data from CSV files, processes all pending
# medicine requests, and reports results to the console.
# ============================================================

import os
from supply_chain import SupplyChain

# ── Resolve file paths relative to this script ────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVENTORY_CSV = os.path.join(BASE_DIR, "hospital_inventory.csv")
ROUTES_CSV    = os.path.join(BASE_DIR, "hospital_routes.csv")
REQUESTS_CSV  = os.path.join(BASE_DIR, "medicine_requests.csv")


def main():
    print("\n" + "=" * 60)
    print("  COM713 – Medicine Supply Chain Optimisation System")
    print("  Sri Lanka Rural Hospital Network")
    print("=" * 60 + "\n")

    # ── Step 1: Initialise the supply chain ──────────────────
    system = SupplyChain()

    # ── Step 2: Load data from CSV files ─────────────────────
    print("[INFO] Loading hospital inventory ...")
    system.load_inventory_csv(INVENTORY_CSV)

    print("[INFO] Loading hospital routes ...")
    system.load_routes_csv(ROUTES_CSV)

    print("[INFO] Loading medicine requests ...")
    system.load_requests_csv(REQUESTS_CSV)

    # ── Step 3: Show initial network summary ─────────────────
    print("\n" + system.network_summary())

    # ── Step 4: Check for low-stock alerts ───────────────────
    print("\n\n" + "=" * 60)
    print("  LOW-STOCK ALERTS  (most critical first)")
    print("=" * 60)
    alerts = system.get_low_stock_alerts()
    if alerts:
        print(f"\n  {'Hospital':<22} {'Medicine':<15} {'Stock':>6} "
              f"{'Min':>6} {'Shortage':>9} {'Score':>7}")
        print("  " + "-" * 70)
        for a in alerts:
            print(f"  {a['hospital']:<22} {a['medicine']:<15} "
                  f"{a['stock']:>6} {a['min_stock']:>6} "
                  f"{a['shortage']:>9} {a['urgency']:>7.3f}")
    else:
        print("\n  All hospitals are adequately stocked.")

    # ── Step 5: Process medicine requests ────────────────────
    print("\n\n" + "=" * 60)
    print("  PROCESSING MEDICINE REQUESTS  (priority order, not arrival order)")
    print("=" * 60)
    results = system.process_requests()

    for r in results:
        print(f"\n  Request #{r['request_id']}")
        print(f"    Hospital  : {r['hospital']}")
        print(f"    Medicine  : {r['medicine']}")
        print(f"    Quantity  : {r['quantity']} units")
        print(f"    Status    : {r['status']}")
        if r.get('supplier'):
            print(f"    Supplier  : {r['supplier']}")
            print(f"    Distance  : {r['distance_km']} km")
            print(f"    Route     : {r['path']}")

    # ── Step 6: Transfer audit log ───────────────────────────
    print("\n\n" + "=" * 60)
    print("  TRANSFER AUDIT LOG")
    print("=" * 60 + "\n")
    print(system.transfer_log_summary())

    print("\n[INFO] All requests processed. System ready.\n")


if __name__ == "__main__":
    main()