"""voffice — Virtual Office: one prompt → a runnable git project.

A multi-agent framework on top of AgentScope that builds a virtual software
team (Manager + PM + Backend + Frontend + QA), gives them tools to actually
write files, runs an iterative pytest verification loop, and packages the
result as a git repository ready to push.

Public API:
    >>> from voffice import build_office, run_turn, ship_workspace
    >>> office = build_office(Path("./workspace"))
    >>> async for event in run_turn(office, "Build a todo API"):
    ...     print(event.speaker, event.text_chunk)
    >>> report = ship_workspace(office, "todo-api")
"""

from voffice.model import DEFAULT_MODEL, make_model
from voffice.engine import (
    MAX_VERIFY_ITERS,
    Office,
    ROLES,
    RoleSpec,
    ShipReport,
    TurnEvent,
    build_office,
    run_turn,
    ship_workspace,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_MODEL",
    "MAX_VERIFY_ITERS",
    "Office",
    "ROLES",
    "RoleSpec",
    "ShipReport",
    "TurnEvent",
    "build_office",
    "make_model",
    "run_turn",
    "ship_workspace",
]
