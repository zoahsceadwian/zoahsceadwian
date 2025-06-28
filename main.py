"""A basic simulation of digital characters in a simplified world.

This program implements a minimal subset of the ideas provided:
 - Characters belong to professions and act once per cycle.
 - Actions can be self-focused, professional, or interactive.
 - Characters earn credits from professional actions. Every 10 credits
   are exchanged for a "block" recorded in a chain log.
 - The program prints a message whenever such a block is produced.

No external dependencies are required.
"""

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# List of professions (simplified from the description)
PROFESSIONS = [
    "Gatherer", "Miner", "Farmer", "Lumberjack", "Signalist",
    "Constructor", "Refiner", "Craftsman", "Echokeeper",
    "Cartographer", "Dreamweaver", "Digital Landscaper", "Cook",
    "Codehealer", "Merchant",
]

# Basic attributes for each character
ATTRIBUTE_NAMES = [
    "stamina", "metabolism", "strength", "perception", "speed",
    "intelligence", "creativity", "logic", "technique", "dedication",
    "industriousness", "hacking", "harmony", "precision", "vision",
    "alignment", "openness", "conscientiousness", "extraversion",
    "agreeableness", "neuroticism",
]


@dataclass
class Outcome:
    """Result of an interaction."""
    description: str
    weight: int
    initiator_mood: int = 0
    target_mood: int = 0
    relationship_change: int = 0
    attr_changes: Dict[str, int] = field(default_factory=dict)
    target_check: Optional[Callable[["Character"], bool]] = None


@dataclass
class Interaction:
    """An interaction with personality requirements and outcomes."""
    name: str
    initiator_check: Callable[["Character"], bool]
    outcomes: List[Outcome]

# Basic interaction library with "greet" and "compliment".
INTERACTIONS: List[Interaction] = [
    Interaction(
        name="Greet",
        initiator_check=lambda c: c.attributes.get("extraversion", 10) > 5,
        outcomes=[
            Outcome(
                description="Friendly exchange",
                weight=70,
                initiator_mood=1,
                target_mood=1,
                relationship_change=1,
            ),
            Outcome(
                description="Cold shoulder",
                weight=30,
                initiator_mood=-1,
                relationship_change=-1,
            ),
        ],
    ),
    Interaction(
        name="Compliment",
        initiator_check=lambda c: c.attributes.get("extraversion", 10) > 10,
        outcomes=[
            Outcome(
                description="Sincere Gratitude",
                weight=60,
                initiator_mood=3,
                target_mood=5,
                relationship_change=2,
                attr_changes={"openness": 1},
            ),
            Outcome(
                description="Awkward Response",
                weight=30,
            ),
            Outcome(
                description="Suspicious Reaction",
                weight=10,
                initiator_mood=-2,
                target_mood=-2,
                relationship_change=-2,
            ),
        ],
    ),
]

# Additional interaction names requested. They use a generic template to
# keep the simulation lightweight while covering many possibilities.
ADDITIONAL_INTERACTIONS = [
    "AskQuestion", "Confide", "GiveAdvice", "SmallTalk", "AskFavor",
    "Flirt", "Mock", "Boast", "Gossip", "Humblebrag", "Flatter",
    "Encourage", "Praise", "Scold", "Thank", "Insult", "Apologize",
    "RevealSecret", "Console", "Taunt", "Tease", "OfferHelp",
    "Intimidate", "MakeRequest", "Warn", "Threaten", "TakeAdvice",
    "Bribe", "PraiseWork", "CriticizeWork", "ShareInformation", "Teach",
    "Learn", "SuggestPlan", "PlanTogether", "Congratulate",
    "Celebrate", "Complain", "VentFrustration", "EncourageRisk",
    "DiscourageRisk", "BorrowItem", "LendItem", "StealItem",
    "AccuseTheft", "ForgiveTheft", "ChallengeDuel", "AcceptDuel",
    "DeclineDuel", "Bow", "ShakeHands", "HighFive", "FistBump", "Hug",
    "KissOnCheek", "Wink", "Nod", "ShakeHead", "EyeRoll", "Sigh",
    "Whistle", "Hum", "Sing", "DanceInvite", "Storytell",
    "RecitePoem", "Joke", "LaughTogether", "Eulogize", "Recruit",
    "Dismiss", "Betray", "Forgive", "MakePromise", "CommendBravery",
    "PraiseCharacter", "WarnOfDanger", "CriticizeCharacter", "ShareRumor",
    "AskOrigin", "ConfirmRumor", "ShareOrigin", "DenyRumor",
]

NEGATIVE_INTERACTIONS = {
    "Mock", "Insult", "Taunt", "Tease", "Intimidate", "Threaten",
    "CriticizeWork", "AccuseTheft", "Betray", "Dismiss",
    "CriticizeCharacter", "ChallengeDuel",
}


def make_generic_interaction(name: str) -> Interaction:
    """Return a simple interaction with generic outcomes."""

    if name in NEGATIVE_INTERACTIONS:
        def check(c, thr: int = 6) -> bool:
            return (
                c.attributes.get("extraversion", 10) >= thr
                and c.attributes.get("agreeableness", 10) <= 10
            )
        outcomes = [
            Outcome("Hostile exchange", weight=50, initiator_mood=-1,
                    target_mood=-2, relationship_change=-2),
            Outcome("Ignored", weight=30),
            Outcome("Backfires", weight=20, initiator_mood=-2,
                    relationship_change=-1),
        ]
    else:
        def check(c, thr: int = 6) -> bool:
            return c.attributes.get("extraversion", 10) >= thr
        outcomes = [
            Outcome("Pleasant response", weight=60, initiator_mood=2,
                    target_mood=2, relationship_change=1),
            Outcome("Neutral response", weight=30),
            Outcome("Awkward moment", weight=10, initiator_mood=-1,
                    target_mood=-1),
        ]

    return Interaction(name=name, initiator_check=check, outcomes=outcomes)


for _name in ADDITIONAL_INTERACTIONS:
    if _name == "Compliment" or _name == "Greet":
        continue
    INTERACTIONS.append(make_generic_interaction(_name))

@dataclass
class Character:
    name: str
    profession: str
    energy: int = 100
    life: int = 100
    charge: int = 100
    battery: int = 100
    mood: int = 100
    attributes: Dict[str, int] = field(default_factory=dict)
    credits: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)  # 3 slots allowed
    relationships: Dict[str, int] = field(default_factory=dict)
    needs_resource: Optional[str] = None
    done: bool = False

    def __post_init__(self):
        # Randomly assign attributes in range 5-15 (approx average 10)
        self.attributes = {
            attr: random.randint(5, 15) for attr in ATTRIBUTE_NAMES
        }

    def choose_action(self) -> str:
        """Determine which type of action to perform this cycle."""
        weights = {
            "self": 10,
            "professional": 10,
            "interactive": 10,
        }

        if self.energy < 50:
            weights["self"] += 30
        if self.charge < 50:
            weights["self"] += 30
        if self.mood < 50:
            weights["interactive"] += 30

        total = sum(weights.values())
        choice = random.randint(1, total)
        cumulative = 0
        for action, weight in weights.items():
            cumulative += weight
            if choice <= cumulative:
                return action
        return "self"  # Fallback

    def perform_self_action(self):
        """Personal upkeep to restore mood, energy, and charge."""
        self.energy = min(100, self.energy + 10)
        self.charge = min(100, self.charge + 10)
        self.mood = min(100, self.mood + 5)
        self.done = True

    def perform_professional_action(self, cycle: int, chain: List[str]):
        """Work action generating credits and consuming resources."""
        self.energy = max(0, self.energy - (21 - self.attributes["metabolism"]))
        self.charge = max(0, self.charge - (25 - self.attributes["stamina"]))
        self.mood = max(0, self.mood - 1)
        self.credits += 1
        if self.credits >= 10:
            block = f"cycle{cycle}_{self.name}_{self.profession}"
            chain.append(block)
            print(f"Block produced: {block}")
            self.credits -= 10
        self.done = True


class World:
    def __init__(self):
        self.characters: List[Character] = []
        self.chain: List[str] = []
        self.cycle = 0
        self._init_characters()

    def _init_characters(self):
        """Create two characters for each profession."""
        counter = 0
        for profession in PROFESSIONS:
            for _ in range(2):
                name = f"toon{counter:07d}"
                self.characters.append(Character(name=name, profession=profession))
                counter += 1

    def _choose_target(self, initiator: Character) -> Optional[Character]:
        """Select an interaction partner based on relationships."""
        population = [c for c in self.characters if c is not initiator and not c.done]
        if not population:
            return None
        sample = random.sample(population, k=min(10, len(population)))
        if not sample:
            return None
        target = max(sample, key=lambda c: abs(initiator.relationships.get(c.name, 0)))
        return target

    def perform_interaction(self, initiator: Character) -> bool:
        """Handle an interactive action, returning True if executed."""
        target = self._choose_target(initiator)
        if target is None:
            return False
        interaction = random.choice(INTERACTIONS)
        if not interaction.initiator_check(initiator):
            return False

        weights = [o.weight for o in interaction.outcomes]
        outcome = random.choices(interaction.outcomes, weights=weights)[0]
        attempts = 0
        while outcome.target_check and not outcome.target_check(target) and attempts < 5:
            outcome = random.choices(interaction.outcomes, weights=weights)[0]
            attempts += 1

        initiator.mood = max(0, min(100, initiator.mood + outcome.initiator_mood))
        target.mood = max(0, min(100, target.mood + outcome.target_mood))
        initiator.relationships[target.name] = initiator.relationships.get(target.name, 0) + outcome.relationship_change
        target.relationships[initiator.name] = target.relationships.get(initiator.name, 0) + outcome.relationship_change
        for attr, delta in outcome.attr_changes.items():
            current = target.attributes.get(attr, 10)
            target.attributes[attr] = max(1, min(20, current + delta))

        print(f"{initiator.name} -> {target.name}: {interaction.name} ({outcome.description})")
        # Provide detailed feedback about the outcome
        details = []
        if outcome.initiator_mood or outcome.target_mood:
            details.append(
                f"mood {initiator.name}:{initiator.mood} {target.name}:{target.mood}"
            )
        if outcome.relationship_change:
            rel = initiator.relationships.get(target.name, 0)
            details.append(f"relationship now {rel}")
        if outcome.attr_changes:
            attr_str = ", ".join(
                f"{k}:{target.attributes.get(k)}" for k in outcome.attr_changes
            )
            details.append(f"attributes -> {attr_str}")
        if details:
            print("  " + "; ".join(details))
        initiator.done = True
        target.done = True
        return True

    def run_cycle(self):
        """Run a single cycle where each character acts once."""
        self.cycle += 1
        order = self.characters[:]
        random.shuffle(order)
        for char in order:
            if char.done:
                continue
            action = char.choose_action()
            if action == "interactive":
                if not self.perform_interaction(char):
                    char.perform_self_action()
            elif action == "professional":
                char.perform_professional_action(self.cycle, self.chain)
            else:
                char.perform_self_action()
        # reset done flags for next cycle
        for char in self.characters:
            char.done = False

    def run(self, cycles: int = 10):
        for _ in range(cycles):
            self.run_cycle()
        self.summary()

    def summary(self):
        """Print a summary of all characters and their attributes."""
        print("\nSimulation complete. Final character states:")
        for c in self.characters:
            attrs = ", ".join(f"{k}:{v}" for k, v in sorted(c.attributes.items()))
            print(
                f"{c.name} ({c.profession}) mood:{c.mood} energy:{c.energy} "
                f"charge:{c.charge} credits:{c.credits} | {attrs}"
            )


if __name__ == "__main__":
    world = World()
    world.run(10)
