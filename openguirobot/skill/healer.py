"""
L1 Skill — Healer: 4-layer recovery strategy for failed test steps.

Layer 1 — Popup dismissal  : tries 5 strategies to close overlay dialogs
Layer 2 — Screenshot similarity : checks if the screen changed (phash)
Layer 3 — Context memory   : tracks consecutive failures; recommends rollback / marks unstable
Layer 4 — Fallback         : placeholder for v0.4 AI-assisted recovery

Usage::

    healer = DefaultHealer(driver)
    result = healer.heal(ctx)
    if result["healed"]:
        # retry the failed step
    else:
        # give up or escalate
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from openguirobot.driver.base import Driver, DomTree


# ── Public types ───────────────────────────────────────────────────────────────

class HealResult(TypedDict):
    """Returned by Healer.heal()."""
    healed:        bool
    layer:         Literal["popup", "similarity", "context", "fallback"] | None
    actions_taken: list[str]
    duration_ms:   int


class StepContext(TypedDict, total=False):
    """All information available to the healer about a failed step."""
    driver:             "Driver"
    step_index:         int
    screenshot_before:  bytes          # PNG taken before the step ran
    screenshot_after:   bytes          # PNG taken right after failure
    dom_before:         "DomTree | None"
    dom_after:          "DomTree | None"
    error_msg:          str
    case_id:            str


# ── Protocol ───────────────────────────────────────────────────────────────────

@runtime_checkable
class Healer(Protocol):
    """Interface that all healer implementations must satisfy."""

    def heal(self, ctx: StepContext) -> HealResult:
        """Attempt to recover from a failed step. Returns HealResult."""
        ...


# ── Context memory (tracks per-case per-step history) ─────────────────────────

class _StepRecord:
    """Tracks attempt history for a single step within a case."""

    def __init__(self) -> None:
        self.total_attempts:  int = 0
        self.success_count:   int = 0
        self.consecutive_failures: int = 0

    def record_failure(self) -> None:
        self.total_attempts += 1
        self.consecutive_failures += 1

    def record_success(self) -> None:
        self.total_attempts += 1
        self.success_count += 1
        self.consecutive_failures = 0

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 1.0
        return self.success_count / self.total_attempts

    @property
    def should_rollback(self) -> bool:
        """Two consecutive failures → suggest rollback."""
        return self.consecutive_failures >= 2

    @property
    def is_unstable(self) -> bool:
        """More than 2 total attempts and success rate <50% → mark unstable."""
        return self.total_attempts > 2 and self.success_rate < 0.5


class ContextMemory:
    """
    In-memory store of per-case, per-step attempt history.

    Not persisted across process restarts (persistence is a v0.3 feature via the graph DB).
    """

    def __init__(self) -> None:
        # key: (case_id, step_index)
        self._records: dict[tuple[str, int], _StepRecord] = {}

    def _get(self, case_id: str, step_index: int) -> _StepRecord:
        key = (case_id, step_index)
        if key not in self._records:
            self._records[key] = _StepRecord()
        return self._records[key]

    def record_failure(self, case_id: str, step_index: int) -> None:
        self._get(case_id, step_index).record_failure()

    def record_success(self, case_id: str, step_index: int) -> None:
        self._get(case_id, step_index).record_success()

    def should_rollback(self, case_id: str, step_index: int) -> bool:
        return self._get(case_id, step_index).should_rollback

    def is_unstable(self, case_id: str, step_index: int) -> bool:
        return self._get(case_id, step_index).is_unstable


# ── Layer 1: Popup dismissal ───────────────────────────────────────────────────

_POPUP_TEXT_CANDIDATES = [
    # Chinese
    "关闭", "取消", "好的", "确定", "知道了", "我知道了",
    # English
    "Close", "Cancel", "Dismiss", "OK", "Got it", "No thanks",
]


def _try_popup_dismiss(driver: "Driver") -> list[str]:
    """
    Try up to 5 strategies to dismiss an overlay popup.

    Returns a list of actions that were taken (may be empty if nothing matched).
    Strategy order:
      1. Close/Cancel text button in DOM
      2. Top-right X button (heuristic position)
      3. Tap outside the dialog (top-left corner)
      4. Press system Back key
      5. Swipe down from centre (sheet dismissal)
    """
    from openguirobot.driver.base import KeyCode

    actions: list[str] = []

    # Strategy 1: DOM text match
    try:
        dom = driver.dump_dom()
        for candidate in _POPUP_TEXT_CANDIDATES:
            nodes = dom.find_by_text(candidate, exact=True)
            if nodes:
                cx, cy = nodes[0].center
                driver.tap(cx, cy)
                actions.append(f"popup_text_tap:{candidate!r}")
                return actions   # stop after first successful text match
    except Exception:  # noqa: BLE001
        pass

    # Strategy 2: top-right X button (heuristic: right 10%, top 10% of screen)
    try:
        w, h = driver.get_window_size()
        x_btn_x = int(w * 0.92)
        x_btn_y = int(h * 0.08)
        driver.tap(x_btn_x, x_btn_y)
        actions.append("popup_x_button_heuristic")
    except Exception:  # noqa: BLE001
        pass

    # Strategy 3: tap outside (top-left corner, likely outside any dialog)
    try:
        w, h = driver.get_window_size()
        driver.tap(int(w * 0.05), int(h * 0.05))
        actions.append("popup_tap_outside")
    except Exception:  # noqa: BLE001
        pass

    # Strategy 4: system Back key
    try:
        driver.press_key(KeyCode.BACK)
        actions.append("popup_back_key")
    except Exception:  # noqa: BLE001
        pass

    # Strategy 5: swipe down (sheet / bottom drawer dismissal)
    try:
        w, h = driver.get_window_size()
        cx = w // 2
        driver.swipe(cx, int(h * 0.4), cx, int(h * 0.9), duration_ms=400)
        actions.append("popup_swipe_down")
    except Exception:  # noqa: BLE001
        pass

    return actions


# ── Layer 2: Screenshot similarity ────────────────────────────────────────────

_SIMILARITY_THRESHOLD = 0.75   # >75% change = healed


def _screen_changed(before: bytes, after: bytes) -> bool:
    """Return True if the screen changed significantly (phash similarity < threshold)."""
    from openguirobot.skill.image_diff import phash_similarity
    result = phash_similarity(before, after, threshold=_SIMILARITY_THRESHOLD)
    return result.changed   # changed=True means similarity < threshold


# ── Default healer implementation ──────────────────────────────────────────────

class DefaultHealer:
    """
    4-layer healer that implements the Healer protocol.

    Args:
        driver:          Active Driver instance.
        decisions_dir:   Directory where decisions.jsonl is written.
                         Defaults to ``evidence/<case_id>/healing/``.
        memory:          Optional shared ContextMemory; created if not supplied.
    """

    def __init__(
        self,
        driver: "Driver",
        decisions_dir: Path | str | None = None,
        memory: ContextMemory | None = None,
    ) -> None:
        self._driver        = driver
        self._decisions_dir = Path(decisions_dir) if decisions_dir else None
        self._memory        = memory or ContextMemory()

    # ── Public entry point ─────────────────────────────────────────────────────

    def heal(self, ctx: StepContext) -> HealResult:
        """
        Run the 4-layer recovery pipeline.

        Layers are tried in order; the first layer that succeeds stops the chain.
        """
        t0             = time.monotonic()
        actions_taken: list[str] = []
        case_id    = ctx.get("case_id", "unknown")
        step_index = ctx.get("step_index", 0)

        # Record the failure in context memory
        self._memory.record_failure(case_id, step_index)

        result = self._run_layers(ctx, actions_taken, case_id, step_index)

        duration_ms = int((time.monotonic() - t0) * 1000)
        final: HealResult = {
            **result,                              # type: ignore[misc]
            "duration_ms": duration_ms,
        }

        self._write_decision(ctx, final)
        return final

    # ── Layer pipeline ─────────────────────────────────────────────────────────

    def _run_layers(
        self,
        ctx: StepContext,
        actions_taken: list[str],
        case_id: str,
        step_index: int,
    ) -> HealResult:
        # ── Layer 1: Popup dismissal ──────────────────────────────────────────
        before_shot = ctx.get("screenshot_after") or ctx.get("screenshot_before") or b""
        popup_actions = _try_popup_dismiss(self._driver)
        actions_taken.extend(popup_actions)

        if popup_actions:
            # Check if screen changed after dismissal attempts
            try:
                after_shot = self._driver.screenshot()
                if _screen_changed(before_shot, after_shot) and before_shot:
                    self._memory.record_success(case_id, step_index)
                    return HealResult(
                        healed=True,
                        layer="popup",
                        actions_taken=actions_taken,
                        duration_ms=0,
                    )
            except Exception:  # noqa: BLE001
                pass

        # ── Layer 2: Screenshot similarity ────────────────────────────────────
        before = ctx.get("screenshot_before") or b""
        after  = ctx.get("screenshot_after")  or b""
        if before and after:
            try:
                if _screen_changed(before, after):
                    # The screen already changed, which may indicate partial success
                    actions_taken.append("similarity_change_detected")
                    self._memory.record_success(case_id, step_index)
                    return HealResult(
                        healed=True,
                        layer="similarity",
                        actions_taken=actions_taken,
                        duration_ms=0,
                    )
            except ImportError:
                # imagehash not installed — skip this layer
                actions_taken.append("similarity_skipped:imagehash_not_installed")

        # ── Layer 3: Context memory ────────────────────────────────────────────
        if self._memory.should_rollback(case_id, step_index):
            actions_taken.append("context_memory:recommend_rollback")
            return HealResult(
                healed=False,
                layer="context",
                actions_taken=actions_taken,
                duration_ms=0,
            )
        if self._memory.is_unstable(case_id, step_index):
            actions_taken.append("context_memory:marked_unstable")
            return HealResult(
                healed=False,
                layer="context",
                actions_taken=actions_taken,
                duration_ms=0,
            )

        # ── Layer 4: Fallback (placeholder, v0.4) ─────────────────────────────
        actions_taken.append("fallback:not_implemented_v0.4")
        return HealResult(
            healed=False,
            layer="fallback",
            actions_taken=actions_taken,
            duration_ms=0,
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def _write_decision(self, ctx: StepContext, result: HealResult) -> None:
        """Append a JSON record to decisions.jsonl in the evidence directory."""
        if self._decisions_dir is None:
            return
        try:
            self._decisions_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "case_id":    ctx.get("case_id", "unknown"),
                "step_index": ctx.get("step_index", 0),
                "error_msg":  ctx.get("error_msg", ""),
                "healed":     result["healed"],
                "layer":      result["layer"],
                "actions":    result["actions_taken"],
                "duration_ms": result["duration_ms"],
            }
            path = self._decisions_dir / "decisions.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            pass   # Never let evidence writing crash the main flow
