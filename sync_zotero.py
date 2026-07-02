#!/usr/bin/env python3
"""Sync the CV's publication bibliography from the local Zotero database.

Reads ~/Zotero/zotero.sqlite (via a temp copy, so it works while Zotero is
open) and writes Bibliography/cv_publications.bib containing:

  * every journal article, book chapter, and report authored by T. Sippel, and
  * anonymous / institution-authored reports the user contributed to but is not
    personally credited on (matched by the whitelists below).

Entries are de-duplicated by title, keeping the most complete record. CV.qmd
reads the resulting .bib. Run this whenever Zotero changes:  python3 sync_zotero.py
"""
import os, re, shutil, sqlite3, tempfile

HOME = os.path.expanduser("~")
ZOTERO_DB = os.path.join(HOME, "Zotero", "zotero.sqlite")
OUT_BIB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Bibliography", "cv_publications.bib")

AUTHOR_SURNAME = "Sippel"
# Institution-authored reports to include even though Sippel isn't a named author
ANON_AUTHORS = ["National Academies of Sciences", "Informal Offshore Wind Energy Group"]
ANON_TITLES = ["National Assessment by the Nature Record"]

# Zotero item type -> BibTeX entry type
TYPE_MAP = {"journalArticle": "article", "bookSection": "incollection", "report": "techreport",
            "book": "book"}
# Zotero field -> BibTeX field
FIELD_MAP = {
    "publicationTitle": "journal", "bookTitle": "booktitle", "institution": "institution",
    "publisher": "publisher", "volume": "volume", "issue": "number",
    "reportNumber": "number", "pages": "pages", "place": "address", "DOI": "doi",
}


def load_items(cur):
    """Return {itemID: {type, fields{}, authors[], modified}} for candidate items."""
    cur.execute("""
        SELECT i.itemID, it.typeName, i.dateModified
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        LEFT JOIN deletedItems di ON di.itemID = i.itemID
        WHERE di.itemID IS NULL AND it.typeName IN ('journalArticle','bookSection','report','book')
    """)
    items = {r[0]: {"type": r[1], "modified": r[2], "fields": {}, "authors": []} for r in cur.fetchall()}
    if not items:
        return items
    ids = ",".join(str(i) for i in items)

    cur.execute(f"""
        SELECT d.itemID, f.fieldName, v.value
        FROM itemData d
        JOIN itemDataValues v ON v.valueID = d.valueID
        JOIN fields f ON f.fieldID = d.fieldID
        WHERE d.itemID IN ({ids})
    """)
    for iid, fname, val in cur.fetchall():
        items[iid]["fields"][fname] = val

    cur.execute(f"""
        SELECT ic.itemID, ic.orderIndex, c.firstName, c.lastName
        FROM itemCreators ic
        JOIN creators c ON c.creatorID = ic.creatorID
        JOIN creatorTypes ct ON ct.creatorTypeID = ic.creatorTypeID
        WHERE ic.itemID IN ({ids}) AND ct.creatorType = 'author'
        ORDER BY ic.itemID, ic.orderIndex
    """)
    for iid, _order, first, last in cur.fetchall():
        items[iid]["authors"].append(((first or "").strip(), (last or "").strip()))
    return items


def year_of(fields):
    m = re.search(r"\d{4}", fields.get("date", ""))
    if not m or m.group(0) == "0000":   # skip undated / placeholder-year items
        return None
    return m.group(0)


def is_included(item):
    typ = item["type"]
    authors_flat = " and ".join(f"{l}, {f}" for f, l in item["authors"])
    title = item["fields"].get("title", "")
    sippel = typ in ("journalArticle", "bookSection", "report") and \
        AUTHOR_SURNAME.lower() in authors_flat.lower()
    anon = (typ in ("book", "report")) and (
        any(a.lower() in authors_flat.lower() for a in ANON_AUTHORS) or
        any(t.lower() in title.lower() for t in ANON_TITLES))
    return sippel or anon


def sanitize(val):
    return re.sub(r"[{}]", "", val).strip()


def author_string(authors):
    parts = []
    for first, last in authors:
        if first:
            parts.append(f"{last}, {first}")
        else:                       # institutional / single-field name
            parts.append("{" + last + "}")
    return " and ".join(parts)


def to_record(item):
    f = item["fields"]
    yr = year_of(f)
    if not yr:
        return None
    rec = {"_type": TYPE_MAP[item["type"]], "title": sanitize(f.get("title", "")),
           "year": yr}
    if item["authors"]:
        rec["author"] = author_string(item["authors"])
    for zf, bf in FIELD_MAP.items():
        if zf in f and bf not in rec:
            v = sanitize(f[zf])
            if v and v not in ("-", "–"):
                rec[bf] = v
    return rec


def completeness(rec):
    return sum(1 for k in ("author", "journal", "booktitle", "institution", "publisher",
                           "volume", "number", "pages", "doi") if rec.get(k))


def main():
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = tmp.name
    shutil.copy2(ZOTERO_DB, tmp_path)
    try:
        con = sqlite3.connect(tmp_path)
        items = load_items(con.cursor())
        con.close()
    finally:
        os.remove(tmp_path)

    recs = []
    for item in items.values():
        if not is_included(item):
            continue
        rec = to_record(item)
        if rec and rec["title"]:
            rec["_modified"] = item["modified"]
            recs.append(rec)

    # De-duplicate by normalized title; keep most complete, then most recently modified
    best = {}
    for rec in recs:
        key = re.sub(r"[^a-z0-9]", "", rec["title"].lower())[:60]
        cur = best.get(key)
        if cur is None or (completeness(rec), rec["_modified"]) > (completeness(cur), cur["_modified"]):
            best[key] = rec
    recs = sorted(best.values(), key=lambda r: (-int(r["year"]), r["title"]))

    order = ["author", "title", "year", "journal", "booktitle", "institution",
             "publisher", "volume", "number", "pages", "address", "doi"]
    lines = ["% Generated by sync_zotero.py from ~/Zotero/zotero.sqlite — do not edit by hand.",
             f"% {len(recs)} publications.\n"]
    for i, rec in enumerate(recs, 1):
        lines.append(f"@{rec['_type']}{{cv{i},")
        body = []
        for k in order:
            if rec.get(k):
                val = rec[k] if k == "year" else "{" + rec[k] + "}"
                body.append(f"  {k} = {val}")
        lines.append(",\n".join(body))
        lines.append("}\n")

    os.makedirs(os.path.dirname(OUT_BIB), exist_ok=True)
    with open(OUT_BIB, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"Wrote {len(recs)} publications to {OUT_BIB}")


if __name__ == "__main__":
    main()
