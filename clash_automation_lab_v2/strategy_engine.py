"""Conservative, observation-driven automation policy for Clash Automation Lab.

This module deliberately separates game-state recognition from decision making.
It never guesses a screen state: callers must provide observations backed by
visible UI evidence (for example, configured screenshot templates).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence


class Screen(str, Enum):
    HOME = "home"
    SEARCH = "search"
    BATTLE = "battle"
    UPGRADE_MENU = "upgrade_menu"
    TRAINING = "training"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    WAIT = "wait"
    COLLECT = "collect"
    OPEN_ATTACK = "open_attack"
    START_SEARCH = "start_search"
    NEXT_BASE = "next_base"
    DEPLOY = "deploy"
    END_BATTLE = "end_battle"
    OPEN_BUILDERS = "open_builders"
    UPGRADE = "upgrade"
    TRAIN_ARMY = "train_army"
    STOP = "stop"


@dataclass(frozen=True)
class Candidate:
    """A visually confirmed action target; coordinates are screenshot pixels."""
    name: str
    x: int
    y: int
    cost_gold: int = 0
    cost_elixir: int = 0
    cost_dark: int = 0
    category: str = "other"
    confidence: float = 1.0


@dataclass(frozen=True)
class GameObservation:
    """Only facts positively recognized from the current screenshot."""
    screen: Screen = Screen.UNKNOWN
    confidence: float = 0.0
    gold: Optional[int] = None
    elixir: Optional[int] = None
    dark_elixir: Optional[int] = None
    army_ready: Optional[bool] = None
    camp_full: Optional[bool] = None
    builders_available: Optional[int] = None
    shield_active: Optional[bool] = None
    buttons: Mapping[str, Candidate] = field(default_factory=dict)
    upgrade_candidates: Sequence[Candidate] = field(default_factory=tuple)
    troop_slots: Sequence[Candidate] = field(default_factory=tuple)
    deployment_points: Sequence[tuple[int, int]] = field(default_factory=tuple)
    battle_ended: Optional[bool] = None


@dataclass(frozen=True)
class PolicyConfig:
    min_gold: int = 100_000
    min_elixir: int = 100_000
    min_dark_elixir: int = 0
    min_candidate_confidence: float = 0.88
    attack_when_loot_low: bool = True
    collect_resources: bool = True
    upgrade_buildings: bool = True
    train_army: bool = True
    deploy_pattern: str = "two_sides"
    upgrade_priority: tuple[str, ...] = (
        "hero", "laboratory", "army", "offense", "resource", "defense", "wall"
    )
    max_searches_per_cycle: int = 30


@dataclass(frozen=True)
class Decision:
    action: ActionType
    reason: str
    target: Optional[Candidate] = None
    points: tuple[tuple[int, int], ...] = ()
    data: Mapping[str, Any] = field(default_factory=dict)


class StrategyEngine:
    """Rule-based decision core; every tap target must be visually confirmed."""

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()
        self.searches_this_cycle = 0

    def reset_cycle(self) -> None:
        self.searches_this_cycle = 0

    def _button(self, observation: GameObservation, name: str) -> Optional[Candidate]:
        candidate = observation.buttons.get(name)
        if candidate and candidate.confidence >= self.config.min_candidate_confidence:
            return candidate
        return None

    def _has_enough_loot(self, observation: GameObservation) -> Optional[bool]:
        # Missing OCR values are unknown, not zero.
        if observation.gold is None or observation.elixir is None:
            return None
        return (
            observation.gold >= self.config.min_gold
            and observation.elixir >= self.config.min_elixir
            and (observation.dark_elixir or 0) >= self.config.min_dark_elixir
        )

    def _choose_upgrade(self, observation: GameObservation) -> Optional[Candidate]:
        affordable = []
        for item in observation.upgrade_candidates:
            if item.confidence < self.config.min_candidate_confidence:
                continue
            if observation.gold is None or observation.elixir is None:
                continue
            if item.cost_gold > observation.gold or item.cost_elixir > observation.elixir:
                continue
            if item.cost_dark > (observation.dark_elixir or 0):
                continue
            affordable.append(item)
        rank = {name: index for index, name in enumerate(self.config.upgrade_priority)}
        affordable.sort(key=lambda item: (rank.get(item.category, len(rank)), -item.confidence))
        return affordable[0] if affordable else None

    def decide(self, observation: GameObservation) -> Decision:
        """Return one safe next action, or WAIT/STOP when evidence is insufficient."""
        if observation.screen == Screen.UNKNOWN or observation.confidence < 0.70:
            return Decision(ActionType.STOP, "لم يتم التعرف على شاشة اللعبة بثقة كافية؛ أوقفت المحرك لتجنب الضغط الخاطئ.")

        if observation.screen == Screen.BATTLE:
            if observation.battle_ended is True:
                target = self._button(observation, "return_home")
                return Decision(ActionType.END_BATTLE, "تم التأكد من انتهاء المعركة؛ العودة متاحة.", target)
            if not observation.troop_slots or not observation.deployment_points:
                return Decision(ActionType.WAIT, "المعركة ظاهرة لكن مواقع القوات أو نقاط النشر غير مؤكدة.")
            slots = [s for s in observation.troop_slots if s.confidence >= self.config.min_candidate_confidence]
            if not slots:
                return Decision(ActionType.WAIT, "لم يتم التعرف على خانة قوات موثوقة.")
            points = list(observation.deployment_points)
            if self.config.deploy_pattern == "four_sides" and len(points) >= 4:
                points = points[:4]
            elif len(points) >= 2:
                points = [points[0], points[-1]]
            else:
                points = points[:1]
            return Decision(
                ActionType.DEPLOY,
                "نشر تدريجي على نقاط ظاهرة ومحددة؛ يجب التحقق من الشاشة بعد كل دفعة.",
                target=slots[0],
                points=tuple(points),
                data={"troop_slots": len(slots), "pattern": self.config.deploy_pattern},
            )

        if observation.screen == Screen.SEARCH:
            enough = self._has_enough_loot(observation)
            if enough is True:
                target = self._button(observation, "attack")
                if target:
                    return Decision(ActionType.START_SEARCH, "الموارد المرصودة تحقق الحدود المحددة؛ اختيار الهجوم.", target)
                return Decision(ActionType.WAIT, "الموارد مناسبة لكن زر الهجوم لم يُتعرف عليه بثقة.")
            if enough is None:
                return Decision(ActionType.WAIT, "تعذر قراءة الموارد؛ لن أتجاوز القرية بناءً على تخمين.")
            if self.searches_this_cycle >= self.config.max_searches_per_cycle:
                return Decision(ActionType.STOP, "تم بلوغ حد البحث في هذه الدورة.")
            target = self._button(observation, "next_base")
            if target:
                self.searches_this_cycle += 1
                return Decision(ActionType.NEXT_BASE, "الموارد أقل من الحد الأدنى؛ البحث عن قرية أخرى.", target)
            return Decision(ActionType.WAIT, "لم يتم التعرف على زر البحث التالي بثقة.")

        if observation.screen == Screen.HOME:
            if self.config.collect_resources:
                target = self._button(observation, "collect")
                if target:
                    return Decision(ActionType.COLLECT, "جمع الموارد لأن زر الجمع تم التعرف عليه.", target)
            if self.config.upgrade_buildings and observation.builders_available is not None and observation.builders_available > 0:
                target = self._button(observation, "builders")
                if target:
                    return Decision(ActionType.OPEN_BUILDERS, "يوجد بنّاء متاح؛ فتح قائمة البناء للتحقق من الترقيات.", target)
            if self.config.train_army and observation.camp_full is False:
                target = self._button(observation, "train")
                if target:
                    return Decision(ActionType.TRAIN_ARMY, "معسكر الجيش غير ممتلئ؛ فتح التدريب.", target)
            enough = self._has_enough_loot(observation)
            if self.config.attack_when_loot_low and observation.army_ready is True and enough is False:
                target = self._button(observation, "attack_menu")
                if target:
                    return Decision(ActionType.OPEN_ATTACK, "الجيش جاهز؛ فتح الهجوم للبحث عن موارد.", target)
            return Decision(ActionType.WAIT, "لا توجد مهمة آمنة مؤكدة الآن؛ إعادة فحص الحالة بعد الانتظار.")

        if observation.screen == Screen.UPGRADE_MENU:
            if observation.builders_available == 0:
                return Decision(ActionType.WAIT, "لا يوجد بنّاء متاح؛ لن أبدأ ترقية غير ممكنة.")
            candidate = self._choose_upgrade(observation)
            if candidate:
                return Decision(ActionType.UPGRADE, "اختيار ترقية متاحة وقابلة للتحمل حسب الأولويات.", candidate)
            return Decision(ActionType.WAIT, "لا توجد ترقية تم التعرف عليها وتأكيد القدرة على دفع تكلفتها.")

        if observation.screen == Screen.TRAINING:
            target = self._button(observation, "train_confirm")
            if target:
                return Decision(ActionType.TRAIN_ARMY, "تأكيد التدريب بعد التعرف على زر التدريب.", target)
            return Decision(ActionType.WAIT, "قائمة التدريب مفتوحة لكن زر التأكيد غير مؤكد.")

        return Decision(ActionType.WAIT, "انتظار الملاحظة التالية.")


class VerifiedRunner:
    """Executes one decision at a time and requires caller-side post-action verification."""

    def __init__(self, engine: StrategyEngine, execute: Callable[[Decision], bool],
                 observe: Callable[[], GameObservation], max_steps: int = 1000):
        self.engine = engine
        self.execute = execute
        self.observe = observe
        self.max_steps = max(1, int(max_steps))
        self.stopped_reason = ""

    def run(self, cancelled: Callable[[], bool] = lambda: False,
            on_decision: Callable[[Decision], None] = lambda decision: None) -> str:
        for _ in range(self.max_steps):
            if cancelled():
                self.stopped_reason = "أوقف المستخدم التشغيل."
                return self.stopped_reason
            observation = self.observe()
            decision = self.engine.decide(observation)
            on_decision(decision)
            if decision.action == ActionType.STOP:
                self.stopped_reason = decision.reason
                return self.stopped_reason
            if decision.action == ActionType.WAIT:
                # The host is responsible for a cancellable delay before the next observation.
                continue
            if not self.execute(decision):
                self.stopped_reason = "فشل تنفيذ الإجراء؛ أوقف المحرك بأمان."
                return self.stopped_reason
            # Loop always obtains a fresh observation before any subsequent action.
        self.stopped_reason = "تم بلوغ حد الخطوات الآمن."
        return self.stopped_reason
