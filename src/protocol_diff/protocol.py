"""A deterministic Mealy machine and the protocol implementations under study.

The protocol is a session-oriented request/response protocol with six
observable states.  Bugs are implemented as *additional latent states*
or altered transitions, never as output overrides keyed on the input
alone: a defect that depends on history must be discovered by a learner
that can represent history, otherwise the experiment would prove
nothing about state-machine inference.

Six states are the minimum for the reference implementation:

    NEW --HELO--> ANON --AUTH_GOOD--> AUTHED --ADMIN--> PENDING --AUTH_GOOD--> ADMIN
                   ^                    |                  |
                   +------ RESET -------+------------------+

CLOSED is absorbing and reachable from every live state via BYE.
"""

from __future__ import annotations

from dataclasses import dataclass

INPUTS: tuple[str, ...] = (
    "HELO",
    "AUTH_GOOD",
    "AUTH_BAD",
    "GET_PUB",
    "GET_PRIV",
    "PUT",
    "ADMIN",
    "RESET",
    "BYE",
    "PING",
)

OUTPUTS: tuple[str, ...] = (
    "220_READY",
    "331_CHALLENGE",
    "230_OK",
    "530_DENY",
    "200_PUB",
    "150_DATA",
    "250_STORED",
    "221_BYE",
    "421_CLOSED",
)

# Short aliases keep the transition tables readable.
R = "220_READY"
C = "331_CHALLENGE"
OK = "230_OK"
D = "530_DENY"
PUB = "200_PUB"
DATA = "150_DATA"
ST = "250_STORED"
BYE = "221_BYE"
CL = "421_CLOSED"

NEW, ANON, AUTHED, PENDING, ADMIN, CLOSED = (
    "NEW",
    "ANON",
    "AUTHED",
    "PENDING",
    "ADMIN",
    "CLOSED",
)


class Mealy:
    """Deterministic Mealy machine: output and next state on every input."""

    def __init__(
        self,
        name: str,
        states: tuple[str, ...],
        init: str,
        delta: dict[tuple[str, str], tuple[str, str]],
        alphabet: tuple[str, ...] = INPUTS,
    ) -> None:
        self.name = name
        self.states = states
        self.init = init
        self.alphabet = alphabet
        self.delta = delta
        missing = [
            (s, a) for s in states for a in alphabet if (s, a) not in delta
        ]
        if missing:
            raise ValueError(f"{name}: incomplete transition table, missing {missing[:4]}")

    def step(self, state: str, symbol: str) -> tuple[str, str]:
        return self.delta[(state, symbol)]

    def run(self, sequence: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
        state = self.init
        out: list[str] = []
        for symbol in sequence:
            output, state = self.delta[(state, symbol)]
            out.append(output)
        return tuple(out), state

    def state_count(self) -> int:
        return len(self.states)


def _table(states: tuple[str, ...], overrides: dict[tuple[str, str], tuple[str, str]] | None = None) -> dict:
    """Reference transition table, with per-variant overrides applied."""
    table: dict[tuple[str, str], tuple[str, str]] = {}
    for state in states:
        for symbol in INPUTS:
            table[(state, symbol)] = (D, state)

    def set_all(state: str, mapping: dict[str, tuple[str, str]]) -> None:
        for symbol, target in mapping.items():
            table[(state, symbol)] = target

    set_all(
        NEW,
        {
            "HELO": (R, ANON),
            "PING": (D, NEW),
            "BYE": (BYE, CLOSED),
        },
    )
    set_all(
        ANON,
        {
            "HELO": (R, ANON),
            "AUTH_GOOD": (OK, AUTHED),
            "AUTH_BAD": (D, ANON),
            "GET_PUB": (PUB, ANON),
            "GET_PRIV": (D, ANON),
            "PUT": (D, ANON),
            "ADMIN": (D, ANON),
            "RESET": (R, ANON),
            "BYE": (BYE, CLOSED),
            "PING": (PUB, ANON),
        },
    )
    set_all(
        AUTHED,
        {
            "HELO": (R, AUTHED),
            "AUTH_GOOD": (OK, AUTHED),
            "AUTH_BAD": (D, ANON),
            "GET_PUB": (PUB, AUTHED),
            "GET_PRIV": (DATA, AUTHED),
            "PUT": (ST, AUTHED),
            "ADMIN": (C, PENDING),
            "RESET": (R, ANON),
            "BYE": (BYE, CLOSED),
            "PING": (PUB, AUTHED),
        },
    )
    set_all(
        PENDING,
        {
            "AUTH_GOOD": (OK, ADMIN),
            "AUTH_BAD": (D, AUTHED),
            "RESET": (R, ANON),
            "BYE": (BYE, CLOSED),
        },
    )
    set_all(
        ADMIN,
        {
            "HELO": (R, ADMIN),
            "AUTH_GOOD": (OK, ADMIN),
            "AUTH_BAD": (D, ANON),
            "GET_PUB": (PUB, ADMIN),
            "GET_PRIV": (DATA, ADMIN),
            "PUT": (ST, ADMIN),
            "ADMIN": (OK, ADMIN),
            "RESET": (R, ANON),
            "BYE": (BYE, CLOSED),
            "PING": (PUB, ADMIN),
        },
    )
    set_all(CLOSED, {symbol: (CL, CLOSED) for symbol in INPUTS})

    if overrides:
        for key, value in overrides.items():
            table[key] = value
    return table


def reference() -> Mealy:
    states = (NEW, ANON, AUTHED, PENDING, ADMIN, CLOSED)
    return Mealy("reference", states, NEW, _table(states))


# --------------------------------------------------------------------------
# Defective variants
# --------------------------------------------------------------------------

def clearance_persist() -> Mealy:
    """RESET drops the session but not the privilege bit.

    A second ANON state carries the stale privilege flag, so the defect is
    only observable after an authenticated session is reset.  A learner
    that collapses both ANON states cannot express the bug.
    """
    states = (NEW, ANON, "ANON_TAINTED", AUTHED, PENDING, ADMIN, CLOSED)
    overrides = {
        (AUTHED, "RESET"): (R, "ANON_TAINTED"),
        (ADMIN, "RESET"): (R, "ANON_TAINTED"),
        ("ANON_TAINTED", "GET_PRIV"): (DATA, "ANON_TAINTED"),
        ("ANON_TAINTED", "RESET"): (R, "ANON_TAINTED"),
    }
    table = _table(states, overrides)
    for symbol in INPUTS:
        if (("ANON_TAINTED", symbol)) not in overrides:
            table[("ANON_TAINTED", symbol)] = table[(ANON, symbol)]
    return Mealy("clearance_persist", states, NEW, table)


def admin_persist() -> Mealy:
    """RESET returns to ANON but the admin role survives."""
    states = (NEW, ANON, "ANON_ADMIN", AUTHED, PENDING, ADMIN, CLOSED)
    overrides = {
        (ADMIN, "RESET"): (R, "ANON_ADMIN"),
        ("ANON_ADMIN", "ADMIN"): (OK, "ANON_ADMIN"),
        ("ANON_ADMIN", "RESET"): (R, "ANON_ADMIN"),
    }
    table = _table(states, overrides)
    for symbol in INPUTS:
        if ("ANON_ADMIN", symbol) not in overrides:
            table[("ANON_ADMIN", symbol)] = table[(ANON, symbol)]
    return Mealy("admin_persist", states, NEW, table)


def auth_inverted() -> Mealy:
    """A failed authentication is treated as success."""
    states = (NEW, ANON, AUTHED, PENDING, ADMIN, CLOSED)
    overrides = {(ANON, "AUTH_BAD"): (OK, AUTHED)}
    return Mealy("auth_inverted", states, NEW, _table(states, overrides))


def close_ignored() -> Mealy:
    """BYE replies 221 but the session is not torn down."""
    states = (NEW, ANON, AUTHED, PENDING, ADMIN, CLOSED)
    overrides = {
        (ANON, "BYE"): (BYE, ANON),
        (AUTHED, "BYE"): (BYE, AUTHED),
        (ADMIN, "BYE"): (BYE, ADMIN),
    }
    return Mealy("close_ignored", states, NEW, _table(states, overrides))


def pub_leak_closed() -> Mealy:
    """A closed session still serves public data."""
    states = (NEW, ANON, AUTHED, PENDING, ADMIN, CLOSED)
    overrides = {(CLOSED, "GET_PUB"): (PUB, CLOSED)}
    return Mealy("pub_leak_closed", states, NEW, _table(states, overrides))


VARIANTS = {
    "reference": reference,
    "clearance_persist": clearance_persist,
    "admin_persist": admin_persist,
    "auth_inverted": auth_inverted,
    "close_ignored": close_ignored,
    "pub_leak_closed": pub_leak_closed,
}


# --------------------------------------------------------------------------
# System under test: a black box with a query counter
# --------------------------------------------------------------------------

@dataclass
class SUT:
    """The only interface the learner is allowed to use.

    A real deployment would speak TCP to a daemon.  The in-process object
    keeps the experiment deterministic and fast while preserving the black
    box contract: reset() then zero or more step() calls.
    """

    machine: Mealy
    queries: int = 0
    steps: int = 0

    def reset(self) -> None:
        self._state = self.machine.init

    def step(self, symbol: str) -> str:
        if symbol not in self.machine.alphabet:
            raise ValueError(f"symbol outside alphabet: {symbol}")
        self.steps += 1
        output, self._state = self.machine.delta[(self._state, symbol)]
        return output

    def query(self, sequence: tuple[str, ...]) -> tuple[str, ...]:
        self.queries += 1
        self.reset()
        return tuple(self.step(symbol) for symbol in sequence)
