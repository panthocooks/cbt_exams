import pathlib
import fitz  # PyMuPDF

out = pathlib.Path("..") / ".." / "_Extracted-Text" / "Paper-2"
out.mkdir(parents=True, exist_ok=True)

for pdf in sorted(pathlib.Path(".").glob("*.pdf")):
    doc = fitz.open(pdf)
    pages = [page.get_text() for page in doc]
    body = "\n\n".join(f"=== page {i + 1} ===\n{t}" for i, t in enumerate(pages))
    (out / f"{pdf.stem}.txt").write_text(body, encoding="utf-8")
    chars = sum(len(t) for t in pages)
    flag = "  <-- probably scanned, needs OCR" if chars / max(len(pages), 1) < 300 else ""
    print(f"{pdf.name}: {len(pages)} pages, {chars} chars{flag}")
