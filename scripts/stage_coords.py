"""Convert between Figma page coordinates and scatter-stage percentages."""
from __future__ import annotations

import common

PAGE_W_PT = 792.0
PAGE_H_PT = 612.0
STAGE_INSET_IN = {"top": 0.45, "right": 0.5, "bottom": 0.45, "left": 0.5}


def _inset_pt() -> tuple[float, float, float, float]:
    w, h = common.PAGE_W_IN, common.PAGE_H_IN
    left = STAGE_INSET_IN["left"] / w * PAGE_W_PT
    top = STAGE_INSET_IN["top"] / h * PAGE_H_PT
    right = STAGE_INSET_IN["right"] / w * PAGE_W_PT
    bottom = STAGE_INSET_IN["bottom"] / h * PAGE_H_PT
    return left, top, right, bottom


def figma_pt_to_stage_pct(x_pt: float, y_pt: float) -> tuple[float, float]:
    """Top-left of a node in Figma → scatter-stage left/top %."""
    left, top, right, bottom = _inset_pt()
    stage_w = PAGE_W_PT - left - right
    stage_h = PAGE_H_PT - top - bottom
    left_pct = (x_pt - left) / stage_w * 100.0
    top_pct = (y_pt - top) / stage_h * 100.0
    return round(left_pct, 1), round(top_pct, 1)


def stage_pct_to_figma_pt(left_pct: float, top_pct: float) -> tuple[float, float]:
    """Scatter-stage left/top % → Figma top-left in pt."""
    left, top, right, bottom = _inset_pt()
    stage_w = PAGE_W_PT - left - right
    stage_h = PAGE_H_PT - top - bottom
    x_pt = left + (left_pct / 100.0) * stage_w
    y_pt = top + (top_pct / 100.0) * stage_h
    return x_pt, y_pt
