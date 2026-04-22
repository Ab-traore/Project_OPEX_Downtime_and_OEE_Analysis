# 📊 Data Dictionary – Manufacturing OEE Dataset

> **Projet** : Analyse TRS (Taux de Rendement Synthétique) en contexte industriel Lean  
> **Période** : 2023–2024 | **2 usines** | **8 lignes de production** | **3 équipes (shifts)**  
> **Format** : CSV + SQLite (`manufacturing_oee.db`)

---

## Schéma relationnel

```
ref_lines ──────────┐
                    │ line_id
oee_daily ──────────┤
                    ├── stops
                    ├── micro_stops
                    └── quality_defects
```

---

## Table : `oee_daily`
**Granularité** : 1 ligne = 1 shift × 1 ligne de production × 1 jour  
**Volume** : ~11 000 enregistrements

| Colonne | Type | Description |
|---|---|---|
| `plant_id` | TEXT | Identifiant usine : `USN_NORD`, `USN_SUD` |
| `plant_name` | TEXT | Nom complet de l'usine |
| `line_id` | TEXT | Identifiant ligne : `LN-01`…`LN-04`, `LS-01`…`LS-04` |
| `product_family` | TEXT | Famille produit fabriquée sur la ligne |
| `date` | DATE | Date de production (YYYY-MM-DD) |
| `year` | INT | Année (2023 ou 2024) |
| `month` | INT | Mois (1–12) |
| `week` | INT | Semaine ISO |
| `day_of_week` | TEXT | Jour de la semaine (en français) |
| `shift` | TEXT | Équipe : `Matin`, `Après-midi`, `Nuit` |
| `planned_time_min` | INT | Temps ouverture planifié (480 min = 8h) |
| `scheduled_stop_min` | INT | Arrêts planifiés (pauses, nettoyage) |
| `available_time_min` | INT | Temps disponible net = planifié − arrêts planifiés |
| `unplanned_stop_min` | INT | Arrêts non planifiés (pannes, etc.) |
| `net_operating_min` | INT | Temps de fonctionnement effectif |
| `availability` | FLOAT | **Disponibilité** = net_operating / available_time ∈ [0,1] |
| `performance` | FLOAT | **Performance** = production réelle / production idéale ∈ [0,1] |
| `quality` | FLOAT | **Qualité** = pièces bonnes / pièces produites ∈ [0,1] |
| `oee` | FLOAT | **TRS** = Disponibilité × Performance × Qualité ∈ [0,1] |
| `ideal_cycle_time_s` | FLOAT | Temps de cycle idéal (secondes/pièce) |
| `ideal_output_units` | INT | Production théorique maximale |
| `actual_output_units` | INT | Production réelle |
| `good_output_units` | INT | Pièces conformes |
| `scrap_units` | INT | Pièces non conformes (rebuts + retouches) |

---

## Table : `stops`
**Granularité** : 1 ligne = 1 événement d'arrêt non planifié  
**Volume** : ~22 000 enregistrements

| Colonne | Type | Description |
|---|---|---|
| `stop_id` | INT | Identifiant unique de l'arrêt |
| `plant_id` | TEXT | Usine concernée |
| `line_id` | TEXT | Ligne concernée |
| `date` | DATE | Date de l'arrêt |
| `shift` | TEXT | Équipe concernée |
| `stop_category` | TEXT | Catégorie Lean : `Panne`, `Changement de série`, `Manque matière`, `Maintenance préventive`, `Qualité / Réglage`, `Arrêt organisationnel`, `Autre` |
| `stop_cause` | TEXT | Cause détaillée de l'arrêt |
| `duration_min` | INT | Durée de l'arrêt (minutes) |
| `maintenance_team` | BOOL | Intervention maintenance nécessaire (1/0) |
| `mttr_min` | FLOAT | MTTR (Mean Time To Repair) en minutes – uniquement pannes |
| `year` | INT | Année |
| `month` | INT | Mois |

---

## Table : `micro_stops`
**Granularité** : 1 ligne = 1 micro-arrêt (< 5 min, souvent non enregistré en production réelle)  
**Volume** : ~210 000 enregistrements

| Colonne | Type | Description |
|---|---|---|
| `micro_stop_id` | INT | Identifiant unique |
| `plant_id` | TEXT | Usine |
| `line_id` | TEXT | Ligne |
| `date` | DATE | Date |
| `shift` | TEXT | Équipe |
| `micro_cause` | TEXT | Cause du micro-arrêt (ex: `Bourrage matière`, `Faux contact capteur`) |
| `duration_min` | FLOAT | Durée en minutes (0.5–4 min) |
| `year` | INT | Année |
| `month` | INT | Mois |

---

## Table : `quality_defects`
**Granularité** : 1 ligne = 1 type de défaut constaté sur un shift  
**Volume** : ~27 000 enregistrements

| Colonne | Type | Description |
|---|---|---|
| `defect_id` | INT | Identifiant unique |
| `plant_id` | TEXT | Usine |
| `line_id` | TEXT | Ligne |
| `product_family` | TEXT | Famille produit |
| `date` | DATE | Date |
| `shift` | TEXT | Équipe |
| `defect_type` | TEXT | Type de défaut (ex: `Dimension hors tolérance`, `Défaut aspect`) |
| `quantity_defect` | INT | Nombre de pièces défectueuses |
| `quantity_rework` | INT | Pièces retouchées et récupérées |
| `quantity_scrap` | INT | Pièces rebuts (irrécupérables) |
| `year` | INT | Année |
| `month` | INT | Mois |

---

## Table : `ref_lines`
**Granularité** : 1 ligne = 1 ligne de production (référentiel)  
**Volume** : 8 enregistrements

| Colonne | Type | Description |
|---|---|---|
| `line_id` | TEXT | Identifiant ligne (clé primaire logique) |
| `plant_id` | TEXT | Usine de rattachement |
| `plant_name` | TEXT | Nom complet de l'usine |
| `product_family` | TEXT | Famille produit de la ligne |
| `commissioning_year` | INT | Année de mise en service de la ligne |
| `shifts_per_day` | INT | Nombre d'équipes standard par jour |
| `oee_target` | FLOAT | Objectif TRS de la ligne |
| `availability_target` | FLOAT | Objectif disponibilité |
| `performance_target` | FLOAT | Objectif performance |
| `quality_target` | FLOAT | Objectif qualité |

---

## Hypothèses de simulation

| Paramètre | Valeur |
|---|---|
| Période | 2023-01-01 → 2024-12-31 |
| Jours ouvrés | Lun–Ven, hors jours fériés FR |
| Shifts | 3 × 8h (nuit optionnelle ~75%) |
| TRS cible Usine Nord | 79% |
| TRS cible Usine Sud | 75% |
| Saisonnalité | Automotive (chute août/déc) · Aerospace (chute été, pic fin d'année) |
| Progression learning curve | +0 à +8% sur 2 ans par ligne |

---

## Idées d'analyses à mener

- 📈 **Évolution temporelle** du TRS mois par mois (tendance, saisonnalité)
- 🔥 **Heatmap** ligne × mois pour identifier les points chauds
- 📊 **Pareto des arrêts** : 80% des pertes viennent de 20% des causes
- ⚙️ **Analyse MTBF / MTTR** par ligne → plan de fiabilisation
- 🔬 **Décomposition des pertes** : Disponibilité vs Performance vs Qualité
- 🌙 **Comparaison par équipe** : l'équipe de nuit est-elle moins performante ?
- 💰 **Gain potentiel** si TRS → 85% (unités supplémentaires, CA)
- 🤖 **ML** : prédiction du TRS ou classification des pannes
