#!/bin/bash
# git-commit-source.sh -- commit source file changes to a COWORK git repo
# WITHOUT touching .git on the FUSE mount.
# Updated 20-May-26: added COWORK_ROOT auto-detection
set -euo pipefail
export GIT_TERMINAL_PROMPT=0

# COWORK root auto-detection (mirrors push-dashboard.sh logic)
if [[ -n "${COWORK_ROOT:-}" && -d "$COWORK_ROOT" ]]; then
    : # use env override
elif COWORK_ROOT=$(ls -d /sessions/*/mnt/COWORK 2>/dev/null | head -1); [[ -n "$COWORK_ROOT" ]]; then
    : # sandbox auto-detect
elif [[ -d "/c/Users/richb/Documents/COWORK" ]]; then
    COWORK_ROOT="/c/Users/richb/Documents/COWORK"
elif [[ -d "C:/Users/richb/Documents/COWORK" ]]; then
    COWORK_ROOT="C:/Users/richb/Documents/COWORK"
else
    echo "ERROR: COWORK folder not found. Set COWORK_ROOT env var." >&2; exit 1
fi
echo "[git-commit-source] COWORK_ROOT resolved to: $COWORK_ROOT"

declare -A REMOTE_BASE=([master]="github.com/vfhqi/master.git" [ratings]="github.com/vfhqi/ratings.git" [landing]="github.com/vfhqi/landing.git" [pipeline]="github.com/vfhqi/master.git")
declare -A COWORK_REPO_DIR=([master]="master-dashboard" [ratings]="databases" [landing]="." [pipeline]="scripts")

REPO=""; FILES=""; MESSAGE=""; DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)     REPO="$2";    shift 2 ;;
        --files)    FILES="$2";   shift 2 ;;
        --message)  MESSAGE="$2"; shift 2 ;;
        --dry-run)  DRY_RUN=true; shift   ;;
        *) echo "ERROR: unknown arg $1" >&2; exit 1 ;;
    esac
done

[[ -z "$REPO" ]]    && { echo "ERROR: --repo required"; exit 1; }
[[ -z "$FILES" ]]   && { echo "ERROR: --files required"; exit 1; }
[[ -z "$MESSAGE" ]] && { echo "ERROR: --message required"; exit 1; }
[[ -z "${REMOTE_BASE[$REPO]:-}" ]] && { echo "ERROR: unknown repo \x27$REPO\x27"; exit 1; }

REMOTE="${REMOTE_BASE[$REPO]}"
COWORK_REPO="$COWORK_ROOT/${COWORK_REPO_DIR[$REPO]}"
SECRET_FILE="$COWORK_ROOT/.secrets/github-pat.txt"
CLONE_DIR="/tmp/git-commit-source-$$"

say() { echo "[git-commit-source] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

[[ ! -f "$SECRET_FILE" ]] && fail "PAT not found at $SECRET_FILE"
PAT=$(tr -d $'\n\r ' < "$SECRET_FILE")
[[ -z "$PAT" ]] && fail "PAT is empty"

say "Checking source files..."
for F in $FILES; do
    SRC="$COWORK_REPO/$F"
    [[ ! -f "$SRC" ]] && fail "Source file not found: $SRC"
    say "  OK: $F ($(wc -c < "$SRC") bytes)"
done

say "Cloning $REMOTE into $CLONE_DIR..."
git clone --quiet --depth 1 "https://vfhqi:${PAT}@${REMOTE}" "$CLONE_DIR"
cd "$CLONE_DIR"
git config user.email "rich.black@gmail.com"
git config user.name "Richard Black"
say "Clone OK -- HEAD: $(git rev-parse --short HEAD)"

say "Copying files and running stale-source guard..."
for F in $FILES; do
    SRC="$COWORK_REPO/$F"
    DST="$CLONE_DIR/$F"
    mkdir -p "$(dirname "$DST")"
    if [[ -f "$DST" ]]; then
        ORIGIN_BYTES=$(wc -c < "$DST")
        NEW_BYTES=$(wc -c < "$SRC")
        THRESHOLD=$(( ORIGIN_BYTES * 90 / 100 ))
        if [[ "$NEW_BYTES" -lt "$THRESHOLD" ]]; then
            fail "Stale-source guard: $F COWORK=$NEW_BYTES < 90% of origin=$ORIGIN_BYTES bytes."
        fi
        say "  Size guard PASS: $F ($NEW_BYTES vs origin $ORIGIN_BYTES)"
    fi
    cp "$SRC" "$DST"
done

git add $FILES
CHANGED=$(git diff --cached --stat | tail -1)
say "Staged: $CHANGED"
if git diff --cached --quiet; then
    say "No changes to commit -- files already match origin."; exit 0
fi
if [[ "$DRY_RUN" == "true" ]]; then
    say "DRY RUN -- would commit: $MESSAGE"; exit 0
fi

git commit -m "$MESSAGE"
say "Committed: $(git rev-parse --short HEAD)"
say "Pushing to origin/main..."
git push origin main
say "Push OK"

LOCAL_HEAD=$(git rev-parse HEAD)
REMOTE_HEAD=$(git ls-remote origin main | cut -f1)
if [[ "$LOCAL_HEAD" == "$REMOTE_HEAD" ]]; then
    say "Layer 3 SHA verify: PASS ($LOCAL_HEAD)"
else
    fail "Layer 3 SHA MISMATCH -- local=$LOCAL_HEAD remote=$REMOTE_HEAD"
fi

git remote set-url origin "https://${REMOTE}"
cd /
rm -rf "$CLONE_DIR"
say "Done. Committed and pushed $FILES to $REMOTE"
