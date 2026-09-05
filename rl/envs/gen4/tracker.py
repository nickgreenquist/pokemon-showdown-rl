"""Per-battle state poke-env 0.15.0 does not track for gen 4, read from the
raw protocol log (`battle._replay_data`, appended before poke-env's ignore
filter) — docs/design_gen4/pokeenv_gen4_survey.md §6 gaps G2–G6, plus what the
2026-09-04 local tapes showed the protocol actually carries:

  weather      `-weather|X|[from] ability: Y` marks ability-set (permanent at
               gen <= 5) weather; `-weather|X|[upkeep]` every residual turn
               (poke-env restamps its turn from THAT, so its stamp carries no
               duration — measured: stamp age always 0 or 1 over 760 battles).
               Here: the set turn and an `indefinite` bit.
  sleep        gen-4 sleep is 1–4 attempts lost, the mon acts on the wake
               attempt, and the counter survives switches. The exact count is
               the number of `cant|X|slp` lines since `-status|X|slp`: one per
               attempt, INCLUDING the Sleep Talk turn (the sim adds `cant`
               before the sleepUsable check, showdown/data/mods/gen4/
               conditions.ts:41-47). poke-env's `status_counter` bumps on that
               `cant` AND on both `|move|` lines of a Sleep Talk turn (survey
               G3) — measured reading 4 after two sleeping turns.
  items        `-enditem` (eaten, Knock Off, Custap, Focus Sash) and `-item`
               (Trick, Switcheroo, Frisk) give an original-item memory and a
               `consumed` bit; poke-env collapses eaten / knocked-off / none to
               `None` (survey G4).
  Encore       `-start|X|Encore` names no move — it is not "dropped by
               poke-env", the sim never sends it (measured 42 `-start|Encore`
               lines, all 4 fields). The encored move is the target's last
               `|move|` line.
  Substitute   `-activate|X|Substitute|[damage]` carries no amount, so sub HP
               is unobservable; the number of hits taken is. (Corrects
               encoder_requirements.md A10's "sub HP scalar".)
  Choice lock  the holder is locked into the FIRST move it used since its
               last switch-in; tracked per mon so a known Choice item plus a
               move since switch-in gives `choice_locked`.
  Flash Fire   `-start|X|ability: Flash Fire` .. `-end|X|ability: Flash Fire`
               on switch-out; poke-env ends it after one Fire move (G6).
  abilities    `-activate|X|ability: Y` reveals Sticky Hold, Forewarn,
               Synchronize, Shed Skin, Hydration, Suction Cups without poke-env
               setting `mon.ability` (survey §3.2).
  rampage lock Outrage / Thrash / Petal Dance lock the user for 2–3 turns.
               Showdown announces neither start nor end of `lockedmove`
               (continuation turns carry `|move|X|Outrage|Y|[from]lockedmove`,
               which poke-env strips, so Effect.LOCKED_MOVE is never set —
               0 hits over 41,908 decisions). Derived here: set on the move
               line, cleared by the `[fatigue]` confusion, a switch, a faint,
               a `cant`, a `-miss` / `-fail` by the user, a different move,
               or three turns (the sim's cap; the gen-4 mod drops the lock
               of a sleeping user, so a Sleep Talk-called rampage never locks).

Idents are normalised to poke-env's team keys ('p1a: Name' -> 'p1: Name').
`update(battle)` is idempotent per line (a cursor), so calling it at every
decision is exact and cheap.
"""

from __future__ import annotations

from rl.envs.gen4.vocab import to_id


def norm_ident(ident: str) -> str:
    """'p1a: Gengar' -> 'p1: Gengar' (the key poke-env's team dicts use)."""
    if len(ident) > 3 and ident[0] == "p" and ident[2] in "abc" and ident[3] == ":":
        return ident[:2] + ident[3:]
    return ident


def _from_cause(sm: list[str]) -> str:
    for field in sm[3:]:
        if field.startswith("[from]"):
            return field[6:].strip()
    return ""


class BattleTracker:
    """State for ONE battle object (one seat's view). Construct per battle,
    call `update(battle)` before encoding."""

    __slots__ = (
        "_cursor", "turn", "weather", "weather_start", "weather_indefinite",
        "first_move_since_switch", "last_move", "sleep_attempts", "sub_hits",
        "flash_fire", "original_item", "consumed", "encored_move", "revealed_ability",
        "wish_pending", "locked_move",
    )

    def __init__(self):
        self._cursor = 0
        self.turn = 0
        self.weather: str | None = None
        self.weather_start: int | None = None
        self.weather_indefinite = False
        self.first_move_since_switch: dict[str, str] = {}
        self.last_move: dict[str, str] = {}
        self.sleep_attempts: dict[str, int] = {}
        self.sub_hits: dict[str, int] = {}
        self.flash_fire: set[str] = set()
        self.original_item: dict[str, str] = {}
        self.consumed: set[str] = set()
        self.encored_move: dict[str, str] = {}
        self.revealed_ability: dict[str, str] = {}
        # side ('p1' / 'p2') -> turn a Wish / Healing Wish was set; poke-env
        # tracks no slot conditions (Move.slot_condition exists, the battle
        # holds no dict), so the pending heal is invisible without this
        self.wish_pending: dict[str, int] = {}
        # ident -> (rampage move, turn it started)
        self.locked_move: dict[str, tuple[str, int]] = {}

    def update(self, battle) -> None:
        log = battle._replay_data
        for sm in log[self._cursor:]:
            if len(sm) < 3:
                continue
            self._apply(sm)
        self._cursor = len(log)

    def _apply(self, sm: list[str]) -> None:
        tag = sm[1]
        self._reveal_from_cause(sm)
        if tag == "turn":
            self.turn = int(sm[2])
            # a Wish resolves at the end of the turn after it was set
            for side, t in list(self.wish_pending.items()):
                if self.turn > t + 1:
                    del self.wish_pending[side]
            for ident, (_, t0) in list(self.locked_move.items()):
                if self.turn > t0 + 2:  # a rampage is at most three turns
                    del self.locked_move[ident]
        elif tag in ("switch", "drag"):
            ident = norm_ident(sm[2])
            self.first_move_since_switch.pop(ident, None)
            self.last_move.pop(ident, None)
            self.sub_hits.pop(ident, None)
            self.flash_fire.discard(ident)
            self.encored_move.pop(ident, None)
            self.locked_move.pop(ident, None)
            # sleep_attempts deliberately kept: gen-4 sleep does not reset on switch
        elif tag in ("faint", "-miss", "-fail"):
            self.locked_move.pop(norm_ident(sm[2]), None)  # `-miss|SOURCE|TARGET`
        elif tag == "move":
            if len(sm) < 4:
                return
            ident = norm_ident(sm[2])
            move = to_id(sm[3])
            cause = _from_cause(sm)
            if move in ("wish", "healingwish") and not any(f in ("[still]", "[miss]") for f in sm[4:]):
                self.wish_pending[ident[:2]] = self.turn
            if "Sleep Talk" in cause:
                # the called move: the mon's Choice lock and Encore target stay
                # on Sleep Talk itself, which the preceding line recorded
                self.last_move[ident] = move
                return
            self.last_move[ident] = move
            self.first_move_since_switch.setdefault(ident, move)
            if move in _RAMPAGE and not any(f in ("[miss]", "[still]", "[notarget]") for f in sm[4:]):
                self.locked_move.setdefault(ident, (move, self.turn))  # continuation lines keep the start
            elif ident in self.locked_move and self.locked_move[ident][0] != move:
                del self.locked_move[ident]
        elif tag == "-status":
            if len(sm) > 3 and sm[3] == "slp":
                self.sleep_attempts[norm_ident(sm[2])] = 0
        elif tag == "cant":
            ident = norm_ident(sm[2])
            self.locked_move.pop(ident, None)  # sleep / paralysis / flinch end a rampage
            if len(sm) > 3 and sm[3] == "slp":
                self.sleep_attempts[ident] = self.sleep_attempts.get(ident, 0) + 1
        elif tag == "-curestatus":
            if len(sm) > 3 and sm[3] == "slp":
                self.sleep_attempts.pop(norm_ident(sm[2]), None)
        elif tag == "-start":
            if len(sm) < 4:
                return
            ident, effect = norm_ident(sm[2]), sm[3]
            if effect == "Substitute":
                self.sub_hits[ident] = 0
            elif effect == "confusion" and "[fatigue]" in sm[4:]:
                self.locked_move.pop(ident, None)
            elif effect == "Encore":
                last = self.last_move.get(ident)
                if last:
                    self.encored_move[ident] = last
            elif effect == "ability: Flash Fire":
                self.flash_fire.add(ident)
        elif tag == "-end":
            if len(sm) < 4:
                return
            ident, effect = norm_ident(sm[2]), sm[3]
            if effect == "Substitute":
                self.sub_hits.pop(ident, None)
            elif effect == "Encore":
                self.encored_move.pop(ident, None)
            elif effect == "ability: Flash Fire":
                self.flash_fire.discard(ident)
        elif tag == "-activate":
            if len(sm) < 4:
                return
            ident, effect = norm_ident(sm[2]), sm[3]
            if effect == "Substitute" and "[damage]" in sm[4:]:
                self.sub_hits[ident] = self.sub_hits.get(ident, 0) + 1
            elif effect.startswith("ability: "):
                self.revealed_ability[ident] = to_id(effect[9:])
        elif tag == "-enditem":
            if len(sm) < 4:
                return
            ident = norm_ident(sm[2])
            self.original_item.setdefault(ident, to_id(sm[3]))
            self.consumed.add(ident)
        elif tag == "-item":
            if len(sm) < 4:
                return
            ident = norm_ident(sm[2])
            cause = _from_cause(sm)
            if "Trick" in cause or "Switcheroo" in cause:
                # a swapped-in item: the mon holds it now, its ORIGINAL stays
                # whatever was learned before (or unknown)
                self.consumed.discard(ident)
            elif cause.startswith("ability: Frisk"):
                # Frisk names the FOE's item under the `[of]` field's mon; the
                # `-item` target is the holder (poke-env reads it that way too)
                self.original_item.setdefault(ident, to_id(sm[3]))
            else:
                self.original_item.setdefault(ident, to_id(sm[3]))
                self.consumed.discard(ident)
        elif tag == "-heal":
            if "move: Wish" in _from_cause(sm) or "move: Healing Wish" in _from_cause(sm):
                self.wish_pending.pop(norm_ident(sm[2])[:2], None)
        elif tag == "-weather":
            weather = sm[2]
            rest = sm[3:]
            if any(f == "[upkeep]" for f in rest):
                return
            if weather == "none":
                self.weather = None
                self.weather_start = None
                self.weather_indefinite = False
                return
            self.weather = weather
            self.weather_start = self.turn
            self.weather_indefinite = any(f.startswith("[from] ability:") for f in rest)

    def _reveal_from_cause(self, sm: list[str]) -> None:
        """Any `[from] ability: X` names X as the ability of the `[of]` mon if
        one is given, else of the message's subject — Natural Cure on
        `-curestatus`, Static on `-status`, Sand Stream on `-weather`, Rough
        Skin on `-damage`, Clear Body on `-fail`, ... poke-env drops the cause
        on most of these (survey §3.2)."""
        cause = ""
        of = ""
        for field in sm[3:]:
            if field.startswith("[from] ability:"):
                cause = field[15:].strip()
            elif field.startswith("[of] "):
                of = field[5:]
        if not cause:
            return
        subject = of if of else (sm[2] if sm[1] != "-weather" else "")
        if subject.startswith("p") and ":" in subject:
            self.revealed_ability[norm_ident(subject)] = to_id(cause)

    # --- reads --------------------------------------------------------------
    def weather_elapsed(self, turn: int) -> int:
        if self.weather_start is None:
            return 0
        return max(turn - self.weather_start, 0)

    def choice_locked(self, ident: str, item: str | None) -> bool:
        return bool(item) and to_id(item) in _CHOICE and ident in self.first_move_since_switch

    def is_locked(self, ident: str) -> bool:
        return ident in self.locked_move

    def lock_elapsed(self, ident: str) -> int:
        """Turns since the rampage started (0 when not locked)."""
        entry = self.locked_move.get(ident)
        return max(self.turn - entry[1], 0) if entry else 0


_CHOICE = frozenset({"choiceband", "choicespecs", "choicescarf"})
_RAMPAGE = frozenset({"outrage", "thrash", "petaldance"})
