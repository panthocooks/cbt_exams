"""Merge new question entries from _Inbox into the unit question banks.

Each file in _Inbox starts with a line like:   target: Paper-2/Unit-01-Geomorphology
followed by entries in the compact layout (and any comprehension passage placed
directly above its questions). The script converts them to the cleaner layout
(keeping every word), appends them to that unit's question-bank.md, and moves the
inbox file to _Inbox/done/. An entry whose ID is already in the bank is skipped,
so running it twice is safe.

Run:  python _tools/merge_inbox.py
"""
import re
import shutil
from pathlib import Path

from convert_banks import ROOT, convert_entry, convert_passage

INBOX = ROOT / "_Inbox"


def main():
    files = sorted(INBOX.glob("*.md")) if INBOX.exists() else []
    if not files:
        print("Nothing in _Inbox.")
        return
    done_dir = INBOX / "done"
    done_dir.mkdir(exist_ok=True)
    for f in files:
        lines = f.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
        target = None
        if lines and lines[0].startswith("target:"):
            target = lines[0].split(":", 1)[1].strip()
            lines = lines[1:]
        bank = (ROOT / target / "question-bank.md") if target else None
        if not bank or not bank.exists():
            print(f"{f.name}: target not found ({target}), left in _Inbox")
            continue
        existing = bank.read_text(encoding="utf-8").replace("\r\n", "\n")
        idxs = [i for i, l in enumerate(lines) if l.startswith("## ")]
        out, added, skipped, raw = [], 0, 0, 0
        for a, b in zip(idxs, idxs[1:] + [len(lines)]):
            seg = lines[a:b]
            while seg and not seg[-1].strip():
                seg.pop()
            em = re.fullmatch(r"## (P2-[A-Za-z0-9-]+)", seg[0].strip())
            pm = re.match(r"## PASSAGE (\S+)", seg[0])
            key = em.group(1) if em else (pm.group(1) if pm else None)
            if key and (f"^{key}" in existing or (pm and seg[0].strip() in existing)):
                skipped += 1
                continue
            new = convert_passage(seg) if pm else convert_entry(seg)
            if not new:
                new, raw = seg, raw + 1
            out += [""] + new
            added += 1
        if out:
            bank.write_text(existing.rstrip("\n") + "\n" + "\n".join(out).rstrip() + "\n", encoding="utf-8")
        shutil.move(str(f), str(done_dir / f.name))
        print(f"{f.name} -> {target}: {added} added ({raw} kept in the old layout), {skipped} already there")


if __name__ == "__main__":
    main()
