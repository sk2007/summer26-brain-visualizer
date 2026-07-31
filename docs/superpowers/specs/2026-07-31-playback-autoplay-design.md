# Playback Auto-Play — Design (PROPOSAL)

**Status:** Proposal — plannable (no open decisions).
**Date:** 2026-07-31

## Goal

Make the "Play" button on the Patient Stats sections behave like actual playback.
Today it opens `PlaybackModal` (`frontend/src/components/MRIPlaybackModal.tsx`),
which is a **manual stepper** (arrows / scrubber / keyboard) despite the play
framing. Add a play/pause timer that advances through the items automatically.

## Background / Current State

- `PlaybackModal` renders items (MRI scans, tumor masks, or dose masks) one at a
  time via an iframe, with `activeIndex` state, a scrubber, prev/next arrows, and
  ArrowLeft/ArrowRight/Escape keyboard handling.
- To respect browser WebGL context limits, only the items within ±1 of
  `activeIndex` are mounted; a loading overlay shows until the active iframe fires
  `onLoad` (`isActiveLoaded`).
- There is currently no timer — advancing is entirely user-driven.

## Scope

**In scope (single component, `MRIPlaybackModal.tsx`):**
- A **Play/Pause toggle button** in the bottom control bar.
- An interval timer that advances `activeIndex` by one on each tick while playing.
- Sensible interaction with the existing loading model and manual controls.
- Auto-stop at the last item (no wrap by default).

**Out of scope:**
- Configurable speed UI (a single sensible default interval is enough for v1).
- Looping/repeat, shuffle.
- Any change to how iframes are windowed or loaded.

## Design

### State & timer
- Add `isPlaying: boolean` state (default `false`).
- Add a `Play`/`Pause` button (lucide `Play`/`Pause` icons) in the bottom bar,
  next to the scrubber. Hidden or disabled when there is only one item
  (`n <= 1`).
- While `isPlaying`, a `setInterval` (in a `useEffect` keyed on `isPlaying`)
  advances one step per tick. **Advance only when the current item has loaded**
  (`isActiveLoaded`) so playback doesn't skip past scans that are still rendering
  — i.e. the tick is a no-op until the active iframe has fired `onLoad`. This
  keeps playback synced to actual render readiness rather than wall-clock alone.
- Default interval: **1500 ms** between advances (a reasonable review pace; a
  named constant so it's trivially tunable).

### Stop conditions
- When `activeIndex` reaches the last item (`n - 1`), set `isPlaying = false`
  (auto-stop, no wrap).
- Any manual navigation (scrubber drag, prev/next, ArrowLeft/Right) pauses
  playback — set `isPlaying = false` so the user takes control cleanly.
- Closing the modal (`onClose`) and reopening resets `isPlaying` to `false`
  (fold into the existing open/close reset `useEffect`).

### Cleanup
- The interval must be cleared on unmount and whenever `isPlaying` flips to false
  (return a cleanup from the `useEffect`), to avoid leaked timers advancing a
  closed modal.

## Testing

- No frontend test harness exists; verify by `tsc --noEmit` and by inspection:
  play advances through items at the interval, pauses on manual nav, stops at the
  end, and no timer leaks after close (the `useEffect` cleanup handles this).

## Success Criteria

- Clicking Play auto-advances through the section's items; Pause stops it.
- Playback waits on slow-loading scans rather than skipping them.
- Manual navigation and closing the modal cleanly stop playback; no orphaned
  timers.
