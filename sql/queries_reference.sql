-- ============================================================
-- REQUÊTES SQL DE RÉFÉRENCE – Projet TRS / OEE Manufacturing
-- ============================================================
-- Base : manufacturing_oee.db (SQLite)
-- Tables : oee_daily | stops | micro_stops | quality_defects | ref_lines
-- ============================================================


-- ────────────────────────────────────────────────
-- 1. TRS GLOBAL PAR USINE ET PAR ANNÉE
-- ────────────────────────────────────────────────
SELECT
    plant_id,
    plant_name,
    year,
    ROUND(AVG(availability), 3)  AS avg_availability,
    ROUND(AVG(performance), 3)   AS avg_performance,
    ROUND(AVG(quality), 3)       AS avg_quality,
    ROUND(AVG(oee), 3)           AS avg_oee,
    COUNT(*)                     AS nb_shifts
FROM oee_daily
GROUP BY plant_id, plant_name, year
ORDER BY plant_id, year;


-- ────────────────────────────────────────────────
-- 2. ÉVOLUTION MENSUELLE DU TRS PAR LIGNE
-- ────────────────────────────────────────────────
SELECT
    plant_id,
    line_id,
    year,
    month,
    ROUND(AVG(oee), 3)           AS avg_oee,
    ROUND(AVG(availability), 3)  AS avg_availability,
    ROUND(AVG(performance), 3)   AS avg_performance,
    ROUND(AVG(quality), 3)       AS avg_quality,
    SUM(good_output_units)       AS total_good_units,
    SUM(scrap_units)             AS total_scrap
FROM oee_daily
GROUP BY plant_id, line_id, year, month
ORDER BY plant_id, line_id, year, month;


-- ────────────────────────────────────────────────
-- 3. PARETO DES CAUSES D'ARRÊTS (toutes usines)
-- ────────────────────────────────────────────────
SELECT
    stop_category,
    stop_cause,
    COUNT(*)                            AS nb_occurrences,
    SUM(duration_min)                   AS total_duration_min,
    ROUND(AVG(duration_min), 1)         AS avg_duration_min,
    ROUND(SUM(duration_min) * 100.0 /
          (SELECT SUM(duration_min) FROM stops), 2)  AS pct_total_time
FROM stops
GROUP BY stop_category, stop_cause
ORDER BY total_duration_min DESC
LIMIT 20;


-- ────────────────────────────────────────────────
-- 4. TEMPS D'ARRÊT PAR LIGNE ET CATÉGORIE
-- ────────────────────────────────────────────────
SELECT
    plant_id,
    line_id,
    stop_category,
    COUNT(*)                    AS nb_arrêts,
    SUM(duration_min)           AS total_min,
    ROUND(SUM(duration_min)/60.0, 1) AS total_heures,
    ROUND(AVG(duration_min), 1) AS mttr_moyen_min
FROM stops
GROUP BY plant_id, line_id, stop_category
ORDER BY plant_id, line_id, total_min DESC;


-- ────────────────────────────────────────────────
-- 5. TOP 10 CAUSES DE MICRO-ARRÊTS
-- ────────────────────────────────────────────────
SELECT
    micro_cause,
    COUNT(*)                    AS nb_occurrences,
    SUM(duration_min)           AS total_min,
    ROUND(AVG(duration_min),2)  AS avg_min
FROM micro_stops
GROUP BY micro_cause
ORDER BY total_min DESC
LIMIT 10;


-- ────────────────────────────────────────────────
-- 6. ANALYSE QUALITÉ – DÉFAUTS PAR TYPE ET LIGNE
-- ────────────────────────────────────────────────
SELECT
    plant_id,
    line_id,
    defect_type,
    SUM(quantity_defect) AS total_defects,
    SUM(quantity_rework) AS total_rework,
    SUM(quantity_scrap)  AS total_scrap,
    ROUND(SUM(quantity_rework) * 100.0 / NULLIF(SUM(quantity_defect),0), 1) AS pct_reworkable
FROM quality_defects
GROUP BY plant_id, line_id, defect_type
ORDER BY plant_id, line_id, total_defects DESC;


-- ────────────────────────────────────────────────
-- 7. COMPARAISON PERFORMANCE PAR ÉQUIPE (SHIFT)
-- ────────────────────────────────────────────────
SELECT
    shift,
    ROUND(AVG(oee), 3)           AS avg_oee,
    ROUND(AVG(availability), 3)  AS avg_availability,
    ROUND(AVG(performance), 3)   AS avg_performance,
    ROUND(AVG(quality), 3)       AS avg_quality,
    COUNT(*)                     AS nb_shifts
FROM oee_daily
GROUP BY shift
ORDER BY avg_oee DESC;


-- ────────────────────────────────────────────────
-- 8. MATRICE LIGNE × MOIS (heatmap data)
-- ────────────────────────────────────────────────
SELECT
    line_id,
    year,
    month,
    ROUND(AVG(oee), 3)   AS avg_oee
FROM oee_daily
GROUP BY line_id, year, month
ORDER BY line_id, year, month;


-- ────────────────────────────────────────────────
-- 9. PANNES : FIABILITÉ & MTTR PAR LIGNE
-- ────────────────────────────────────────────────
SELECT
    s.plant_id,
    s.line_id,
    COUNT(*)                                AS nb_pannes,
    ROUND(AVG(s.duration_min), 1)           AS mttr_moyen_min,
    ROUND(MAX(s.duration_min), 1)           AS mttr_max_min,
    -- MTBF approximatif : temps dispo / nb pannes
    ROUND(
        SUM(o.available_time_min) * 1.0 / NULLIF(COUNT(*), 0) / 60.0
    , 1)                                    AS mtbf_heures
FROM stops s
JOIN (
    SELECT plant_id, line_id, SUM(available_time_min) AS available_time_min
    FROM oee_daily
    GROUP BY plant_id, line_id
) o ON s.plant_id = o.plant_id AND s.line_id = o.line_id
WHERE s.stop_category = 'Panne'
GROUP BY s.plant_id, s.line_id
ORDER BY nb_pannes DESC;


-- ────────────────────────────────────────────────
-- 10. GAINS POTENTIELS SI TRS CIBLE = 85%
-- ────────────────────────────────────────────────
SELECT
    plant_id,
    line_id,
    ROUND(AVG(oee), 3)                          AS oee_actuel,
    0.85                                         AS oee_cible,
    SUM(good_output_units)                       AS production_actuelle,
    ROUND(SUM(good_output_units) * (0.85 / AVG(oee))) AS production_potentielle,
    ROUND(SUM(good_output_units) * (0.85 / AVG(oee)) - SUM(good_output_units)) AS gain_unites
FROM oee_daily
GROUP BY plant_id, line_id
HAVING AVG(oee) < 0.85
ORDER BY gain_unites DESC;
