#!/usr/bin/env python3
"""
ORIE 5135 Project — Exam Scheduling ILP
Three formulations:
  F1 : natural ILP (edge conflict constraints)
  F2 : clique-strengthened ILP (maximal-clique constraints)
  F3 : extended formulation / set partitioning over feasible groupings
"""

import json
import time
import os
import sys

import gurobipy as gp
from gurobipy import GRB
import networkx as nx


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_instance(filepath: str) -> dict:
    with open(filepath) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# LP-relaxation helper
# ---------------------------------------------------------------------------

def lp_relaxation_value(model: gp.Model) -> float | None:
    """Return the optimal LP-relaxation objective, or None if infeasible."""
    lp = model.relax()
    lp.setParam("OutputFlag", 0)
    lp.setParam("InfUnbdInfo", 1)
    lp.optimize()
    if lp.Status == GRB.OPTIMAL:
        return lp.ObjVal
    return None


# ---------------------------------------------------------------------------
# F1 — Natural ILP
# ---------------------------------------------------------------------------

def build_f1(data: dict) -> gp.Model:
    """
    Variables
        x[i,j] in {0,1}  exam i (0-indexed) assigned to slot j (0-indexed)
        y[j]   in {0,1}  slot j is used

    Objective
        min  sum_j  y[j]

    Constraints
        (assignment)   sum_j x[i,j] = 1          for all i
        (proctor)      sum_i r[i]*x[i,j] <= R*y[j] for all j
        (conflict)     x[i,j] + x[i',j] <= 1      for all (i,i') in E, j
        (symmetry)     y[j] >= y[j+1]              for j = 0..n-2
    """
    m, n, R = data["m"], data["n"], data["R"]
    r = data["r"]
    edges = data["edges"]

    model = gp.Model("F1_natural")
    model.setParam("OutputFlag", 0)

    x = model.addVars(m, n, vtype=GRB.BINARY, name="x")
    y = model.addVars(n, vtype=GRB.BINARY, name="y")

    model.setObjective(gp.quicksum(y[j] for j in range(n)), GRB.MINIMIZE)

    for i in range(m):
        model.addConstr(gp.quicksum(x[i, j] for j in range(n)) == 1,
                        name=f"assign_{i}")

    for j in range(n):
        model.addConstr(
            gp.quicksum(r[i] * x[i, j] for i in range(m)) <= R * y[j],
            name=f"proctor_{j}")

    for i1, i2 in edges:
        i1 -= 1; i2 -= 1          # convert to 0-indexed
        for j in range(n):
            model.addConstr(x[i1, j] + x[i2, j] <= 1,
                            name=f"edge_{i1}_{i2}_{j}")

    for j in range(n - 1):
        model.addConstr(y[j] >= y[j + 1], name=f"sym_{j}")

    model.update()
    return model


# ---------------------------------------------------------------------------
# F2 — Clique-strengthened ILP
# ---------------------------------------------------------------------------

def build_f2(data: dict) -> gp.Model:
    """
    Same as F1 but replaces the per-edge conflict constraints with per-maximal-clique
    constraints:

        sum_{i in C}  x[i,j] <= 1    for every maximal clique C in G, for all j

    A clique constraint dominates all edge constraints among its members, so this
    is a strict strengthening of the LP relaxation whenever |C| >= 3.
    """
    m, n, R = data["m"], data["n"], data["R"]
    r = data["r"]
    edges = data["edges"]

    G = nx.Graph()
    G.add_nodes_from(range(1, m + 1))
    G.add_edges_from(edges)
    cliques = list(nx.find_cliques(G))

    model = gp.Model("F2_clique")
    model.setParam("OutputFlag", 0)

    x = model.addVars(m, n, vtype=GRB.BINARY, name="x")
    y = model.addVars(n, vtype=GRB.BINARY, name="y")

    model.setObjective(gp.quicksum(y[j] for j in range(n)), GRB.MINIMIZE)

    for i in range(m):
        model.addConstr(gp.quicksum(x[i, j] for j in range(n)) == 1,
                        name=f"assign_{i}")

    for j in range(n):
        model.addConstr(
            gp.quicksum(r[i] * x[i, j] for i in range(m)) <= R * y[j],
            name=f"proctor_{j}")

    for c_idx, clique in enumerate(cliques):
        for j in range(n):
            model.addConstr(
                gp.quicksum(x[v - 1, j] for v in clique) <= 1,
                name=f"clique_{c_idx}_{j}")

    for j in range(n - 1):
        model.addConstr(y[j] >= y[j + 1], name=f"sym_{j}")

    model.update()
    return model


# ---------------------------------------------------------------------------
# F3 — Extended formulation (set partitioning)
# ---------------------------------------------------------------------------

def enumerate_feasible_groupings(G: nx.Graph, r: list, R: int, m: int) -> list:
    """
    Enumerate all non-empty subsets S of exams (0-indexed) such that:
      - S is an independent set in G (no two exams in S share a student)
      - sum_{i in S} r[i] <= R   (proctor budget)
    Returns a list of tuples of 1-indexed exam IDs.
    """
    feasible = []

    def backtrack(start: int, current: list, current_r: int):
        if current:
            feasible.append(tuple(current))
        for i in range(start, m):
            exam_1idx = i + 1
            # exam must be independent from all exams already in current
            if any(G.has_edge(exam_1idx, v) for v in current):
                continue
            new_r = current_r + r[i]
            if new_r > R:
                continue
            current.append(exam_1idx)
            backtrack(i + 1, current, new_r)
            current.pop()

    backtrack(0, [], 0)
    return feasible


def build_f3(data: dict):
    """
    Extended (set-partitioning) formulation.

    Variables
        lambda[s] in {0,1}   grouping s is selected

    Objective
        min  sum_s  lambda[s]

    Constraints
        (cover)  sum_{s: i in s} lambda[s] = 1    for all exams i
                 (set partitioning — each exam in exactly one grouping)

    Returns (model, n_groupings, enumeration_time_seconds).

    Discussion (Q2b): Set *covering* (>= 1) relaxes the equality and admits
    fractional solutions where an exam is covered by parts of multiple groupings
    summing to less than one, yielding a weaker LP relaxation.  Set *partitioning*
    (= 1) is tighter and matches the structure of the problem (each exam takes place
    exactly once).  In practice the LP value of the partitioning formulation is at
    least as large as that of the covering formulation.
    """
    m, n, R = data["m"], data["n"], data["R"]
    r = data["r"]
    edges = data["edges"]

    G = nx.Graph()
    G.add_nodes_from(range(1, m + 1))
    G.add_edges_from(edges)

    t0 = time.time()
    groupings = enumerate_feasible_groupings(G, r, R, m)
    enum_time = time.time() - t0

    if not groupings:
        raise RuntimeError("No feasible groupings found.")

    model = gp.Model("F3_extended")
    model.setParam("OutputFlag", 0)

    lam = model.addVars(len(groupings), vtype=GRB.BINARY, name="lambda")

    model.setObjective(gp.quicksum(lam[s] for s in range(len(groupings))),
                       GRB.MINIMIZE)

    for i in range(m):
        exam_1idx = i + 1
        model.addConstr(
            gp.quicksum(lam[s]
                        for s, grp in enumerate(groupings)
                        if exam_1idx in grp) == 1,
            name=f"cover_{i}")

    model.update()
    return model, len(groupings), enum_time


# ---------------------------------------------------------------------------
# Unified solver
# ---------------------------------------------------------------------------

def solve_instance(data: dict, formulation: str, time_limit: float) -> dict:
    """
    Build and solve one instance with the given formulation.
    Returns a dict with LP value, solve time, node count, optimality, etc.
    """
    results = {"formulation": formulation}
    enum_time = 0.0

    if formulation == "F1":
        model = build_f1(data)
    elif formulation == "F2":
        model = build_f2(data)
    elif formulation == "F3":
        model, n_groupings, enum_time = build_f3(data)
        results["n_groupings"] = n_groupings
        results["enum_time_s"] = round(enum_time, 3)
    else:
        raise ValueError(f"Unknown formulation: {formulation}")

    # LP relaxation
    results["lp_relaxation"] = lp_relaxation_value(model)

    # Solve ILP
    model.setParam("OutputFlag", 1)
    model.setParam("TimeLimit", time_limit)
    model.optimize()

    results["solve_time_s"] = round(model.Runtime, 3)
    results["node_count"] = int(model.NodeCount)
    results["status"] = model.Status
    results["optimal"] = model.Status == GRB.OPTIMAL

    if model.SolCount > 0:
        results["obj_val"] = model.ObjVal
        results["obj_bound"] = round(model.ObjBound, 6)
    else:
        results["obj_val"] = None
        results["obj_bound"] = None

    return results


# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------

def run_dataset(base_dir: str, n_instances: int, formulations: list,
                time_limit: float, dataset_label: str) -> dict:
    all_results = {}
    print(f"\n{'='*70}")
    print(f"  {dataset_label}  |  formulations: {formulations}  |  limit: {time_limit}s")
    print(f"{'='*70}")

    for k in range(1, n_instances + 1):
        inst_name = f"instance_{k:02d}"
        filepath = os.path.join(base_dir, f"{inst_name}.json")
        data = load_instance(filepath)
        print(f"\n[{inst_name}]  m={data['m']}  n={data['n']}  R={data['R']}")
        all_results[inst_name] = {"m": data["m"], "R": data["R"]}

        for form in formulations:
            print(f"  -- {form}", flush=True)
            try:
                res = solve_instance(data, form, time_limit)
                all_results[inst_name][form] = res
                lp = res["lp_relaxation"]
                obj = res["obj_val"]
                nodes = res["node_count"]
                t = res["solve_time_s"]
                opt = "OPT" if res["optimal"] else "TL"
                print(f"     LP={lp:.4f}  obj={obj}  nodes={nodes}  "
                      f"time={t:.2f}s  [{opt}]")
                if form == "F3":
                    print(f"     groupings={res.get('n_groupings')}  "
                          f"enum={res.get('enum_time_s'):.2f}s")
            except Exception as exc:
                print(f"     ERROR: {exc}")
                all_results[inst_name][form] = {"error": str(exc)}

    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    # Dataset 1: all three formulations, 120-second limit
    results1 = run_dataset(
        base_dir=os.path.join(base, "dataset1"),
        n_instances=10,
        formulations=["F1", "F2", "F3"],
        time_limit=120,
        dataset_label="DATASET 1",
    )

    # Dataset 2: F1 and F2 only, 600-second limit
    results2 = run_dataset(
        base_dir=os.path.join(base, "dataset2"),
        n_instances=9,
        formulations=["F1", "F2"],
        time_limit=600,
        dataset_label="DATASET 2",
    )

    # Persist results
    out1 = os.path.join(base, "results_dataset1.json")
    out2 = os.path.join(base, "results_dataset2.json")
    with open(out1, "w") as f:
        json.dump(results1, f, indent=2, default=str)
    with open(out2, "w") as f:
        json.dump(results2, f, indent=2, default=str)

    print(f"\nResults saved to:\n  {out1}\n  {out2}")
