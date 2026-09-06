#!/usr/bin/env bash
# ============================================================================
# auto-sync.sh — watches the working tree and automatically commits + pushes
# to the GitHub remote once files change and then stay unchanged for
# SETTLE_SECS (debounce, so half-written states are never committed).
#
# Usage:
#   bash auto-sync.sh            start the watcher (run in foreground)
#   bash auto-sync.sh &          start it in the background of this terminal
#   bash auto-sync.sh stop       stop a running watcher
#   bash auto-sync.sh once       run a single settle -> commit -> push cycle
#   bash auto-sync.sh status     show running state + recent log
#
# Tuning via environment variables:
#   POLL_SECS=2 SETTLE_SECS=30 bash auto-sync.sh
#
# Activity is appended to ./.auto-sync.log (git-ignored).
# ============================================================================
set -u

cd "$(dirname "$0")" || exit 1

LOG=".auto-sync.log"
PID=".auto-sync.pid"
POLL="${POLL_SECS:-2}"
SETTLE="${SETTLE_SECS:-30}"
BRANCH="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo main)"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

dirty() { [ -n "$(git status --porcelain 2>/dev/null)" ]; }

is_running() { [ -f "$PID" ] && kill -0 "$(cat "$PID" 2>/dev/null)" 2>/dev/null; }

commit_and_push() {
  git add -A 2>/dev/null
  if git diff --cached --quiet 2>/dev/null; then
    log "nothing new to commit - skipping"
    return 1
  fi
  local msg files
  msg="Auto-sync $(date '+%Y-%m-%d %H:%M')"
  files="$(git diff --cached --name-only 2>/dev/null | sed 's/^/  - /' | head -25)"
  if ! git commit -q -m "$msg" -m "$files"; then
    log "COMMIT FAILED"
    return 1
  fi
  log "committed ($(git show -s --format=%h HEAD)): $msg"
  if git push origin "$BRANCH" >> "$LOG" 2>&1; then
    log "pushed to origin/$BRANCH"
    return 0
  fi
  log "PUSH FAILED (see log tail above) - will retry on the next change"
  return 1
}

settle_and_sync() {
  local quiet=0 prev=""
  while true; do
    local snap
    snap="$(git status --porcelain 2>/dev/null)"
    if [ -z "$snap" ]; then
      log "tree went clean by itself (external commit?) - nothing to push"
      return 1
    fi
    if [ "$snap" = "$prev" ]; then
      quiet=$((quiet + POLL))
      if [ "$quiet" -ge "$SETTLE" ]; then
        commit_and_push
        return $?
      fi
    else
      quiet=0
    fi
    prev="$snap"
    sleep "$POLL"
  done
}

start() {
  if is_running; then
    log "already running (pid $(cat "$PID"))"
    return 0
  fi
  echo "$$" > "$PID"
  log "auto-sync started - branch=$BRANCH poll=${POLL}s settle=${SETTLE}s"
  while true; do
    if dirty; then settle_and_sync; fi
    sleep "$POLL"
  done
}

stop() {
  if is_running; then
    kill "$(cat "$PID")" 2>/dev/null
    rm -f "$PID"
    log "auto-sync stopped"
    echo "stopped"
  else
    echo "not running (no live pid in $PID)"
  fi
}

status() {
  if is_running; then echo "RUNNING - pid $(cat "$PID")"; else echo "stopped"; fi
  if [ -f "$LOG" ]; then echo "--- recent log ---"; tail -8 "$LOG"; fi
}

trap 'rm -f "$PID"' EXIT

case "${1:-start}" in
  start)  start ;;
  stop)   stop ;;
  once)   if dirty; then settle_and_sync; else log "tree is clean - nothing to do"; fi ;;
  status) status ;;
  *) echo "unknown command: $1" >&2; echo "usage: bash auto-sync.sh [start|stop|once|status]" >&2; exit 2 ;;
esac
