from __future__ import annotations


def assign_role(index: int, total: int) -> str:
    if total <= 1:
        return "setup"
    if index == 0:
        return "setup"
    if index == total - 1:
        return "resolution"
    return "development"


def ensure_role_coverage(roles: list[str]) -> list[str]:
    required = {"setup", "development", "resolution"}
    present = set(roles)
    return sorted(required - present)
