"""
OEE (TRS) Dataset Generator - Manufacturing Analytics Project
=============================================================
Generates realistic manufacturing data for 2 plants, 8 lines, 2 years
Includes: OEE metrics, stops/breakdowns, micro-stops, quality defects
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta
import random

random.seed(42)
np.random.seed(42)

OUTPUT_DIR = "/home/claude/datasets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────

PLANTS = {
    "USN_NORD": {
        "name": "Usine Nord – Valenciennes",
        "lines": ["LN-01", "LN-02", "LN-03", "LN-04"],
        "product_family": ["Boîtiers plastique", "Faisceaux câbles", "Connecteurs", "Modules électroniques"],
        "base_trs": 0.74,          # TRS cible de l'usine
        "seasonality": "automotive" # forte chute en août + décembre
    },
    "USN_SUD": {
        "name": "Usine Sud – Bordeaux",
        "lines": ["LS-01", "LS-02", "LS-03", "LS-04"],
        "product_family": ["Capots aluminium", "Joints d'étanchéité", "Éléments de structure", "Assemblage final"],
        "base_trs": 0.70,
        "seasonality": "aerospace"  # ralentissement estival + fin d'année chargée
    }
}

SHIFTS = {
    "Matin":   {"start": "06:00", "end": "14:00", "duration_h": 8},
    "Après-midi": {"start": "14:00", "end": "22:00", "duration_h": 8},
    "Nuit":    {"start": "22:00", "end": "06:00", "duration_h": 8},
}

# Catégories de causes d'arrêts (Lean 6 grandes pertes)
STOP_CATEGORIES = {
    "Panne": {
        "weight": 0.28,
        "causes": [
            "Panne capteur", "Défaillance moteur", "Rupture courroie",
            "Fuite hydraulique", "Court-circuit armoire", "Panne automate",
            "Blocage mécanique", "Défaillance vérin", "Panne convoyeur"
        ],
        "avg_duration_min": 55,
        "std_duration_min": 40
    },
    "Changement de série": {
        "weight": 0.20,
        "causes": [
            "Changement d'outil", "Réglage machine", "Changement moule",
            "Remplacement filière", "Ajustement paramètres"
        ],
        "avg_duration_min": 45,
        "std_duration_min": 20
    },
    "Manque matière": {
        "weight": 0.15,
        "causes": [
            "Rupture composants", "Retard fournisseur", "Non-conformité lot entrant",
            "Manque emballage", "Rupture matière première"
        ],
        "avg_duration_min": 30,
        "std_duration_min": 25
    },
    "Maintenance préventive": {
        "weight": 0.12,
        "causes": [
            "Graissage planifié", "Remplacement filtres", "Étalonnage capteurs",
            "Vérification sécurités", "Nettoyage système"
        ],
        "avg_duration_min": 35,
        "std_duration_min": 15
    },
    "Qualité / Réglage": {
        "weight": 0.13,
        "causes": [
            "Dérive dimensionnelle", "Problème aspect surface", "Non-conformité soudure",
            "Mauvais collage", "Défaut d'assemblage"
        ],
        "avg_duration_min": 20,
        "std_duration_min": 15
    },
    "Arrêt organisationnel": {
        "weight": 0.07,
        "causes": [
            "Réunion équipe", "Formation opérateur", "Audit qualité",
            "Inventaire", "Nettoyage 5S"
        ],
        "avg_duration_min": 25,
        "std_duration_min": 20
    },
    "Autre": {
        "weight": 0.05,
        "causes": ["Cause inconnue", "Divers", "En cours d'analyse"],
        "avg_duration_min": 15,
        "std_duration_min": 10
    }
}

DEFECT_TYPES = [
    "Dimension hors tolérance", "Défaut aspect", "Mauvais assemblage",
    "Soudure défectueuse", "Inclusion / Corps étranger", "Fissure",
    "Mauvais marquage", "Manque composant", "Défaut électrique"
]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def seasonal_factor(date: datetime, seasonality: str) -> float:
    """Return a multiplier (0.5–1.1) based on month and plant type."""
    m = date.month
    if seasonality == "automotive":
        factors = {1:0.95, 2:1.00, 3:1.02, 4:1.00, 5:1.03,
                   6:1.00, 7:0.80, 8:0.52, 9:1.05, 10:1.05,
                   11:1.02, 12:0.72}
    else:  # aerospace
        factors = {1:0.90, 2:0.98, 3:1.02, 4:1.05, 5:1.05,
                   6:1.00, 7:0.85, 8:0.68, 9:1.05, 10:1.10,
                   11:1.10, 12:1.08}
    return factors.get(m, 1.0)


def line_maturity_factor(line_id: str, date: datetime, start_date: datetime) -> float:
    """Lines improve slowly over 2 years (learning curve)."""
    days = (date - start_date).days
    improvement = min(0.08, days / 730 * 0.08)  # max +8% over 2 years
    # Some lines are newer / less mature
    base = {"LN-01": 1.00, "LN-02": 0.96, "LN-03": 0.93, "LN-04": 0.98,
            "LS-01": 0.97, "LS-02": 1.00, "LS-03": 0.91, "LS-04": 0.95}
    return base.get(line_id, 1.0) + improvement


def is_production_day(date: datetime) -> bool:
    """Mon–Fri only (no weekends). Some bank holidays excluded."""
    BANK_HOLIDAYS = [
        "2023-01-01","2023-04-10","2023-05-01","2023-05-08","2023-05-18",
        "2023-05-29","2023-07-14","2023-08-15","2023-11-01","2023-11-11","2023-12-25",
        "2024-01-01","2024-04-01","2024-05-01","2024-05-08","2024-05-09","2024-05-20",
        "2024-07-14","2024-08-15","2024-11-01","2024-11-11","2024-12-25"
    ]
    if date.weekday() >= 5:
        return False
    if date.strftime("%Y-%m-%d") in BANK_HOLIDAYS:
        return False
    return True


def generate_oee_components(base_trs, seasonal_f, maturity_f, shift_name):
    """Generate realistic Availability, Performance, Quality that multiply to OEE."""
    # Shift effect: night shift slightly worse
    shift_penalty = {"Matin": 0.0, "Après-midi": -0.01, "Nuit": -0.025}.get(shift_name, 0)

    # Target OEE adjusted
    target = base_trs * seasonal_f * maturity_f + shift_penalty
    target = np.clip(target, 0.30, 0.95)

    # Decompose into A × P × Q
    # Availability: 0.70–0.98
    A = np.clip(np.random.beta(12, 3) * 0.30 + 0.68, 0.50, 0.99)
    # Performance: 0.75–0.99
    P = np.clip(np.random.beta(14, 3) * 0.24 + 0.74, 0.55, 0.99)
    # Quality: 0.92–0.999
    Q = np.clip(np.random.beta(20, 2) * 0.08 + 0.92, 0.80, 0.999)

    # Nudge product toward target
    current = A * P * Q
    ratio = (target / current) ** (1/3)
    A = np.clip(A * ratio, 0.40, 0.99)
    P = np.clip(P * ratio, 0.40, 0.99)
    Q = np.clip(Q * ratio, 0.75, 0.999)

    oee = A * P * Q
    return round(A, 4), round(P, 4), round(Q, 4), round(oee, 4)


# ──────────────────────────────────────────────
# TABLE 1 : oee_daily
# ──────────────────────────────────────────────

def generate_oee_daily() -> pd.DataFrame:
    rows = []
    start = datetime(2023, 1, 1)
    end   = datetime(2024, 12, 31)

    for plant_id, plant in PLANTS.items():
        date = start
        while date <= end:
            if not is_production_day(date):
                date += timedelta(days=1)
                continue

            sf = seasonal_factor(date, plant["seasonality"])

            for line_id in plant["lines"]:
                mf = line_maturity_factor(line_id, date, start)
                prod_family = plant["product_family"][plant["lines"].index(line_id)]

                for shift_name, shift_info in SHIFTS.items():
                    # Skip night shift ~25% of the time (not all plants run 3x8 every day)
                    if shift_name == "Nuit" and random.random() < 0.25:
                        continue

                    A, P, Q, oee = generate_oee_components(
                        plant["base_trs"], sf, mf, shift_name
                    )

                    planned_time_min = shift_info["duration_h"] * 60
                    # Scheduled stops (breaks, cleaning) 5–10%
                    scheduled_stop_min = round(planned_time_min * random.uniform(0.05, 0.10))
                    available_time_min = planned_time_min - scheduled_stop_min
                    unplanned_stop_min = round(available_time_min * (1 - A))
                    net_operating_min  = round(available_time_min * A)

                    # Production volumes
                    ideal_cycle_time_s = random.uniform(8, 45)   # secondes / pièce
                    ideal_output = int((net_operating_min * 60) / ideal_cycle_time_s)
                    actual_output = int(ideal_output * P)
                    good_output   = int(actual_output * Q)
                    scrap_output  = actual_output - good_output

                    rows.append({
                        "plant_id":             plant_id,
                        "plant_name":           plant["name"],
                        "line_id":              line_id,
                        "product_family":       prod_family,
                        "date":                 date.strftime("%Y-%m-%d"),
                        "year":                 date.year,
                        "month":                date.month,
                        "week":                 date.isocalendar()[1],
                        "day_of_week":          date.strftime("%A"),
                        "shift":                shift_name,
                        "planned_time_min":     planned_time_min,
                        "scheduled_stop_min":   scheduled_stop_min,
                        "available_time_min":   available_time_min,
                        "unplanned_stop_min":   unplanned_stop_min,
                        "net_operating_min":    net_operating_min,
                        "availability":         A,
                        "performance":          P,
                        "quality":              Q,
                        "oee":                  oee,
                        "ideal_cycle_time_s":   round(ideal_cycle_time_s, 2),
                        "ideal_output_units":   ideal_output,
                        "actual_output_units":  actual_output,
                        "good_output_units":    good_output,
                        "scrap_units":          scrap_output,
                    })

            date += timedelta(days=1)

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# TABLE 2 : stops (arrêts & pannes)
# ──────────────────────────────────────────────

def generate_stops(oee_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    stop_id = 1

    for _, rec in oee_df.iterrows():
        remaining_stop_min = rec["unplanned_stop_min"]
        if remaining_stop_min <= 2:
            continue

        # Distribute stops into events
        while remaining_stop_min > 5:
            # Pick category
            cats = list(STOP_CATEGORIES.keys())
            weights = [STOP_CATEGORIES[c]["weight"] for c in cats]
            cat = random.choices(cats, weights=weights)[0]
            cfg = STOP_CATEGORIES[cat]

            duration = max(5, int(np.random.normal(cfg["avg_duration_min"], cfg["std_duration_min"])))
            duration = min(duration, remaining_stop_min, 240)  # cap at 4h

            cause = random.choice(cfg["causes"])

            # MTTR (mean time to repair) – only for breakdowns
            mttr = duration if cat == "Panne" else None
            # Maintenance team involved?
            maintenance = cat in ["Panne", "Maintenance préventive"]

            rows.append({
                "stop_id":          stop_id,
                "plant_id":         rec["plant_id"],
                "line_id":          rec["line_id"],
                "date":             rec["date"],
                "shift":            rec["shift"],
                "stop_category":    cat,
                "stop_cause":       cause,
                "duration_min":     duration,
                "maintenance_team": maintenance,
                "mttr_min":         mttr,
                "year":             rec["year"],
                "month":            rec["month"],
            })

            stop_id += 1
            remaining_stop_min -= duration
            # Small chance of ending the loop early
            if random.random() < 0.15:
                break

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# TABLE 3 : micro_stops
# ──────────────────────────────────────────────

def generate_microstops(oee_df: pd.DataFrame) -> pd.DataFrame:
    MICRO_CAUSES = [
        "Bourrage matière", "Faux contact capteur", "Défaut positionnement pièce",
        "Obstruction buse", "Glissement courroie", "Mauvais éjection",
        "Accumulation copeaux", "Défaut lecture code-barres", "Retard opérateur",
        "Pièce hors gabarit", "Vibration excessive", "Surchauffe locale"
    ]

    rows = []
    ms_id = 1

    for _, rec in oee_df.iterrows():
        # Micro-stops come from Performance loss
        perf_loss_min = rec["net_operating_min"] * (1 - rec["performance"])
        n_microstops = int(perf_loss_min / random.uniform(1.5, 4))  # 1.5–4 min chacun
        n_microstops = min(n_microstops, 60)

        for _ in range(n_microstops):
            duration = round(random.uniform(0.5, 4.0), 1)
            rows.append({
                "micro_stop_id":    ms_id,
                "plant_id":         rec["plant_id"],
                "line_id":          rec["line_id"],
                "date":             rec["date"],
                "shift":            rec["shift"],
                "micro_cause":      random.choice(MICRO_CAUSES),
                "duration_min":     duration,
                "year":             rec["year"],
                "month":            rec["month"],
            })
            ms_id += 1

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# TABLE 4 : quality_defects
# ──────────────────────────────────────────────

def generate_quality_defects(oee_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    def_id = 1

    for _, rec in oee_df.iterrows():
        n_defects = rec["scrap_units"]
        if n_defects == 0:
            continue

        # Group defects by type
        n_types = random.randint(1, min(4, n_defects))
        split = np.random.multinomial(n_defects, np.ones(n_types)/n_types)

        for qty in split:
            if qty == 0:
                continue
            defect_type = random.choice(DEFECT_TYPES)
            # Rework possible for some defects
            rework_rate = random.uniform(0.0, 0.45)
            reworked = int(qty * rework_rate)
            scrapped  = qty - reworked

            rows.append({
                "defect_id":        def_id,
                "plant_id":         rec["plant_id"],
                "line_id":          rec["line_id"],
                "product_family":   rec["product_family"],
                "date":             rec["date"],
                "shift":            rec["shift"],
                "defect_type":      defect_type,
                "quantity_defect":  int(qty),
                "quantity_rework":  reworked,
                "quantity_scrap":   scrapped,
                "year":             rec["year"],
                "month":            rec["month"],
            })
            def_id += 1

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# TABLE 5 : ref_lines (référentiel lignes)
# ──────────────────────────────────────────────

def generate_ref_lines() -> pd.DataFrame:
    rows = []
    for plant_id, plant in PLANTS.items():
        for i, line_id in enumerate(plant["lines"]):
            rows.append({
                "line_id":          line_id,
                "plant_id":         plant_id,
                "plant_name":       plant["name"],
                "product_family":   plant["product_family"][i],
                "commissioning_year": random.choice([2015, 2017, 2018, 2019, 2020, 2021]),
                "shifts_per_day":   3,
                "oee_target":       round(plant["base_trs"] + 0.05, 2),
                "availability_target": 0.90,
                "performance_target":  0.92,
                "quality_target":      0.995,
            })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# MAIN – EXPORT CSV + SQLite
# ──────────────────────────────────────────────

def main():
    print("🏭  Génération des données TRS / OEE...")
    print("    → oee_daily          ", end="", flush=True)
    oee_df = generate_oee_daily()
    print(f"[{len(oee_df):,} lignes]")

    print("    → stops              ", end="", flush=True)
    stops_df = generate_stops(oee_df)
    print(f"[{len(stops_df):,} lignes]")

    print("    → micro_stops        ", end="", flush=True)
    micro_df = generate_microstops(oee_df)
    print(f"[{len(micro_df):,} lignes]")

    print("    → quality_defects    ", end="", flush=True)
    defects_df = generate_quality_defects(oee_df)
    print(f"[{len(defects_df):,} lignes]")

    print("    → ref_lines          ", end="", flush=True)
    ref_df = generate_ref_lines()
    print(f"[{len(ref_df):,} lignes]")

    # ── CSV ──────────────────────────────────
    print("\n📄  Export CSV...")
    csv_dir = os.path.join(OUTPUT_DIR, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    oee_df.to_csv(f"{csv_dir}/oee_daily.csv", index=False)
    stops_df.to_csv(f"{csv_dir}/stops.csv", index=False)
    micro_df.to_csv(f"{csv_dir}/micro_stops.csv", index=False)
    defects_df.to_csv(f"{csv_dir}/quality_defects.csv", index=False)
    ref_df.to_csv(f"{csv_dir}/ref_lines.csv", index=False)
    print("    ✓ CSV exportés dans datasets/csv/")

    # ── SQLite ───────────────────────────────
    print("\n🗄️   Export SQLite...")
    db_path = os.path.join(OUTPUT_DIR, "manufacturing_oee.db")
    conn = sqlite3.connect(db_path)

    oee_df.to_sql("oee_daily",       conn, if_exists="replace", index=False)
    stops_df.to_sql("stops",          conn, if_exists="replace", index=False)
    micro_df.to_sql("micro_stops",    conn, if_exists="replace", index=False)
    defects_df.to_sql("quality_defects", conn, if_exists="replace", index=False)
    ref_df.to_sql("ref_lines",        conn, if_exists="replace", index=False)

    # Indexes for performance
    cur = conn.cursor()
    for tbl, col in [
        ("oee_daily","line_id"),("oee_daily","date"),("oee_daily","plant_id"),
        ("stops","line_id"),("stops","date"),("stops","stop_category"),
        ("micro_stops","line_id"),("micro_stops","date"),
        ("quality_defects","line_id"),("quality_defects","defect_type"),
    ]:
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_{col} ON {tbl}({col})")
    conn.commit()
    conn.close()
    print(f"    ✓ SQLite : {db_path}")

    # ── Summary ──────────────────────────────
    print("\n" + "="*52)
    print("  RÉSUMÉ DES DATASETS GÉNÉRÉS")
    print("="*52)
    print(f"  oee_daily        : {len(oee_df):>7,} enregistrements")
    print(f"  stops            : {len(stops_df):>7,} enregistrements")
    print(f"  micro_stops      : {len(micro_df):>7,} enregistrements")
    print(f"  quality_defects  : {len(defects_df):>7,} enregistrements")
    print(f"  ref_lines        : {len(ref_df):>7,} enregistrements")
    print("="*52)
    print(f"\n  TRS moyen global : {oee_df['oee'].mean():.1%}")
    print(f"  Dispo moyenne    : {oee_df['availability'].mean():.1%}")
    print(f"  Perf moyenne     : {oee_df['performance'].mean():.1%}")
    print(f"  Qualité moyenne  : {oee_df['quality'].mean():.1%}")
    print(f"\n  Top 3 causes arrêts :")
    top3 = stops_df["stop_category"].value_counts().head(3)
    for cat, n in top3.items():
        print(f"    • {cat:<28} {n:,}")
    print("\n✅  Terminé !\n")


if __name__ == "__main__":
    main()
