from collections import defaultdict
import json
import math
from pathlib import Path
import random
from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 == 1 else 0.5 * (ordered[mid - 1] + ordered[mid])


def _exact_two_sided_sign_test(diffs: list[float], tol: float = 1e-12) -> dict[str, Any]:
    pos = sum(1 for d in diffs if d > tol)
    neg = sum(1 for d in diffs if d < -tol)
    n_eff = pos + neg
    if n_eff == 0:
        return {"effective_pairs": 0, "positive_diffs": 0, "negative_diffs": 0, "two_sided_p_value": 1.0}
    k = min(pos, neg)
    tail = sum(math.comb(n_eff, i) for i in range(0, k + 1)) * (0.5 ** n_eff)
    return {
        "effective_pairs": n_eff,
        "positive_diffs": pos,
        "negative_diffs": neg,
        "two_sided_p_value": round(min(1.0, 2.0 * tail), 6),
    }


def _paired_metric_comparison(tefv_vals: list[float], base_vals: list[float], lower_is_better: bool = True) -> dict[str, Any]:
    pairs = [(a, b) for a, b in zip(tefv_vals, base_vals) if math.isfinite(a) and math.isfinite(b)]
    if not pairs:
        return {"n_pairs": 0, "tefv_wins": 0, "mean_diff_tefv_minus_base": None, "median_diff": None}
    diffs = [a - b for a, b in pairs]
    wins = sum(1 for d in diffs if (d < -1e-12 if lower_is_better else d > 1e-12))
    sign = _exact_two_sided_sign_test(diffs)
    return {
        "n_pairs": len(pairs),
        "tefv_wins": wins,
        "tefv_win_rate": round(wins / len(pairs), 4),
        "mean_diff_tefv_minus_base": round(_mean(diffs), 4),
        "median_diff": round(_median(diffs), 4),
        "two_sided_sign_p_value": sign["two_sided_p_value"],
    }


def generate_synthetic_instance(scenario: str, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    n_items = 18
    n_slots = 3
    configs = {
        "production_shifts": {"cap": 90.0, "q_min": 2, "p_conflict": 0.20, "deadline_max": 12, "data_type": "synthetic_baseline"},
        "resource_allocation": {"cap": 74.0, "q_min": 2, "p_conflict": 0.36, "deadline_max": 10, "data_type": "synthetic_baseline"},
        "sla_replanning": {"cap": 60.0, "q_min": 3, "p_conflict": 0.50, "deadline_max": 8, "data_type": "synthetic_baseline"},
    }
    cfg = configs[scenario]
    demands = [float(rng.randint(8, 22)) for _ in range(n_items)]
    deadlines = [rng.randint(3, cfg["deadline_max"] + 2) for _ in range(n_items)]
    conflicts = {
        (i, j)
        for i in range(n_items)
        for j in range(i + 1, n_items)
        if rng.random() < cfg["p_conflict"]
    }
    return {
        "scenario": scenario,
        "data_type": cfg["data_type"],
        "seed": seed,
        "n_items": n_items,
        "n_slots": n_slots,
        "demands": demands,
        "deadlines": deadlines,
        "conflicts": conflicts,
        "capacities": [cfg["cap"]] * n_slots,
        "q_min": cfg["q_min"],
    }


def evaluate_channels(inst: dict[str, Any], state: list[int]) -> dict[str, float]:
    n_slots = inst["n_slots"]
    slot_counts = [0] * n_slots
    slot_loads = [0.0] * n_slots
    for item, slot in enumerate(state):
        slot_counts[slot] += 1
        slot_loads[slot] += inst["demands"][item]

    v_capacity = sum(max(0.0, slot_loads[s] - inst["capacities"][s]) for s in range(n_slots))
    v_quota = sum(max(0.0, float(inst["q_min"] - slot_counts[s])) for s in range(n_slots))
    v_deadline = sum(max(0.0, float((slot + 1) * 4 - inst["deadlines"][item])) for item, slot in enumerate(state))
    v_conflict = sum(1.0 for (i, j) in inst["conflicts"] if state[i] == state[j])

    channels = {
        "capacity": round(v_capacity, 4),
        "deadline": round(v_deadline, 4),
        "conflict": round(v_conflict, 4),
        "quota": round(v_quota, 4),
    }
    channels["total"] = round(sum(channels.values()), 4)
    return channels


def _dominant_bottleneck(channels: dict[str, float]) -> str:
    non_total = {k: v for k, v in channels.items() if k != "total"}
    if sum(non_total.values()) <= 1e-9:
        return "none"
    return max(non_total.items(), key=lambda kv: kv[1])[0]


def run_budgeted_algorithm(inst: dict[str, Any], algorithm: str, c_verif_cap: int, seed: int) -> dict[str, Any]:
    assert c_verif_cap >= 2, "c_verif_cap must be >= 2 to include search verifications and a final audit."
    rng = random.Random(seed * 1009 + hash(algorithm) % 997)
    n_items = inst["n_items"]
    n_slots = inst["n_slots"]

    current_state = [rng.randrange(n_slots) for _ in range(n_items)]
    init_channels = evaluate_channels(inst, current_state)
    v_ini = init_channels["total"]

    best_state = list(current_state)
    best_v = v_ini

    verif_used = 1
    search_limit = c_verif_cap - 1
    transitions = 0
    rebounds = 0
    prev_channels = init_channels
    channel_order = ["capacity", "deadline", "conflict", "quota"]
    focus_idx = 0
    nogoods: dict[tuple[int, int], int] = {}

    while verif_used < search_limit:
        item = rng.randrange(n_items)
        if algorithm == "TEFV_G_Orquestrador":
            if rng.random() < 0.65:
                item = (item + int(inst["demands"][item]) + focus_idx) % n_items
            for key in list(nogoods.keys()):
                nogoods[key] -= 1
                if nogoods[key] <= 0:
                    del nogoods[key]
            cand_slot = rng.randrange(n_slots)
            if (item, cand_slot) in nogoods and rng.random() < 0.75:
                cand_slot = (cand_slot + 1) % n_slots
        elif algorithm == "Busca_Tabu_Orcamento":
            cand_slot = (current_state[item] + rng.randint(1, n_slots - 1)) % n_slots
        else:
            cand_slot = rng.randrange(n_slots)

        if cand_slot == current_state[item]:
            cand_slot = (cand_slot + 1) % n_slots

        cand_state = list(current_state)
        cand_state[item] = cand_slot
        cand_channels = evaluate_channels(inst, cand_state)
        verif_used += 1
        transitions += 1

        if any(cand_channels[c] > prev_channels[c] + 1e-9 for c in channel_order):
            rebounds += 1

        delta_v = cand_channels["total"] - prev_channels["total"]
        focus_channel = channel_order[focus_idx]
        accept = False
        if delta_v <= 0.0:
            accept = True
        elif algorithm == "Simulated_Annealing_Orcamento":
            temp = max(0.25, 4.0 * (1.0 - verif_used / max(1, search_limit)))
            accept = rng.random() < math.exp(-delta_v / temp)
        elif algorithm == "Busca_Tabu_Orcamento":
            accept = rng.random() < 0.15
        else:
            if cand_channels[focus_channel] < prev_channels[focus_channel] and delta_v <= 2.0:
                accept = True
            else:
                nogoods[(item, cand_slot)] = 4

        if accept:
            current_state = cand_state
            prev_channels = cand_channels
            if cand_channels["total"] < best_v:
                best_v = cand_channels["total"]
                best_state = list(cand_state)

        if algorithm == "TEFV_G_Orquestrador" and transitions % 12 == 0:
            focus_idx = (focus_idx + 1) % len(channel_order)

        if best_v <= 1e-9:
            break

    final_channels = evaluate_channels(inst, best_state)
    verif_used += 1
    v_fin = final_channels["total"]
    net_reduction = max(0.0, v_ini - v_fin)
    eta_v = net_reduction / max(1, verif_used - 1)
    cost_per_net = (verif_used / net_reduction) if net_reduction > 1e-9 else None
    rebound_rate = (rebounds / transitions) if transitions > 0 else 0.0

    return {
        "scenario": inst["scenario"],
        "data_type": inst["data_type"],
        "seed": seed,
        "algorithm": algorithm,
        "c_verif_cap": c_verif_cap,
        "c_verif": verif_used,
        "initial_violations": round(v_ini, 4),
        "final_violations": round(v_fin, 4),
        "net_reduction": round(net_reduction, 4),
        "eta_v_final": round(eta_v, 6),
        "cost_per_net_reduction": round(cost_per_net, 6) if cost_per_net is not None else None,
        "rebound_rate": round(rebound_rate, 4),
        "feasible": v_fin <= 1e-9,
        "residual_bottleneck": _dominant_bottleneck(final_channels),
    }


def run_paired_validation(
    seeds: list[int] | None = None,
    c_verif_cap: int = 200,
    output_json: str = "sample_reports/paired_validation_summary.json",
) -> dict[str, Any]:
    if seeds is None:
        seeds = list(range(101, 111))

    scenarios = ["production_shifts", "resource_allocation", "sla_replanning"]
    algorithms = ["TEFV_G_Orquestrador", "Busca_Tabu_Orcamento", "Simulated_Annealing_Orcamento"]
    results = [
        run_budgeted_algorithm(generate_synthetic_instance(scenario, seed), alg, c_verif_cap, seed)
        for scenario in scenarios
        for seed in seeds
        for alg in algorithms
    ]

    by_pair: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in results:
        by_pair[(row["scenario"], row["seed"])][row["algorithm"]] = row

    paired_comparisons = []
    for scenario in scenarios:
        complete_pairs = [
            by_pair[(scenario, seed)]
            for seed in seeds
            if all(alg in by_pair[(scenario, seed)] for alg in algorithms)
        ]
        for baseline in ["Busca_Tabu_Orcamento", "Simulated_Annealing_Orcamento"]:
            paired_comparisons.append(
                {
                    "scenario": scenario,
                    "baseline": baseline,
                    "final_violations": _paired_metric_comparison(
                        [p["TEFV_G_Orquestrador"]["final_violations"] for p in complete_pairs],
                        [p[baseline]["final_violations"] for p in complete_pairs],
                        lower_is_better=True,
                    ),
                    "rebound_rate": _paired_metric_comparison(
                        [p["TEFV_G_Orquestrador"]["rebound_rate"] for p in complete_pairs],
                        [p[baseline]["rebound_rate"] for p in complete_pairs],
                        lower_is_better=True,
                    ),
                }
            )

    payload = {
        "c_verif_cap": c_verif_cap,
        "seeds": seeds,
        "data_note": "Synthetic benchmark data only; does not replace real-world operational datasets.",
        "paired_comparisons": paired_comparisons,
        "results": results,
    }
    Path(output_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    summary = run_paired_validation()
    for comp in summary["paired_comparisons"]:
        print(comp)