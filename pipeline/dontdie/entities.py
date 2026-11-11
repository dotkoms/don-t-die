"""Entity pages (M4): compounds, organizations, trials — the destinations
the digest and item pages link into.

Deterministic, like the digest and retraction flags: no model, no fetches,
a full recompute over the corpus on every pipeline run. Three entity kinds,
each linked from source-truth fields only:

- **Compounds** — a curated intervention vocabulary (below), NOT the raw
  DrugAge compound list, which is full of generic chemistry ("Glucose",
  "Ethanol", "Lactic acid") that would flood abstracts with junk links.
  Items link by word-boundary mention in title/abstract; DrugAge assay rows
  link by their own compound field where it matches the vocabulary.
- **Organizations** — grant institutions (NIH RePORTER, UKRI GtR) and trial
  sponsors (CT.gov, ISRCTN, CTIS). Name variants collapse to one slug;
  the display name prefers a properly-cased form because the grant
  registries ship ALL CAPS while sponsors ship title case.
- **Trials** — every relevant registry record is an entity; corpus items
  whose text cites a registry id (NCT/ISRCTN/EU CT number) link to it.

An entity exists only with at least one link (no empty pages), and only
relevant, un-retracted items are linked. One item links to one entity once:
when several link kinds apply, the most specific wins
(assay > record > citation > funding > sponsor > mention).
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from . import store
from .relevance import _HYPHEN_MAP

# The curated intervention vocabulary: (slug, display name, family, aliases).
# Plan's pharmacological list + peptides (gate terms) + the GLP-1 family.
# Growth is one line here; the list is deliberately not the DrugAge compound
# column (see module docstring).
COMPOUNDS: List[Tuple[str, str, str, List[str]]] = [
    # Pharmacological interventions (plan §2).
    ("rapamycin", "Rapamycin", "mTOR inhibitor", ["sirolimus"]),
    ("metformin", "Metformin", "biguanide", []),
    ("acarbose", "Acarbose", "glycosidase inhibitor", []),
    ("spermidine", "Spermidine", "polyamine", []),
    ("resveratrol", "Resveratrol", "sirtuin activator", []),
    ("nicotinamide", "Nicotinamide", "NAD+ precursor", []),
    ("nicotinamide-riboside", "Nicotinamide riboside", "NAD+ precursor", ["NR"]),
    ("nicotinamide-mononucleotide", "Nicotinamide mononucleotide",
     "NAD+ precursor", ["NMN"]),
    ("fisetin", "Fisetin", "senolytic", []),
    ("dasatinib", "Dasatinib", "senolytic", []),
    ("quercetin", "Quercetin", "senolytic", []),
    ("navitoclax", "Navitoclax", "senolytic", ["ABT-263"]),
    ("canagliflozin", "Canagliflozin", "SGLT2 inhibitor", []),
    ("17alpha-estradiol", "17α-estradiol", "sex hormone",
     ["17alpha-estradiol", "17α-estradiol", "17-alpha-estradiol",
      "17a-estradiol"]),
    ("ta-65", "TA-65", "telomerase activator", ["TA65"]),
    # Peptide interventions (M2 gate terms).
    ("bpc-157", "BPC-157", "peptide", []),
    ("epitalon", "Epitalon", "peptide", ["epithalon"]),
    ("mots-c", "MOTS-c", "mitochondrial-derived peptide", []),
    ("humanin", "Humanin", "mitochondrial-derived peptide", []),
    ("ghk-cu", "GHK-Cu", "peptide", []),
    ("elamipretide", "Elamipretide", "mitochondrial-derived peptide",
     ["SS-31", "Bendavia"]),
    ("tesamorelin", "Tesamorelin", "peptide", []),
    ("ipamorelin", "Ipamorelin", "peptide", []),
    ("cjc-1295", "CJC-1295", "peptide", []),
    ("ghrp-6", "GHRP-6", "growth hormone-releasing peptide", []),
    ("ghrp-2", "GHRP-2", "growth hormone-releasing peptide", []),
    ("hexarelin", "Hexarelin", "growth hormone-releasing peptide", []),
    ("thymosin-beta-4", "Thymosin beta-4", "peptide",
     ["thymosin beta 4", "thymosin beta-4", "TB-500", "TB500", "Tβ4"]),
    ("thymosin-alpha-1", "Thymosin alpha-1", "peptide",
     ["thymosin alpha 1", "thymosin alpha-1", "Tα1"]),
    ("aod-9604", "AOD-9604", "peptide", []),
    ("selank", "Selank", "peptide", []),
    ("semax", "Semax", "peptide", []),
    ("dihexa", "Dihexa", "peptide", []),
    ("noopept", "Noopept", "peptide", []),
    ("carnosine", "Carnosine", "peptide", []),
    # The GLP-1 agonist family (plan lists "GLP-1s" as a class).
    ("semaglutide", "Semaglutide", "GLP-1 agonist", []),
    ("tirzepatide", "Tirzepatide", "GLP-1 / GIP agonist", []),
    ("retatrutide", "Retatrutide", "GLP-1 / GIP / glucagon agonist", []),
    ("orforglipron", "Orforglipron", "GLP-1 agonist", []),
    ("liraglutide", "Liraglutide", "GLP-1 agonist", []),
    ("exenatide", "Exenatide", "GLP-1 agonist", []),
    # Gate v1.3 (2026-11-11): the clinic-sweep compounds, plus the
    # big-literature compounds that are entities but deliberately not gate
    # terms (taurine, alpha-ketoglutarate, everolimus).
    ("sermorelin", "Sermorelin", "GHRH analog peptide", []),
    ("ibutamoren", "Ibutamoren", "GH secretagogue",
     ["MK-677", "MK0677", "ibutamoren mesylate"]),
    ("5-amino-1mq", "5-Amino-1MQ", "NNMT inhibitor peptide",
     ["5A1MQ", "5-amino-1-methylquinolinium"]),
    ("ara-290", "ARA-290", "innate repair peptide", ["cibinetide"]),
    ("foxo4-dri", "FOXO4-DRI", "peptide senolytic",
     ["FOXO4 DRI", "foxo4-dri"]),
    ("dsip", "DSIP", "peptide",
     ["delta sleep-inducing peptide", "delta sleep inducing peptide"]),
    ("cagrilintide", "Cagrilintide", "amylin analog", []),
    ("mazdutide", "Mazdutide", "GLP-1 / glucagon agonist", []),
    ("survodutide", "Survodutide", "GLP-1 / glucagon agonist", []),
    ("urolithin-a", "Urolithin A", "mitophagy activator", []),
    ("berberine", "Berberine", "AMPK activator", ["dihydroberberine"]),
    ("taurine", "Taurine", "amino acid", []),
    ("alpha-ketoglutarate", "Alpha-ketoglutarate", "metabolite",
     ["α-ketoglutarate", "CaAKG", "AKG",
      "calcium alpha-ketoglutarate", "calcium α-ketoglutarate"]),
    ("glynac", "GlyNAC", "glycine + N-acetylcysteine",
     ["glycine and N-acetylcysteine"]),
    ("everolimus", "Everolimus", "mTOR inhibitor (rapalog)", ["Afinitor"]),
]

# Link kinds, most specific first — the winner when one item-entity pair
# qualifies for several (a DrugAge row that also mentions its compound in
# the title is an assay, not a mention).
_HOW_PRIORITY = ["assay", "record", "citation", "funding", "sponsor",
                 "mention"]

_TRIAL_SOURCES = {"ctgov", "isrctn", "ctis"}
_GRANT_SOURCES = {"reporter", "gtr"}

# Registry ids as they appear in text: NCT + 8 digits, ISRCTN + 6–10,
# EU CT number 2022-501073-40-00.
_TRIAL_ID_RE = re.compile(
    r"\b(NCT\d{8}|ISRCTN\d{6,10}|\d{4}-\d{6}-\d{2}-\d{2})\b"
)

_TOKEN_STRIP = "(){}[]<>.,;:!?'“”‘’…·\""


def _norm(text: str) -> str:
    """Lowercase, fold typographic hyphens, collapse whitespace."""
    return " ".join((text or "").lower().translate(_HYPHEN_MAP).split())


def _ngrams(text: str) -> set:
    """The 1–3 word n-grams of a text field, punctuation edges stripped."""
    tokens = [t.strip(_TOKEN_STRIP)
              for t in _norm(text).split()]
    tokens = [t for t in tokens if t]
    grams = set()
    for n in (1, 2, 3):
        for i in range(len(tokens) - n + 1):
            grams.add(" ".join(tokens[i:i + n]))
    return grams


def _name_index() -> Dict[str, Tuple[str, str, str]]:
    """Normalized name/alias → (compound slug, display name, family)."""
    index: Dict[str, Tuple[str, str, str]] = {}
    for slug, name, family, aliases in COMPOUNDS:
        for key in [name, *aliases]:
            index[_norm(key)] = (slug, name, family)
    return index


def _org_slug(name: str) -> str:
    """A stable slug for an organization name; variants collapse here."""
    slug = re.sub(r"[^a-z0-9]+", "-", _norm(name)).strip("-")
    return slug


def _org_display(variants: Counter) -> str:
    """The display name: prefer a properly-cased form over the ALL-CAPS
    the grant registries ship; most frequent wins, ties broken
    lexicographically so the rebuild is deterministic."""
    proper = [v for v in variants if v != v.upper()]
    pool = proper or list(variants)
    return sorted(pool, key=lambda v: (-variants[v], v))[0]


def build(dsn: Optional[str] = None) -> Dict[str, Any]:
    """Recompute every entity and its item links from the corpus.

    Idempotent: both tables are derived state, emptied and rebuilt each run
    (entity ids are internal; nothing outside item_entities references them).
    """
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, source_id, slug, title,
                       raw->>'abstract', raw->>'brief_summary',
                       raw->>'summary', raw->>'official_title',
                       raw->>'compound', raw->>'institution',
                       raw->>'sponsor'
                FROM items
                WHERE is_relevant AND NOT is_retracted
                ORDER BY id
                """
            )
            rows = cur.fetchall()

        names = _name_index()
        name_keys = set(names)
        # (kind, slug) → {"name", "family"/…, "variants"}; links accumulate
        # per (item, entity) with the most specific how.
        meta: Dict[Tuple[str, str], Dict[str, Any]] = {}
        links: Dict[Tuple[int, Tuple[str, str]], str] = {}

        def add(item_id: int, key: Tuple[str, str], how: str) -> None:
            pair = (item_id, key)
            if pair in links:
                if _HOW_PRIORITY.index(how) < \
                        _HOW_PRIORITY.index(links[pair]):
                    links[pair] = how
            else:
                links[pair] = how

        # (kind, slug) keyed trial entities: registry id → entity key.
        trials: Dict[str, Tuple[str, str]] = {}
        # Citations are resolved after the loop: an item citing a registry id
        # must link to its record regardless of which row the scan met first.
        citations: List[Tuple[int, str]] = []

        for (item_id, source, source_id, slug, title, abstract,
             brief_summary, summary, official_title, compound,
             institution, sponsor) in rows:
            text = " ".join(
                t for t in (title, abstract, brief_summary, summary,
                            official_title) if t
            )

            # Compounds: vocabulary mentions in the searchable text, plus
            # the DrugAge row's own compound field.
            grams = _ngrams(text)
            for gram in grams & name_keys:
                cslug, cname, family = names[gram]
                meta.setdefault(("compound", cslug),
                                {"name": cname, "family": family})
                add(item_id, ("compound", cslug), "mention")
            if source == "drugage" and compound:
                hit = names.get(_norm(compound))
                if hit:
                    cslug, cname, family = hit
                    meta.setdefault(("compound", cslug),
                                    {"name": cname, "family": family})
                    add(item_id, ("compound", cslug), "assay")

            # Trials: every registry record is an entity; items citing a
            # known registry id link to it.
            if source in _TRIAL_SOURCES:
                tslug = _norm(source_id)
                trials[source_id] = (("trial", tslug), item_id)
                meta.setdefault(
                    ("trial", tslug),
                    {"name": title, "registry": source,
                     "registry_id": source_id, "record_slug": slug},
                )
                add(item_id, ("trial", tslug), "record")
            for found in _TRIAL_ID_RE.findall(text):
                citations.append((item_id, found))

            # Organizations: grant institutions and trial sponsors.
            org_name = None
            org_how = None
            if source in _GRANT_SOURCES:
                org_name, org_how = institution, "funding"
            elif source in _TRIAL_SOURCES:
                org_name, org_how = sponsor, "sponsor"
            if org_name:
                key = ("org", _org_slug(org_name))
                entry = meta.setdefault(key, {"variants": Counter()})
                entry["variants"][org_name] += 1
                add(item_id, key, org_how)

        for item_id, found in citations:
            hit = trials.get(found)
            if hit and hit[1] != item_id:  # a record never cites itself
                add(item_id, hit[0], "citation")

        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM entities")  # cascades item_entities
            by_key: Dict[Tuple[str, str], int] = {}
            counts: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
            for (_, key), how in links.items():
                counts[key][how] += 1
            for key in sorted(meta):
                kind, eslug = key
                entry = meta[key]
                if kind == "org":
                    name = _org_display(entry["variants"])
                    data: Dict[str, Any] = {}
                else:
                    name = entry["name"]
                    data = {k: v for k, v in entry.items() if k != "variants"}
                data.update(counts[key])
                data["items"] = sum(counts[key].values())
                cur.execute(
                    """
                    INSERT INTO entities (kind, slug, name, data)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (kind, eslug, name, json.dumps(data, default=str)),
                )
                by_key[key] = cur.fetchone()[0]
            cur.executemany(
                "INSERT INTO item_entities (item_id, entity_id, how)"
                " VALUES (%s, %s, %s)",
                [(item_id, by_key[key], how)
                 for (item_id, key), how in links.items()],
            )
    finally:
        conn.close()

    kinds = Counter(kind for kind, _ in meta)
    return {
        "compounds": kinds["compound"],
        "orgs": kinds["org"],
        "trials": kinds["trial"],
        "links": len(links),
    }
