-- Governed metric definitions over gold.driver_performance.
--
-- Until now every metric was defined once *per surface*: total_points in a mart
-- column, pace_vs_team_pct in a dashboard dataset, and the rule "always use
-- total_points" in the Genie agent's instruction block. Those agreed because one
-- person wrote all three. A metric view makes them agree structurally — the
-- dashboard, Genie and an ad-hoc SQL query resolve the same name to the same
-- expression, enforced by Unity Catalog.
--
--     databricks experimental aitools tools statement submit \
--       --file sql/metrics/driver_performance_metrics.sql --warehouse <id>
--
-- Measures are queried through MEASURE(); SELECT * is not supported.

CREATE OR REPLACE VIEW f1.gold.driver_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: f1.gold.driver_performance
comment: "Governed driver and constructor metrics. One definition, every consumer."

dimensions:
  - name: Season
    expr: season
    comment: "Championship year"
  - name: Round
    expr: round
    comment: "Round number within the season"
  - name: Race
    expr: race_name
  - name: Circuit
    expr: circuit_name
  - name: Country
    expr: circuit_country
  - name: Driver
    expr: driver_name
  - name: Team
    expr: constructor_name_as_of_race
    comment: "The team the driver actually drove for that weekend, from the SCD-2 join. Never their current team."
  - name: Qualifying Stage
    expr: quali_stage_reached
  - name: Result
    expr: CASE
        WHEN dnf_flag THEN 'Retired'
        WHEN finish_position = 1 THEN 'Win'
        WHEN finish_position <= 3 THEN 'Podium'
        WHEN is_points_finish THEN 'Points'
        ELSE 'No points'
        END
    comment: "Outcome bucket for a single drive"

measures:
  - name: Total Points
    expr: SUM(race_points + sprint_points)
    comment: "Race plus sprint. Race points alone leave 13 of 24 drivers short of their official 2024 total."
  - name: Race Points
    expr: SUM(race_points)
  - name: Sprint Points
    expr: SUM(sprint_points)
  - name: Wins
    expr: SUM(CASE WHEN is_win THEN 1 ELSE 0 END)
  - name: Podiums
    expr: SUM(CASE WHEN is_podium THEN 1 ELSE 0 END)
  - name: Starts
    expr: COUNT(1)
    comment: "Car-races: one row per driver per race"
  - name: Retirements
    expr: SUM(CASE WHEN dnf_flag THEN 1 ELSE 0 END)
  - name: DNF Rate
    expr: 100.0 * SUM(CASE WHEN dnf_flag THEN 1 ELSE 0 END) / COUNT(1)
    comment: "Percentage of starts ending in retirement. Safe to re-aggregate at any grain."
  - name: Average Grid
    expr: AVG(grid_position)
  - name: Average Finish
    expr: AVG(finish_position)
  - name: Places Made Up
    expr: AVG(quali_to_finish_delta)
    comment: "Qualifying position minus finishing position. Positive means places gained on Sunday."
  - name: Points Finish Rate
    expr: 100.0 * SUM(CASE WHEN is_points_finish THEN 1 ELSE 0 END) / COUNT(1)
  - name: Points Per Start
    expr: SUM(race_points + sprint_points) / COUNT(1)
    comment: "A ratio, re-aggregated correctly at every grain — the thing a standard view cannot do."
$$
