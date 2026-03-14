#!/bin/bash
# Daily Conversation Archive Script (Generic Version)
# Archives yesterday's conversations from OpenClaw sessions

SESSIONS_DIR="${OPENCLAW_SESSIONS:-$HOME/.openclaw/agents/main/sessions}"
ARCHIVE_DIR="${OPENCLAW_ARCHIVE:-$HOME/.openclaw/workspace/archive/conversations}"
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)

mkdir -p "$ARCHIVE_DIR"

for jsonl in "$SESSIONS_DIR"/*.jsonl; do
    [ -f "$jsonl" ] || continue
    sid=$(basename "$jsonl" .jsonl)
    
    python3 -c "
import json, os
target_date = '$YESTERDAY'
lines = []
with open('$jsonl') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            d = json.loads(line)
            ts = d.get('timestamp', '')
            if ts[:10] == target_date:
                lines.append(line)
        except: pass

if lines:
    outpath = '$ARCHIVE_DIR/${YESTERDAY}_session_${sid}.jsonl'
    if not os.path.exists(outpath):
        with open(outpath, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        print(f'Archived: {len(lines)} messages → {outpath}')
"
done
echo "Archive complete: $YESTERDAY"
