#!/usr/bin/env python3
"""
case_export.py — export any a2knowledge schema as a CASE CFPackage JSON

We take the best of CASE (UUID identifiers, CFItemType vocabulary, isChildOf
associations) and leave the rest (K-12 assumptions, membership politics, static
document model). Output is a valid CFPackage a CASE-consuming LMS can import.

Usage:
  python3 case_export.py --schema path/to/schema.yaml --output exports/case/
  python3 case_export.py --registry path/to/registry.yaml --output exports/case/
"""
import argparse
import json
import os
import uuid
import yaml
from datetime import datetime, timezone

# ── CASE CFItemType vocabulary (we map from atom_hint) ────────────────────────
# We take the useful controlled vocabulary and ignore K-12-specific types.
ATOM_HINT_TO_CF_ITEM_TYPE = {
    "method":    "Procedure",
    "concept":   "Concept",
    "glossary":  "Term",
    "checklist": "Checklist",
    "piege":     "AssessmentItem",
    "scenario":  "AssessmentItem",
    "comparison":"Concept",
    "drill":     "AssessmentItem",
}

CASE_CONTEXT = "https://opensalt.net/api/v1p0"
LICENSE_DEFAULT = "https://creativecommons.org/licenses/by/4.0/"


def deterministic_uuid(seed: str) -> str:
    """UUID v5 from a stable seed — same slug always produces same UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://a2knowledge/{seed}"))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_competencies(schema: dict) -> list[dict]:
    """Normalise domain-based and subject-based schemas to a flat competency list."""
    items = []
    # pro-cert style: domains > required_competencies
    for domain in schema.get("domains", []):
        for c in domain.get("required_competencies", []):
            items.append({**c, "_domain": domain["id"], "_domain_name": domain["name"]})
    # national-education style: subjects > required_competencies
    for subj_id, subj in schema.get("subjects", {}).items():
        for c in subj.get("required_competencies", []):
            items.append({**c, "_domain": subj_id, "_domain_name": subj.get("label", subj_id)})
    return items


def get_domains(schema: dict) -> list[dict]:
    """Normalise domain/subject lists to a common shape."""
    domains = []
    for d in schema.get("domains", []):
        domains.append({"id": d["id"], "name": d["name"], "weight": d.get("weight", 0)})
    for subj_id, subj in schema.get("subjects", {}).items():
        domains.append({"id": subj_id, "name": subj.get("label", subj_id), "weight": 0})
    return domains


def build_cf_document(schema: dict, doc_uuid: str) -> dict:
    return {
        "identifier":       doc_uuid,
        "uri":              f"https://a2knowledge/{schema['id']}",
        "serverGeneratedId": doc_uuid,
        "title":            schema.get("name", schema["id"]),
        "description":      schema.get("description", ""),
        "creator":          "Curtis Krygier — a2knowledge catalogue",
        "publisher":        schema.get("issuer", ""),
        "language":         "fr" if schema.get("country") == "FR" else "en",
        "version":          "1.0",
        "adoptionStatus":   "Draft",
        "statusStartDate":  schema.get("last_updated", now_iso()),
        "licenseURI":       LICENSE_DEFAULT,
        "lastChangeDateTime": now_iso(),
        # A2UI extension fields — CASE ignores unknown keys
        "extensions": {
            "a2knowledge:id":              schema["id"],
            "a2knowledge:renderStrategy":  schema.get("render_strategy", "hub"),
            "a2knowledge:source":          schema.get("source", ""),
        }
    }


def build_cf_items(schema: dict, doc_uuid: str) -> list[dict]:
    """One CFItem per domain + one CFItem per competency."""
    items = []
    competencies = get_competencies(schema)
    domains = get_domains(schema)

    # Domain-level items (parents)
    for domain in domains:
        d_uuid = deterministic_uuid(f"{schema['id']}/{domain['id']}")
        items.append({
            "identifier":           d_uuid,
            "uri":                  f"https://a2knowledge/{schema['id']}/{domain['id']}",
            "fullStatement":        domain["name"],
            "humanCodingScheme":    domain["id"],
            "CFItemType":           "Domain",
            "language":             "fr" if schema.get("country") == "FR" else "en",
            "lastChangeDateTime":   now_iso(),
            "CFDocumentURI": {
                "identifier": doc_uuid,
                "uri":        f"https://a2knowledge/{schema['id']}"
            },
            # A2UI extensions
            "extensions": {
                "a2knowledge:weight": domain.get("weight", 0)
            }
        })

    # Competency-level items (children)
    for comp in competencies:
        c_uuid = deterministic_uuid(f"{schema['id']}/{comp['id']}")
        cf_item_type = ATOM_HINT_TO_CF_ITEM_TYPE.get(comp.get("atom_hint", "concept"), "Concept")

        # educationLevel: map our level field to a meaningful string
        level = comp.get("level", "both")
        if level == "both":
            ed_levels = ["professional-foundation", "professional-practitioner"]
        elif level == "foundation":
            ed_levels = ["professional-foundation"]
        elif level == "practitioner":
            ed_levels = ["professional-practitioner"]
        else:
            ed_levels = [level]

        items.append({
            "identifier":           c_uuid,
            "uri":                  f"https://a2knowledge/{schema['id']}/{comp['id']}",
            "fullStatement":        comp.get("label", comp["id"]),
            "humanCodingScheme":    comp["id"],
            "CFItemType":           cf_item_type,
            "educationLevel":       ed_levels,
            "language":             "fr" if schema.get("country") == "FR" else "en",
            "lastChangeDateTime":   now_iso(),
            "CFDocumentURI": {
                "identifier": doc_uuid,
                "uri":        f"https://a2knowledge/{schema['id']}"
            },
            # A2UI extensions — CASE consumers ignore these; our tools use them
            "extensions": {
                "a2knowledge:atomHint": comp.get("atom_hint", "concept"),
                "a2knowledge:weight":   comp.get("weight", "medium"),
                "a2knowledge:domain":   comp.get("_domain", ""),
            }
        })

    return items


def build_cf_associations(schema: dict, items: list[dict]) -> list[dict]:
    """
    Build isChildOf associations: domain items are children of the CFDocument,
    competency items are children of their domain item.
    We use the humanCodingScheme to match items back to schema entries.
    """
    associations = []
    doc_uuid = deterministic_uuid(schema["id"])
    item_by_code = {i["humanCodingScheme"]: i for i in items}

    competencies = get_competencies(schema)
    domains = get_domains(schema)

    # Domains are children of the document root
    for domain in domains:
        d_item = item_by_code.get(domain["id"])
        if not d_item:
            continue
        a_uuid = deterministic_uuid(f"assoc/{schema['id']}/{domain['id']}/doc")
        associations.append({
            "identifier":       a_uuid,
            "uri":              f"https://a2knowledge/assoc/{schema['id']}/{domain['id']}/doc",
            "originNodeURI": {
                "identifier": d_item["identifier"],
                "uri":        d_item["uri"]
            },
            "associationType":  "isChildOf",
            "destinationNodeURI": {
                "identifier": doc_uuid,
                "uri":        f"https://a2knowledge/{schema['id']}"
            },
            "lastChangeDateTime": now_iso()
        })

    # Competencies are children of their domain
    for i, comp in enumerate(competencies):
        c_item  = item_by_code.get(comp["id"])
        d_item  = item_by_code.get(comp.get("_domain", ""))
        if not c_item or not d_item:
            continue
        a_uuid = deterministic_uuid(f"assoc/{schema['id']}/{comp['id']}/domain")
        associations.append({
            "identifier":       a_uuid,
            "uri":              f"https://a2knowledge/assoc/{schema['id']}/{comp['id']}/domain",
            "originNodeURI": {
                "identifier": c_item["identifier"],
                "uri":        c_item["uri"]
            },
            "associationType":  "isChildOf",
            "destinationNodeURI": {
                "identifier": d_item["identifier"],
                "uri":        d_item["uri"]
            },
            "sequenceNumber":   i + 1,
            "lastChangeDateTime": now_iso()
        })

    return associations


def export_schema(schema_path: str, output_dir: str):
    schema   = load_yaml(schema_path)
    schema_id = schema.get("id", os.path.basename(schema_path))
    doc_uuid = deterministic_uuid(schema_id)

    cf_document    = build_cf_document(schema, doc_uuid)
    cf_items       = build_cf_items(schema, doc_uuid)
    cf_associations = build_cf_associations(schema, cf_items)

    package = {
        "@context":      CASE_CONTEXT,
        "@type":         "CFPackage",
        "CFDocument":    cf_document,
        "CFItems":       cf_items,
        "CFAssociations": cf_associations,
    }

    # Mirror the schema ID path under output_dir
    out_path = os.path.join(output_dir, schema_id.replace("/", os.sep) + ".json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(package, f, indent=2, ensure_ascii=False)

    n_items  = len(cf_items)
    n_assocs = len(cf_associations)
    print(f"  {schema_id} → {out_path}")
    print(f"    {n_items} CFItems · {n_assocs} CFAssociations")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Export a2knowledge schemas as CASE CFPackage JSON"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--schema",   help="Path to a single schema YAML file")
    group.add_argument("--registry", help="Path to registry.yaml — exports all schemas")
    parser.add_argument("--output",  default="exports/case", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if args.schema:
        export_schema(args.schema, args.output)

    elif args.registry:
        registry = load_yaml(args.registry)
        schemas_dir = os.path.dirname(args.registry)
        exported = 0
        for entry in registry.get("schemas", []):
            if entry["id"].endswith("_template"):
                continue
            schema_path = os.path.join(schemas_dir, entry.get("path", ""))
            if not os.path.exists(schema_path):
                print(f"  ⚠  skipping {entry['id']} — schema file not found at {schema_path}")
                continue
            export_schema(schema_path, args.output)
            exported += 1
        print(f"\n✓  exported {exported} schemas → {args.output}/")


if __name__ == "__main__":
    main()
