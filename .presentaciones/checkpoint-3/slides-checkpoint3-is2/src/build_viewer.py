#!/usr/bin/env python3
"""Regenera index.html: visor de todas las carpetas 'slide N from pdf'."""
import json, re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
folders = sorted((p for p in root.glob("slide * from pdf") if p.is_dir()),
                 key=lambda p: int(re.search(r"slide (\d+)", p.name).group(1)))
slides = [f"{d.name}/{f.name}" for d in folders
          for f in sorted(d.glob("slide_*.html"), key=lambda f: int(re.match(r"slide_(\d+)", f.name).group(1)))]
tpl = (root / "viewer.template.html").read_text(encoding="utf8")
(root / "index.html").write_text(tpl.replace("__SLIDES__", json.dumps(slides, ensure_ascii=False)), encoding="utf8")
print(f"{len(slides)} slides")
