"""Fix missing critical/high variables in _build_summary"""
import pathlib, re

f   = pathlib.Path(__file__).parent / "spike_detector.py"
txt = f.read_text(encoding="utf-8")

old = (
    "        clips    = type_counts[\"Clipping Artifact\"]\r\n"
    "        cinematic = type_counts[\"Cinematic Effect\"]\r\n"
    "        errors    = type_counts[\"Editing Error\"]\r\n"
)
new = (
    "        clips     = type_counts[\"Clipping Artifact\"]\r\n"
    "        cinematic = type_counts[\"Cinematic Effect\"]\r\n"
    "        errors    = type_counts[\"Editing Error\"]\r\n"
    "        critical  = sev_counts[\"Critical\"]\r\n"
    "        high      = sev_counts[\"High\"]\r\n"
)

if old in txt:
    txt2 = txt.replace(old, new, 1)
    f.write_text(txt2, encoding="utf-8")
    print("OK: added critical/high variable assignments")
else:
    # try LF only
    old_lf = old.replace("\r\n", "\n")
    new_lf = new.replace("\r\n", "\n")
    if old_lf in txt:
        txt2 = txt.replace(old_lf, new_lf, 1)
        f.write_text(txt2, encoding="utf-8")
        print("OK (LF): added critical/high variable assignments")
    else:
        print("ERROR: could not find target text. Lines around 295:")
        for i, line in enumerate(txt.splitlines(), 1):
            if 290 <= i <= 302:
                print(f"  {i}: {repr(line)}")
