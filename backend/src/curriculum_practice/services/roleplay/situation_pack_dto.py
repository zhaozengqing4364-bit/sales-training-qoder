"""Compatibility alias for the neutral Situation Pack snapshot.

Owner: curriculum-practice
Retire when: Gate 6 consumer inventory for this import path is empty.
Expires on: 2026-10-31.
"""

from roleplay.situation_packs import SituationPackSnapshot

SituationPackDTO = SituationPackSnapshot

__all__ = ["SituationPackDTO"]
