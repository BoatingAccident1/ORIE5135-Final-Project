#!/usr/bin/env python3
"""Print a formatted summary table from saved result JSON files."""

import json
import sys
import os


def fmt(val, width=10, decimals=4):
    if val is None:
        return "N/A".center(width)
    if isinstance(val, float):
        return f"{val:.{decimals}f}".rjust(width)
    return str(val).rjust(width)


def print_table(results: dict, formulations: list, dataset_label: str):
    print(f"\n{'='*90}")
    print(f"  {dataset_label}")
    print(f"{'='*90}")
    header = (f"{'Instance':<14} {'m':>4}  " +
              "".join(f"{'LP_'+f:>10} {'obj_'+f:>7} {'nodes_'+f:>9} {'t_'+f:>8} {'opt_'+f:>5}  "
                      for f in formulations))
    print(header)
    print("-" * len(header))

    for inst, inst_data in sorted(results.items()):
        m = inst_data.get("m", "?")
        row = f"{inst:<14} {m:>4}  "
        for f in formulations:
            fd = inst_data.get(f, {})
            if "error" in fd:
                row += f"{'ERR':>10} {'ERR':>7} {'ERR':>9} {'ERR':>8} {'ERR':>5}  "
            else:
                lp = fd.get("lp_relaxation")
                obj = fd.get("obj_val")
                nodes = fd.get("node_count")
                t = fd.get("solve_time_s")
                opt = "Y" if fd.get("optimal") else "N"
                row += (fmt(lp, 10, 4) + " " +
                        fmt(obj, 7, 1) + " " +
                        fmt(nodes, 9, 0) + " " +
                        fmt(t, 8, 2) + " " +
                        fmt(opt, 5) + "  ")
        print(row)
    print()


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    f1 = os.path.join(base, "results_dataset1.json")
    f2 = os.path.join(base, "results_dataset2.json")

    if os.path.exists(f1):
        with open(f1) as fh:
            r1 = json.load(fh)
        print_table(r1, ["F1", "F2", "F3"], "DATASET 1  (F1, F2, F3 | 120s limit)")
    else:
        print("results_dataset1.json not found — run solve.py first.")

    if os.path.exists(f2):
        with open(f2) as fh:
            r2 = json.load(fh)
        print_table(r2, ["F1", "F2"], "DATASET 2  (F1, F2 | 600s limit)")
    else:
        print("results_dataset2.json not found — run solve.py first.")
