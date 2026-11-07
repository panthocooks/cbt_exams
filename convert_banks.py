"""Convert every question-bank.md in the vault to the cleaner Obsidian layout.

Run:  python _tools/convert_banks.py   (from the vault folder, or anywhere)

- Finds Paper-*/Unit-*/question-bank.md in the vault (the folder above _tools).
- Saves the original of each file once in _tools/backups/ before touching it.
- Keeps every word of the explanations; only the layout changes.
- An entry that cannot be converted without losing a word is left exactly as it was.
- Files already converted are skipped, so it is safe to run again.
"""
import re
import shutil
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
BACKUPS = TOOLS / "backups"
MARK = "<!-- layout: v2 -->"

STATUS = {
    "confirmed": "Confirmed",
    "confirmed-with-caveat": "Confirmed, with a caveat",
    "disputed": "Disputed (my answer differs from the source key)",
    "flawed-item": "Flawed item",
}
ROMAN = {"I.", "II.", "III.", "IV.", "V."}
LABEL_RE = re.compile(r"^(Also useful|Remember|Caveat|Both views|Flaw|Note|Tip|Where each blows|How to solve these|Source check):\s*(.*)$")
DECOY_RE = re.compile(r"^(Decoy check)\b\s*(.*)$")
ANSWER_RE = re.compile(r"^(Answer used|Answer):\s*(.*)$")
WHY_RE = re.compile(r"^Why [^:\n]{0,70}:\s")
OPTS_RE = re.compile(r"^Option by option:\s*$")
OPT4_RE = re.compile(r"(?:^|\s)(1\.\s.*?\s2\.\s.*?\s3\.\s.*?\s4\.\s.*)$")
KIND = {"Also useful": "tip", "Remember": "abstract", "Caveat": "warning", "Both views": "warning",
        "Flaw": "warning", "Note": "note", "Tip": "tip", "Where each blows": "note",
        "How to solve these": "note", "Source check": "note", "Decoy check": "note"}


def words(text):
    text = text.replace("\u2019", "'")
    return Counter(w.lower() for w in re.findall(r"[A-Za-z0-9']+", text) if w.lower() != "with")


def find_marker(text, mk, start):
    pat = re.compile(r"(?:(?<=\s)|^)" + re.escape(mk) + r"\.\s")
    for m in pat.finditer(text, start):
        if start > 0:  # after the first marker, "IV. E. C. Semple" is a Roman list, not item E
            before = text[:m.start()].split()
            if before and before[-1] in ROMAN:
                continue
        return m
    return None


def split_items(text, markers):
    pos, found = 0, []
    for mk in markers:
        m = find_marker(text, mk, pos)
        if not m:
            break
        found.append((mk, m.start(), m.end()))
        pos = m.end()
    if len(found) < 2:
        return None
    prefix = text[:found[0][1]].strip()
    items = []
    for i, (mk, s, e) in enumerate(found):
        end = found[i + 1][1] if i + 1 < len(found) else len(text)
        items.append((mk, text[e:end].strip()))
    return prefix, items


def is_paren(line):
    return line.startswith("(") and line.endswith(")")


def render_stem_line(line):
    out = []
    line = re.sub(r"\s+(Reason \(R\):)", r"\n\n\1", line.strip())
    for piece in line.split("\n"):
        piece = piece.strip()
        if not piece:
            out.append("")
            continue
        m = re.match(r"^\((.+?)\)\s+(.*)$", piece)
        if m and not is_paren(piece):
            out.append("*(" + m.group(1) + ")*  ")
            piece = m.group(2)
        elif is_paren(piece):
            out.append("*" + piece + "*")
            continue
        res = split_items(piece, list("ABCDE"))
        if res:
            prefix, items = res
            roman = None
            last_mk, last_text = items[-1]
            r = split_items(last_text, ["I", "II", "III", "IV", "V"])
            if r:
                rp, roman = r
                rp = re.sub(r"\s+with$", "", rp).strip()
                items[-1] = (last_mk, rp)
            if prefix:
                out.append("**" + prefix + "**  ")
            out.extend(f"{mk}. {t}  " for mk, t in items)
            if roman:
                out.append("")
                out.extend(f"{mk}. {t}  " for mk, t in roman)
            continue
        if re.match(r"^I\.\s", piece):
            r = split_items(piece, ["I", "II", "III", "IV", "V"])
            if r:
                out.extend(f"{mk}. {t}  " for mk, t in r[1])
                continue
        am = re.match(r"^(Assertion \(A\):|Reason \(R\):)\s*(.*)$", piece)
        if am:
            out.append("**" + am.group(1) + "** " + am.group(2))
        else:
            out.append("**" + piece + "**  ")
    return out


def extract_options(qlines):
    for idx in range(len(qlines) - 1, -1, -1):
        m = OPT4_RE.search(qlines[idx])
        if m:
            parts = re.split(r"\s+(?=[1-4]\.\s)", m.group(1).strip())
            if len(parts) == 4 and all(p.startswith(f"{i + 1}. ") for i, p in enumerate(parts)):
                return idx, qlines[idx][:m.start(1)].strip(), parts
    return None


def parse_sections(body_lines):
    sections, cur, answer = [], None, None
    for raw in body_lines:
        line = raw.rstrip()
        if not line:
            if cur:
                cur["lines"].append("")
            continue
        m = ANSWER_RE.match(line)
        if m and answer is None:
            answer, cur = (m.group(1), m.group(2)), None
            continue
        if OPTS_RE.match(line):
            cur = {"kind": "opts", "title": "Option by option (click to open)", "lines": []}
            sections.append(cur)
            continue
        if WHY_RE.match(line):
            cur = {"kind": "why", "title": "", "lines": [re.sub(r"^Why it is right:\s*", "", line)]}
            sections.append(cur)
            continue
        m = LABEL_RE.match(line) or DECOY_RE.match(line)
        if m:
            rem = m.group(2).lstrip(":").strip()
            cur = {"kind": "label", "title": m.group(1), "lines": [rem] if rem else []}
            sections.append(cur)
            continue
        if cur is None:
            cur = {"kind": "misc", "title": "Note", "lines": []}
            sections.append(cur)
        cur["lines"].append(line)
    for s in sections:
        while s["lines"] and not s["lines"][-1]:
            s["lines"].pop()
    return answer, sections


def cap(lines):
    lines = list(lines)
    for i, l in enumerate(lines):
        if l.strip():
            lines[i] = re.sub(r"^([^A-Za-z0-9(]*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), l, count=1)
            break
    return lines


def callout(kind, title, lines, fold=False):
    out = [f"> [!{kind}]{'-' if fold else ''} {title}"]
    out.extend(("> " + l) if l else ">" for l in lines)
    return out


ITEM_RE = re.compile(r"^\d(?:(?:, | and )\d)*\. ")


def opt_lines(lines):
    out, prev_item = [], False
    for l in lines:
        item = bool(ITEM_RE.match(l))
        if l and not item and prev_item:
            out.append("")
        out.append(re.sub(r"^(\d)\. ([^:]{1,90}?): ", r"\1. **\2**: ", l))
        prev_item = item if l else prev_item
    return out


def convert_entry(seg):
    m = re.fullmatch(r"## (P2-[A-Za-z0-9-]+)", seg[0].strip())
    if not m:
        return None
    eid = m.group(1)
    meta, i = {}, 1
    while i < len(seg) and seg[i].startswith("- "):
        for part in seg[i][2:].split(" | "):
            if ":" in part:
                k, v = part.split(":", 1)
                meta[k.strip()] = v.strip()
        i += 1
    rest = seg[i:]
    a_idx = next((j for j, l in enumerate(rest) if ANSWER_RE.match(l)), None)
    if a_idx is None or "topic" not in meta:
        return None
    qlines = [l.strip() for l in rest[:a_idx] if l.strip()]
    opt = extract_options(qlines)
    if not opt:
        return None
    idx, stem, parts = opt
    stem_lines = qlines[:idx] + ([stem] if stem else [])
    notes = qlines[idx + 1:]
    answer, sections = parse_sections(rest[a_idx:])
    if not answer or not sections:
        return None

    q_md = []
    for l in stem_lines:
        new = render_stem_line(l)
        if new and re.match(r"^I\. ", new[0]) and q_md and q_md[-1].strip():
            q_md.append("")
        q_md.extend(new)
    q_md.append("")
    q_md.extend(parts)
    if notes:
        q_md.append("")
    for n in notes:
        q_md.append("*" + n + "*" if is_paren(n) else n)

    qn = re.search(r"Q(\d+)$", eid)
    topic = meta["topic"]
    title = topic.split(">")[-1].strip()
    title = title[:1].upper() + title[1:]
    ans_text = answer[1].strip()
    if ". " not in ans_text:
        ans_text = ans_text.rstrip(".")
    ans_text = ans_text[:1].upper() + ans_text[1:]
    num = re.search(r"option\s+(\d)", answer[1], re.I)
    ans_title = f"Answer: option {num.group(1)}" if num else "Answer"
    status = STATUS.get(meta.get("check", ""), meta.get("check", ""))

    out = [f"## {'Q' + qn.group(1) + '. ' if qn else ''}{title}", "", "| | |", "|---|---|",
           f"| Topic | {topic} |", f"| Source | {meta.get('source', '')} |"]
    if ";" in meta.get("appeared_in", ""):
        out.append(f"| Appeared in | {meta['appeared_in']} |")
    out += [f"| Answer used | {ans_text} |",
            f"| Source key / my check | {meta.get('source_key', '?')} / {meta.get('my_answer', '?')} |",
            f"| Status | {status} |", "", f"^{eid}", ""]
    out.extend(q_md)
    first_why = True
    for s in sections:
        out.append("")
        if s["kind"] == "why" and first_why:
            first_why = False
            out.extend(callout("success", ans_title, cap(s["lines"])))
        elif s["kind"] == "opts":
            out.extend(callout("info", s["title"], opt_lines(s["lines"]), fold=True))
        elif s["kind"] == "label":
            out.extend(callout(KIND.get(s["title"], "note"), s["title"], cap(s["lines"])))
        else:
            out.extend(callout("note", s["title"] or "Why", s["lines"]))

    orig = re.sub(r"Why it is right:\s*", "", "\n".join(rest))
    lost = words(orig) - words("\n".join(out))
    if lost:
        print(f"   kept as it was ({eid}): would lose {sorted(lost)}")
        return None
    return out


def convert_passage(seg):
    text, notes = [], []
    for l in seg[1:]:
        if l.startswith("In the CBT JSON"):
            notes.append(l)
        elif l.strip() or text:
            text.append(l)
    while text and not text[-1].strip():
        text.pop()
    out = [seg[0], ""] + callout("quote", "Passage", text) + [""] + ["*" + n + "*" for n in notes]
    lost = words("\n".join(seg[1:])) - words("\n".join(out))
    return None if lost else out


def convert_header(lines):
    out, note, pos = [], [], None
    for l in lines:
        if l.startswith(("How to read an entry:", "check values:", "check status values:")):
            if pos is None:
                pos = len(out)
            note.append(l)
        else:
            out.append(l)
    if note:
        out[pos:pos] = callout("note", "How to read an entry (click to open)", note, fold=True) + [""]
    for j, l in enumerate(out):
        if l.startswith("# "):
            out.insert(j + 1, MARK)
            break
    return out


def convert_text(text):
    lines = text.split("\n")
    idxs = [i for i, l in enumerate(lines) if l.startswith("## ")]
    if not idxs:
        return text, 0, 0
    out = convert_header(lines[:idxs[0]])
    done = kept = 0
    for a, b in zip(idxs, idxs[1:] + [len(lines)]):
        seg = lines[a:b]
        while seg and not seg[-1].strip():
            seg.pop()
        new = convert_passage(seg) if seg[0].startswith("## PASSAGE") else convert_entry(seg)
        if new:
            done += 1
        else:
            kept += 1
            new = seg
        out += [""] + new
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).rstrip() + "\n", done, kept


def main():
    files = sorted(ROOT.glob("Paper-*/Unit-*/question-bank.md"))
    if not files:
        print("No question-bank.md files found.")
        return
    BACKUPS.mkdir(exist_ok=True)
    for f in files:
        text = f.read_text(encoding="utf-8").replace("\r\n", "\n")
        label = f.parent.parent.name + "/" + f.parent.name
        if MARK in text:
            print(f"{label}: already converted, skipped")
            continue
        backup = BACKUPS / f"{f.parent.parent.name}__{f.parent.name}__question-bank.md"
        if not backup.exists():
            shutil.copy2(f, backup)
        new, done, kept = convert_text(text)
        f.write_text(new, encoding="utf-8")
        print(f"{label}: {done} converted, {kept} left as they were")


if __name__ == "__main__":
    main()
