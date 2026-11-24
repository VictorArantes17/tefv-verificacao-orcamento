from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from typing import Any


def _get_value(record: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    for subkey in ("metrics", "summary", "final_audit", "diagnostics"):
        sub = record.get(subkey)
        if isinstance(sub, dict):
            for key in keys:
                if key in sub and sub[key] is not None:
                    return sub[key]
    return default


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("results", "resultados", "records", "runs", "entries", "data"):
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]
    raise ValueError(
        "Unrecognized JSON structure: expected a list of records or a dictionary with a list under 'results'."
    )


def verify_lemma_from_json(
    input_json_path: str = "sample_reports/tefv_g_orchestrator_sample_report.json",
    output_json_path: str = "sample_reports/lemma_verification_summary.json",
) -> dict[str, Any]:
    src = Path(input_json_path)
    if not src.exists():
        raise FileNotFoundError(f"JSON file not found: {src.resolve()}")

    payload = json.loads(src.read_text(encoding="utf-8"))
    records = _extract_records(payload)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    bottlenecks_by_scenario: dict[str, Counter[str]] = defaultdict(Counter)

    for rec in records:
        scenario = str(_get_value(rec, ("scenario", "cenario"), "unknown"))
        algorithm = str(_get_value(rec, ("algorithm", "algoritmo"), "unknown"))
        bottleneck = str(_get_value(rec, ("residual_bottleneck", "gargalo_residual"), "none"))
        grouped[(scenario, algorithm)].append(rec)
        bottlenecks_by_scenario[scenario][bottleneck] += 1

    comparison_rows: list[dict[str, Any]] = []
    for (scenario, algorithm), items in sorted(grouped.items()):
        total_runs = len(items)
        costs: list[float] = []
        inv_etas: list[float] = []
        diffs: list[float] = []
        ratios: list[float] = []
        exact_errors: list[float] = []
        rebounds: list[float] = []
        feasible_count = 0
        non_positive_count = 0

        for rec in items:
            v_ini_raw = _get_value(rec, ("initial_violations", "violacoes_iniciais", "v_ini"))
            v_fin_raw = _get_value(rec, ("final_violations", "violacoes_finais", "v_fin"))
            net_red_raw = _get_value(rec, ("net_reduction", "reducao_liquida", "delta_v_liq"))
            eta_raw = _get_value(rec, ("eta_v_final", "eta_v"))
            cost_raw = _get_value(rec, ("cost_per_net_reduction", "custo_por_reducao_liquida", "kappa_verif"))
            c_verif_raw = _get_value(rec, ("c_verif", "verifications_used"))
            rebound_raw = _get_value(rec, ("rebound_rate", "taxa_rebote", "tau_rebote"))
            feasible_raw = _get_value(rec, ("feasible", "valida"))

            v_fin = float(v_fin_raw) if v_fin_raw is not None else None
            if isinstance(feasible_raw, bool):
                if feasible_raw:
                    feasible_count += 1
            elif v_fin is not None and v_fin <= 1e-9:
                feasible_count += 1

            if rebound_raw is not None and math.isfinite(float(rebound_raw)):
                rebounds.append(float(rebound_raw))

            if net_red_raw is not None:
                net_red = float(net_red_raw)
            elif v_ini_raw is not None and v_fin is not None:
                net_red = max(0.0, float(v_ini_raw) - v_fin)
            else:
                net_red = None

            eta_val = float(eta_raw) if eta_raw is not None else 0.0
            cost_val = float(cost_raw) if cost_raw is not None else math.inf

            if (net_red is not None and net_red <= 1e-12) or eta_val <= 1e-12 or not math.isfinite(cost_val):
                non_positive_count += 1
                continue

            inv_eta = 1.0 / eta_val
            costs.append(cost_val)
            inv_etas.append(inv_eta)
            diffs.append(cost_val - inv_eta)
            ratios.append(cost_val / inv_eta)

            if c_verif_raw is not None and float(c_verif_raw) > 1.0:
                c_val = float(c_verif_raw)
                exact_val = inv_eta * (1.0 + 1.0 / (c_val - 1.0))
                exact_errors.append(abs(cost_val - exact_val))

        n_pos = len(costs)
        comparison_rows.append(
            {
                "scenario": scenario,
                "algorithm": algorithm,
                "total_runs": total_runs,
                "positive_reduction_runs": n_pos,
                "non_positive_or_zero_eta_runs": non_positive_count,
                "feasibility_rate": round(feasible_count / max(1, total_runs), 4),
                "mean_rebound_rate": round(sum(rebounds) / len(rebounds), 4) if rebounds else None,
                "mean_cost_per_net_reduction": round(sum(costs) / n_pos, 4) if n_pos > 0 else None,
                "mean_one_over_eta_v": round(sum(inv_etas) / n_pos, 4) if n_pos > 0 else None,
                "mean_diff_cost_minus_one_over_eta": round(sum(diffs) / n_pos, 4) if n_pos > 0 else None,
                "mean_ratio_cost_over_one_over_eta": round(sum(ratios) / n_pos, 4) if n_pos > 0 else None,
                "max_exact_lemma_abs_error": round(max(exact_errors), 6) if exact_errors else None,
            }
        )

    bottleneck_summary = [
        {
            "scenario": scenario,
            "total_runs": sum(counter.values()),
            "counts": dict(counter.most_common()),
        }
        for scenario, counter in sorted(bottlenecks_by_scenario.items())
    ]

    output = {
        "source_file": str(src),
        "total_records": len(records),
        "data_note": "Synthetic benchmark data only; does not replace real-world operational datasets.",
        "lemma_comparison_by_scenario_and_algorithm": comparison_rows,
        "residual_bottlenecks_by_scenario": bottleneck_summary,
    }
    Path(output_json_path).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


if __name__ == "__main__":
    summary = verify_lemma_from_json()
    for row in summary["lemma_comparison_by_scenario_and_algorithm"]:
        print(row)