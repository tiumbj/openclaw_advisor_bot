"""MAIN agent manager runtime package.

MAIN (super-advisor) is the sole user-facing entry point.
This package contains the runtime modules that implement MAIN's 14 operational components.
All specialist agents are dispatched through MAIN — never called directly by the user.

Blueprint §3: MAIN Agent Manager Architecture
"""
from __future__ import annotations

from .planner import MainPlanner
from .router import AgentRouter

__all__ = ["MainPlanner", "AgentRouter"]
