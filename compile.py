#!/usr/bin/env python3
"""
compile.py — reads source catalogues, writes .well-known/agent-resources.json

Produces a JSON-LD manifest conforming to Schema.org + A2A resource discovery.
Each entry in registry.yaml becomes a resource object in the manifest.
"""
import argparse
import json
import os
import yaml
from datetime import datetime, timezone

AGENT_ID = "https://github.com/curtiskrygier/Agentic-Resource-Directory"
GAS_BASE  = (
    "https://script.google.com/macros/s/"
    "AKfycbySUgHU2ynyj-GMc9_oR9qiWlwCVrNSeCwFXY_JYExxIldHYnQFfqgo_vE_uUBJg2L7/exec"
)

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

def schema_entry_to_resource(entry, schemas_base):
    """Convert one registry.yaml entry into a JSON-LD resource object."""
    schema_path = os.path.join(schemas_base, entry.get("path", ""))
    schema = {}
    if os.path.exists(schema_path):
        schema = load_yaml(schema_path)

    resource = {
        "@type":            schema.get("@type", "EducationalOccupationalCredential"),
        "@id":              f"https://raw.githubusercontent.com/curtiskrygier/a2knowledge/master/schemas/{entry.get('path', entry['id'])}",
        "identifier":       entry["id"],
        "name":             entry.get("name", entry["id"]),
        "provider": {
            "@type": "Organization",
            "name":  entry.get("issuer", "Unknown")
        },
        "inLanguage":       "fr" if entry.get("country") == "FR" else "en",
        "educationalLevel": entry.get("type", ""),
        "keywords":         entry.get("tags", []),
        "a2a:renderCapabilities": [
            {
                "surface":        "google-apps-script",
                "url":            f"{GAS_BASE}?nav={entry.get('nav', entry['id'].split('/')[-1])}",
                "renderStrategy": entry.get("render_strategy", "hub")
            }
        ],
    }

    # Attach exam metadata if present in schema
    if "levels" in schema:
        resource["hasPart"] = [
            {
                "@type":   "EducationalOccupationalProgram",
                "name":    lvl_data.get("label", lvl),
                "timeToComplete": lvl_data.get("exam", {}).get("duration", ""),
            }
            for lvl, lvl_data in schema["levels"].items()
        ]

    return resource


def build_manifest(registry_path):
    registry = load_yaml(registry_path)
    schemas_base = os.path.dirname(registry_path)

    resources = []
    for entry in registry.get("schemas", []):
        if entry["id"].endswith("_template"):
            continue
        resources.append(schema_entry_to_resource(entry, schemas_base))

    return {
        "@context": {
            "@vocab":  "https://schema.org/",
            "a2a":     "https://google.github.io/A2A/vocab#",
            "a2ui":    "https://github.com/curtiskrygier/a2ui/vocab#"
        },
        "@type":        "ItemList",
        "@id":          f"{AGENT_ID}/.well-known/agent-resources.json",
        "name":         "A2 Agentic Resource Discovery",
        "description":  (
            "Machine-discoverable index of a2knowledge curricula and a2ui "
            "rendering capabilities. Each resource is a compiled knowledge "
            "artefact queryable by A2A-compatible agents."
        ),
        "author": {
            "@type": "Person",
            "name":  "Curtis Krygier",
            "url":   "https://github.com/curtiskrygier"
        },
        "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "numberOfItems": len(resources),
        "itemListElement": resources
    }


def build_ai_catalog(registry_path: str) -> dict:
    """
    Spec-compliant ai-catalog.json per agenticresourcediscovery.org.
    Proposes application/a2ui-knowledge+json as a new MIME type for
    educational knowledge curricula — a gap in the current ARD spec.
    """
    registry = load_yaml(registry_path)

    entries = []
    for entry in registry.get("schemas", []):
        if entry["id"].endswith("_template"):
            continue
        slug = entry["id"].split("/")[-1]
        entries.append({
            "identifier":  f"urn:ai:curtiskrygier.github.io:knowledge:{entry['id']}",
            "displayName": entry.get("name", entry["id"]),
            "type":        "application/a2ui-knowledge+json",
            "url":         f"{GAS_BASE}?mode=api&resource={entry['id']}",
            "description": (
                f"{entry.get('name', entry['id'])} — "
                f"competency-mapped knowledge curriculum. "
                f"Render: {GAS_BASE}?nav={slug}"
            ),
            "tags": entry.get("tags", []),
        })

    return {
        "specVersion": "1.0",
        "host": {
            "displayName": "Curtis Krygier — A2 Knowledge",
            "identifier":  "https://github.com/curtiskrygier"
        },
        "entries": entries,
        "collections": [
            {
                "displayName": "a2knowledge — full schema + curriculum catalogue",
                "url":         "https://github.com/curtiskrygier/a2knowledge"
            }
        ]
    }


def build_agent_card() -> dict:
    """
    A2A agent card describing the ARD as a discoverable agent.
    Published at /.well-known/agent-card.json per a2a-protocol.org.
    """
    return {
        "name": "A2 Agentic Resource Discovery",
        "description": (
            "Curated registry of structured knowledge resources — "
            "competency-mapped curricula for professional certifications and "
            "national education frameworks, compiled for agent consumption. "
            "Proposes application/a2ui-knowledge+json as a type extension "
            "for educational resources in the ARD spec."
        ),
        "url": GAS_BASE,
        "provider": {
            "organization": "Curtis Krygier",
            "url":          "https://github.com/curtiskrygier/ard"
        },
        "version": "0.1.0",
        "capabilities": {
            "streaming":         False,
            "pushNotifications": False
        },
        "skills": [
            {
                "id":          "discover-resources",
                "name":        "Discover knowledge resources",
                "description": "Returns the full catalog via /.well-known/ai-catalog.json",
                "inputModes":  ["text"],
                "outputModes": ["application/json"]
            },
            {
                "id":          "render-resource",
                "name":        "Render a knowledge resource",
                "description": "Returns an interactive learning app for a given resource ID via A2UI GAS surface",
                "inputModes":  ["text"],
                "outputModes": ["text/html"]
            },
            {
                "id":          "export-case",
                "name":        "Export as CASE CFPackage",
                "description": "Returns a CASE-compliant CFPackage JSON for any registered resource — for LMS import",
                "inputModes":  ["text"],
                "outputModes": ["application/json"]
            }
        ],
        "securitySchemes": {
            "google": {
                "type":        "oauth2",
                "description": "Google account required for GAS render surface"
            }
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output",   required=True)
    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    os.makedirs(out_dir, exist_ok=True)

    # 1. Schema.org JSON-LD manifest (extended format)
    manifest = build_manifest(args.registry)
    with open(args.output, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  wrote {len(manifest['itemListElement'])} resources → {args.output}")

    # 2. ARD spec-compliant ai-catalog.json
    catalog_path = os.path.join(out_dir, "ai-catalog.json")
    catalog = build_ai_catalog(args.registry)
    with open(catalog_path, "w") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"  wrote {len(catalog['entries'])} entries → {catalog_path}")

    # 3. A2A agent card
    card_path = os.path.join(out_dir, "agent-card.json")
    with open(card_path, "w") as f:
        json.dump(build_agent_card(), f, indent=2, ensure_ascii=False)
    print(f"  wrote agent-card → {card_path}")


if __name__ == "__main__":
    main()
