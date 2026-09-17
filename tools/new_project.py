#!/usr/bin/env python3
"""new_project.py <slug> "one-line intent"  → creates projects/<slug>/ from _template with brief.md stub."""
import sys, os, shutil, time
ROOT=os.environ.get('STUDIO_PROJECTS', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'projects')); TPL=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'projects','_template'); slug=sys.argv[1]; intent=' '.join(sys.argv[2:])
dst=os.path.join(ROOT,slug); shutil.copytree(TPL,dst,dirs_exist_ok=True)
open(os.path.join(dst,'brief.md'),'w').write(f"# {slug} — brief\n\nCreated {time.strftime('%Y-%m-%d')}\n\n## Intent\n{intent}\n\n## Locks (fill at intake)\n- duration:\n- ratio:\n- platform:\n- audio approach:\n- deliverable language:\n- must-show / excluded:\n\n## Verified facts\n\n## Style Master\n")
print(dst)
