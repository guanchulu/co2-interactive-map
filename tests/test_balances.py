import unittest

from co2alloc.decision import evaluate_all
from co2alloc.pipeline_cost import pipeline_transport_cost
from co2alloc.profitability import (
    city_profit_recommendations,
    load_profitability_assumptions,
    profit_scan,
)
from co2alloc.scenario import Scenario
from co2alloc.spatial import (
    generate_spatial_candidates,
    greedy_allocate,
    load_destinations,
    load_sources,
    load_transport_modes,
    optimize_allocate,
)


class BalanceTests(unittest.TestCase):
    def test_all_default_pathways_are_valid(self):
        evaluations = evaluate_all(Scenario())
        self.assertGreaterEqual(len(evaluations), 10)
        families = {evaluation.inventory.technology_family for evaluation in evaluations}
        self.assertIn("thermochemical", families)
        self.assertIn("electrochemical", families)
        self.assertIn("photochemical", families)
        for evaluation in evaluations:
            inv = evaluation.inventory
            self.assertGreater(inv.co2_feed_kg, 0)
            self.assertGreaterEqual(evaluation.economics.gross_cost_usd_per_tco2, 0)
            self.assertLessEqual(
                inv.co2_stored_kg
                + inv.co2_released_end_of_life_kg
                + inv.direct_co2_emissions_kg,
                inv.co2_feed_kg * 1.15,
            )

    def test_spatial_candidates_and_allocation_are_nonempty(self):
        sources = load_sources("data/spatial_sources.csv")
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        candidates = generate_spatial_candidates(sources, destinations, modes, Scenario())
        self.assertGreater(len(candidates), 0)
        allocations = greedy_allocate(candidates)
        self.assertGreater(len(allocations), 0)
        self.assertGreater(
            sum(float(row["allocated_mtco2_per_year"]) for row in allocations),
            0,
        )

    def test_spatial_lp_allocation_meets_source_total(self):
        sources = load_sources("data/spatial_sources.csv")
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        candidates = generate_spatial_candidates(sources, destinations, modes, Scenario())
        allocations = optimize_allocate(candidates, minimum_source_fraction=1.0)
        allocated = sum(float(row["allocated_mtco2_per_year"]) for row in allocations)
        available = sum(source.co2_available_mtpa for source in sources)
        self.assertAlmostEqual(allocated, available, places=6)

    def test_spatial_lp_allocation_meets_explicit_target(self):
        sources = load_sources("data/spatial_sources.csv")
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        candidates = generate_spatial_candidates(sources, destinations, modes, Scenario())
        allocations = optimize_allocate(
            candidates,
            minimum_source_fraction=0.0,
            target_total_mtco2_per_year=40.0,
        )
        allocated = sum(float(row["allocated_mtco2_per_year"]) for row in allocations)
        self.assertAlmostEqual(allocated, 40.0, places=6)

    def test_capture_energy_responds_to_destination_electricity(self):
        source = load_sources("data/spatial_sources.csv")[0]
        source_fields = {field: getattr(source, field) for field in source.__dataclass_fields__}
        zero_energy_source = source.__class__(**{**source_fields, "capture_energy_kwh_per_tco2": 0.0})
        high_energy_source = source.__class__(**{**source_fields, "capture_energy_kwh_per_tco2": 1000.0})
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        zero_candidates = generate_spatial_candidates([zero_energy_source], destinations, modes, Scenario())
        high_candidates = generate_spatial_candidates([high_energy_source], destinations, modes, Scenario())

        def by_key(candidates):
            return {
                (
                    candidate.destination.destination_id,
                    candidate.transport_mode.mode,
                    candidate.pathway,
                ): candidate
                for candidate in candidates
            }

        zero_by_key = by_key(zero_candidates)
        high_by_key = by_key(high_candidates)
        sample_key = next(key for key in zero_by_key if key in high_by_key)
        self.assertGreater(
            high_by_key[sample_key].adjusted_gross_cost_usd_per_tco2,
            zero_by_key[sample_key].adjusted_gross_cost_usd_per_tco2,
        )
        self.assertLess(
            high_by_key[sample_key].adjusted_net_avoided_kgco2e_per_tco2,
            zero_by_key[sample_key].adjusted_net_avoided_kgco2e_per_tco2,
        )

    def test_dac_sources_are_loadable(self):
        dac_sources = load_sources("data/dac_sources.csv")
        self.assertGreater(len(dac_sources), 0)
        self.assertTrue(all(source.source_type == "dac" for source in dac_sources))
        self.assertTrue(all(source.capture_energy_kwh_per_tco2 > 0 for source in dac_sources))

    def test_spatial_mode_ignores_generic_transport_to_avoid_double_counting(self):
        sources = load_sources("data/spatial_sources.csv")
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        zero_generic = Scenario(
            co2_transport_distance_km=0.0,
            co2_transport_cost_usd_per_tkm=0.0,
            co2_transport_emissions_kgco2e_per_tkm=0.0,
        )
        huge_generic = Scenario(
            co2_transport_distance_km=9999.0,
            co2_transport_cost_usd_per_tkm=100.0,
            co2_transport_emissions_kgco2e_per_tkm=50.0,
        )
        zero_candidates = generate_spatial_candidates(sources, destinations, modes, zero_generic)
        huge_candidates = generate_spatial_candidates(sources, destinations, modes, huge_generic)
        self.assertEqual(len(zero_candidates), len(huge_candidates))

        def by_key(candidates):
            return {
                (
                    candidate.source.source_id,
                    candidate.destination.destination_id,
                    candidate.transport_mode.mode,
                    candidate.pathway,
                ): candidate
                for candidate in candidates
            }

        zero_by_key = by_key(zero_candidates)
        huge_by_key = by_key(huge_candidates)
        self.assertEqual(set(zero_by_key), set(huge_by_key))
        sample_key = next(iter(zero_by_key))
        self.assertAlmostEqual(
            zero_by_key[sample_key].adjusted_net_cost_usd_per_tco2,
            huge_by_key[sample_key].adjusted_net_cost_usd_per_tco2,
            places=9,
        )
        self.assertAlmostEqual(
            zero_by_key[sample_key].adjusted_net_avoided_kgco2e_per_tco2,
            huge_by_key[sample_key].adjusted_net_avoided_kgco2e_per_tco2,
            places=9,
        )

    def test_pipeline_transport_cost_has_scale_economies(self):
        short = pipeline_transport_cost(
            distance_km=100.0,
            flow_mtpa=5.0,
            electricity_price_usd_per_mwh=60.0,
            discount_rate=0.08,
            lifetime_years=20,
        )
        long = pipeline_transport_cost(
            distance_km=500.0,
            flow_mtpa=5.0,
            electricity_price_usd_per_mwh=60.0,
            discount_rate=0.08,
            lifetime_years=20,
        )
        large_flow = pipeline_transport_cost(
            distance_km=100.0,
            flow_mtpa=20.0,
            electricity_price_usd_per_mwh=60.0,
            discount_rate=0.08,
            lifetime_years=20,
        )
        self.assertGreater(long.levelized_cost_usd_per_tco2, short.levelized_cost_usd_per_tco2)
        self.assertLess(large_flow.levelized_cost_usd_per_tco2, short.levelized_cost_usd_per_tco2)

    def test_profitability_scan_outputs_margin_and_city_recommendation(self):
        sources = load_sources("data/spatial_sources.csv")
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        candidates = generate_spatial_candidates(sources, destinations, modes, Scenario())
        assumptions = load_profitability_assumptions()
        records = profit_scan(candidates, assumptions, year=2030, target_market="china")
        self.assertGreater(len(records), 0)
        self.assertIn("margin_usd_per_tco2", records[0])
        self.assertIn("break_even_product_price_usd_per_kg", records[0])
        recommendations = city_profit_recommendations(records)
        self.assertGreater(len(recommendations), 0)
        self.assertIn("recommended_base", recommendations[0])

    def test_profitability_responds_to_product_price_case(self):
        sources = load_sources("data/spatial_sources.csv")
        destinations = load_destinations("data/spatial_destinations.csv")
        modes = load_transport_modes("data/transport_modes.csv")
        candidates = generate_spatial_candidates(sources, destinations, modes, Scenario())
        assumptions = load_profitability_assumptions()
        low = profit_scan(
            candidates,
            assumptions,
            year=2030,
            target_market="china",
            price_case="low",
        )
        high = profit_scan(
            candidates,
            assumptions,
            year=2030,
            target_market="china",
            price_case="high",
        )
        low_best = max(float(row["margin_usd_per_tco2"]) for row in low)
        high_best = max(float(row["margin_usd_per_tco2"]) for row in high)
        self.assertGreaterEqual(high_best, low_best)


if __name__ == "__main__":
    unittest.main()
