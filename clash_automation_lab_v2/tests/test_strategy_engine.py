import unittest

from strategy_engine import (
    ActionType, Candidate, GameObservation, PolicyConfig, Screen, StrategyEngine
)


def target(name, x=10, y=20, confidence=0.99, **kwargs):
    return Candidate(name=name, x=x, y=y, confidence=confidence, **kwargs)


class StrategyEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = StrategyEngine()

    def test_unknown_screen_stops_safely(self):
        decision = self.engine.decide(GameObservation(screen=Screen.UNKNOWN, confidence=0.99))
        self.assertEqual(decision.action, ActionType.STOP)

    def test_search_does_not_skip_when_resource_reading_is_missing(self):
        obs = GameObservation(
            screen=Screen.SEARCH, confidence=0.99,
            buttons={"next_base": target("next")}
        )
        self.assertEqual(self.engine.decide(obs).action, ActionType.WAIT)

    def test_search_skips_base_when_loot_is_below_threshold(self):
        obs = GameObservation(
            screen=Screen.SEARCH, confidence=0.99, gold=1, elixir=1,
            buttons={"next_base": target("next")}
        )
        decision = self.engine.decide(obs)
        self.assertEqual(decision.action, ActionType.NEXT_BASE)
        self.assertEqual(self.engine.searches_this_cycle, 1)

    def test_search_attacks_only_when_loot_threshold_met(self):
        obs = GameObservation(
            screen=Screen.SEARCH, confidence=0.99,
            gold=200_000, elixir=200_000,
            buttons={"attack": target("attack")}
        )
        self.assertEqual(self.engine.decide(obs).action, ActionType.START_SEARCH)

    def test_low_confidence_button_is_never_used(self):
        obs = GameObservation(
            screen=Screen.SEARCH, confidence=0.99, gold=0, elixir=0,
            buttons={"next_base": target("next", confidence=0.2)}
        )
        self.assertEqual(self.engine.decide(obs).action, ActionType.WAIT)

    def test_battle_requires_confirmed_troop_slot_and_deployment_points(self):
        obs = GameObservation(screen=Screen.BATTLE, confidence=0.99)
        self.assertEqual(self.engine.decide(obs).action, ActionType.WAIT)

    def test_battle_deploys_only_to_provided_points(self):
        slot = target("troop", 100, 700)
        obs = GameObservation(
            screen=Screen.BATTLE, confidence=0.99,
            troop_slots=(slot,), deployment_points=((100, 500), (900, 500))
        )
        decision = self.engine.decide(obs)
        self.assertEqual(decision.action, ActionType.DEPLOY)
        self.assertEqual(decision.points, ((100, 500), (900, 500)))
        self.assertEqual(decision.target, slot)

    def test_upgrade_respects_affordability_and_priority(self):
        engine = StrategyEngine(PolicyConfig(upgrade_priority=("hero", "army")))
        obs = GameObservation(
            screen=Screen.UPGRADE_MENU, confidence=0.99, gold=100, elixir=100,
            builders_available=1,
            upgrade_candidates=(
                target("army", category="army", cost_gold=50),
                target("hero", category="hero", cost_elixir=50),
                target("too expensive", category="hero", cost_gold=1000),
            )
        )
        decision = engine.decide(obs)
        self.assertEqual(decision.action, ActionType.UPGRADE)
        self.assertEqual(decision.target.name, "hero")

    def test_upgrade_does_not_guess_when_resources_are_unknown(self):
        obs = GameObservation(
            screen=Screen.UPGRADE_MENU, confidence=0.99, builders_available=1,
            upgrade_candidates=(target("hero", category="hero"),)
        )
        self.assertEqual(self.engine.decide(obs).action, ActionType.WAIT)

    def test_builder_available_opens_builders_only_if_button_seen(self):
        obs = GameObservation(
            screen=Screen.HOME, confidence=0.99, builders_available=1,
            gold=0, elixir=0
        )
        self.assertEqual(self.engine.decide(obs).action, ActionType.WAIT)


if __name__ == "__main__":
    unittest.main()
