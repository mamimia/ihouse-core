import sys
import re
import datetime
import os

def update_file(filepath, pattern, replacement):
    with open(filepath, 'r') as f:
        content = f.read()
    content = re.sub(pattern, replacement, content)
    with open(filepath, 'w') as f:
        f.write(content)

def append_file(filepath, text):
    with open(filepath, 'a') as f:
        f.write("\n" + text + "\n")

def main():
    if len(sys.argv) < 4:
        print("Usage: python close_phase.py <phase_number> <phase_name> <description>")
        sys.exit(1)
        
    phase_num = int(sys.argv[1])
    phase_name = sys.argv[2]
    desc = sys.argv[3]
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 1. Update work-context.md
    wc_path = "docs/core/work-context.md"
    update_file(wc_path, r"Phase (\d+) — .* ← ACTIVE", f"Phase \\1 — [CLOSED] ← CLOSED\nPhase {phase_num} — {phase_name} ← ACTIVE")
    # Actually simpler: we just regex replace
    
    # Let's just do precise sed-like replacements for current-snapshot and work-context
    # Since regex can be tricky, let's read lines and manipulate.
    with open(wc_path, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "## Current Active Phase" in line:
            lines[i+2] = f"Phase {phase_num} — {phase_name}. Phases 841–{phase_num-1} closed.\n"
        if "## Last Closed Phase" in line:
            prev_phase = phase_num - 1
            lines[i+2] = f"Phase {prev_phase} closed successfully.\n"
        
        # update the sequence
        if f"Phase {phase_num} — {phase_name}" in line and "← NEXT" in line:
            lines[i] = line.replace("← NEXT", "← ACTIVE")
        if f"Phase {phase_num-1}" in line and "← ACTIVE" in line:
            lines[i] = line.replace("← ACTIVE", "← CLOSED")
            
    with open(wc_path, 'w') as f:
        f.writelines(lines)
        
    # 2. current-snapshot.md
    snap_path = "docs/core/current-snapshot.md"
    with open(snap_path, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "**Current Phase:**" in line:
            lines[i] = f"- **Current Phase:** {phase_num}\n"
        if "**Last Closed Phase:**" in line:
            lines[i] = f"- **Last Closed Phase:** {phase_num-1}\n"
            
    with open(snap_path, 'w') as f:
        f.writelines(lines)

    # 3. phase-timeline.md
    tl_path = "docs/core/phase-timeline.md"
    append_file(tl_path, f"## Phase {phase_num}: {phase_name}\n**Date:** {date_str}\n\n**Goal:** {desc}\n")

    # 4. construction-log.md
    cl_path = "docs/core/construction-log.md"
    append_file(cl_path, f"### Phase {phase_num} ({date_str})\n- Implemented {phase_name}.\n- {desc}\n")

    # 5. phase spec
    spec_dir = "docs/archive/phases"
    os.makedirs(spec_dir, exist_ok=True)
    with open(f"{spec_dir}/phase-{phase_num}-spec.md", 'w') as f:
        f.write(f"# Phase {phase_num} Specification: {phase_name}\n\n## Overview\n{desc}\n\n## Implementation Details\nCompleted.\n")
        
    print(f"Phase {phase_num} closed successfully.")

if __name__ == "__main__":
    main()
