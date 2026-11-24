# TEFV — Operational Theory of Frustration and Verification Efficiency

**Author:** Victor Gonçalves Vieira Arantes  
**ORCID:** [`0009-0005-3565-7904`](https://orcid.org/0009-0005-3565-7904)  

Academic and technical repository for **combinatorial optimization under a finite verification budget ($C_{\mathrm{verif}}$)** in coupled-constraint systems, including cross-channel coupling (**TEFV-G**), item-level sensitivity (**TEFV-S**), and budget orchestration (**`TEFV_G_Orquestrador`**).

---

## Reproducibility and Methodological Transparency

* **Identical verification budget cap ($C_{\mathrm{verif}}$):** all compared algorithms (`TEFV_G_Orquestrador`, `Busca_Tabu_Orcamento`, and `Simulated_Annealing_Orcamento`) are evaluated under the same total verification budget $C_{\mathrm{verif}}$ (inclusive of the final audit), documented seeds, and structured JSON/Markdown exports.
* **Evaluation criteria:**
  * Feasibility rate (`valida`, defined by audited final violation $V_{\mathrm{fin}} = 0$);
  * Final violation ($V_{\mathrm{fin}}$) and total verifications used ($C_{\mathrm{verif}}$);
  * Marginal verification efficiency ($\eta_v = \Delta V_{\mathrm{líq}} / \max(1,\; C_{\mathrm{verif}} - 1)$) and cost per net violation reduction ($\kappa_{\mathrm{verif}} = C_{\mathrm{verif}} / \Delta V_{\mathrm{líq}}$, for $\Delta V_{\mathrm{líq}} > 0$), compared against $1/\eta_v$;
  * Rebound rate ($\tau_{\mathrm{rebote}}$), net per-channel efficiency ($\eta_{v,k}^{\mathrm{líq}}$), dominant residual bottleneck when $V_{\mathrm{fin}} > 0$, and paired statistical comparisons.
* **Data nature and scope:** evaluated scenarios to date rely on **synthetic data** (they do not replace empirical real-world operational datasets). TEFV does not alter worst-case complexity bounds on $\mathbf{NP}$-hard problems or guarantee feasibility or global optimality under tight verification budgets.

---

## AI Assistance Declaration (Gemini)

The author conceived the study, defined its scope, and took responsibility for reviewing and validating the material. Assistance from artificial intelligence—specifically **Gemini**—is explicitly declared as support for scientific drafting, methodological structuring, formatting, and code/text review under the author's supervision.

---

## Repository Layout

```text
tefv-verification-budget/
├── README.md
├── LICENSE
├── docs/
│   ├── tefv_pacote_academico_completo_pt.html
│   └── tefv_complete_academic_package_en.html
├── scripts/
│   ├── verify_lemma_json.py
│   └── paired_validation_tefv.py
└── sample_reports/
    └── tefv_g_orchestrator_sample_report.json
```

---

## Where to Place Files and How to Publish

1. **GitHub:** upload `README.md`, `LICENSE`, the Portuguese and English manuscripts/PDFs, the Python scripts (lemma verification and paired validation), and sample reports to a public repository.
2. **Zenodo + DOI:** link the GitHub repository to Zenodo and publish a tagged Release (e.g., `v0.1.0`) to generate a persistent, citable **DOI**.
3. **ORCID:** link the repository and release **DOI** to your ORCID profile (`0009-0005-3565-7904`).
4. **Academic venues:** submit to preprint servers, workshops, conferences, or journals following venue guidelines while retaining all ethical, methodological, data-nature, and **Gemini** AI assistance declarations.