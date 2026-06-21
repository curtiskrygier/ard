# Agentic Resource Discovery (ARD)

A machine-discoverable index of structured knowledge resources, built to test
the concept of an [ARD](https://agenticresourcediscovery.org)-compatible resource discovery on top of real, shipped
catalogues.

**Prerequisites:** Python ≥ 3.9, PyYAML (`pip install pyyaml`). Both source repos must be public on GitHub before running `build.sh`.

---

## How this came to be

**[a2ui](https://github.com/curtiskrygier/a2ui)** came first.
It started as a way to build interactive learning apps on Google Apps Script — a
rendering vocabulary of atoms (flashcard decks, step sequences, knowledge checks,
hub navigation) that could be driven by a JSON payload. Built by solving real
problems: meet stage demos at work, a study app for a French Brevet exam.

**[a2knowledge](https://github.com/curtiskrygier/a2knowledge)** came second. Looking at what the pipeline was actually doing —
extracting competency-mapped, exam-weighted knowledge from official curricula and
certification guides — it became clear this wasn't just input data for the renderer.
It was a knowledge layer in its own right: structured, schema-validated, and
independent of any presentation surface.

**This repo** is the third layer. With two real catalogues already running, the
question became: what does it look like when you make that knowledge
machine-discoverable in a way that any agent can find and consume it — not just
the GAS renderer?

That's the ARD. Not a framework designed upfront. A natural description of what
was already built.

---

## What it does

The ARD assembles a discovery manifest from source catalogues at build time.
No content lives here — it reads from published catalogue repos, compiles a
JSON-LD manifest, and serves it at `/.well-known/agent-resources.json`.

```
git clone a2knowledge  ← knowledge schemas + curricula
         ↓
    compile.py
         ↓
.well-known/agent-resources.json   ← ARD discovery endpoint
.well-known/ai-catalog.json        ← ai-catalog.json per ARD spec
exports/case/*.json                ← CASE CFPackage export for LMS consumers (local CLI)
```

Any ARD-compatible agent can query `/.well-known/ai-catalog.json` and
discover what knowledge resources are available, what surface each can be
rendered on, and how to invoke them.

---

## Architecture

```
Agentic-Resource-Directory/   ← this repo (assembly + serving layer)
├── build.sh                  ← clone catalogues, run compile.py
├── compile.py                ← registry.yaml → agent-resources.json + ai-catalog.json
├── case_export.py            ← any schema → CASE CFPackage (local CLI, LMS bridge)
├── Dockerfile                ← Cloud Run deployment stub (demo; use a WSGI server for prod)
├── .well-known/
│   ├── agent-resources.json  ← compiled ARD discovery manifest (Schema.org JSON-LD)
│   ├── ai-catalog.json       ← ARD spec ai-catalog.json
│   └── agent-card.json       ← A2A agent card
└── exports/case/             ← CASE CFPackage output per schema

a2knowledge/          ← source catalogue (separate repo)
├── schemas/          ← competency specs (schema.yaml per qualification)
├── *.curriculum.md   ← extracted, competency-anchored knowledge
└── schemas/registry.yaml ← catalogue index
```

The ARD and the catalogue are **independent repos**. The ARD's build step clones
the catalogue — that's the only coupling. On the laptop they sit side by side.
On Cloud Run the Dockerfile does the same clone at container build time.

---

## Resources (current)

| ID | Name | Render surface |
|---|---|---|
| `national-education/fr/dnb-2026` | Diplôme National du Brevet — Session 2026 | [GAS hub](https://script.google.com/macros/s/AKfycbySUgHU2ynyj-GMc9_oR9qiWlwCVrNSeCwFXY_JYExxIldHYnQFfqgo_vE_uUBJg2L7/exec?nav=brevet-2026) |
| `pro-cert/nist/nist-ai-rmf` | NIST AI Risk Management Framework 1.0 | [GAS hub](https://script.google.com/macros/s/AKfycbySUgHU2ynyj-GMc9_oR9qiWlwCVrNSeCwFXY_JYExxIldHYnQFfqgo_vE_uUBJg2L7/exec?nav=nist-ai-rmf) |

---

## Run locally

```bash
# Bootstrap — clone catalogues and compile manifest
./build.sh

# Or point directly at a local catalogue clone (both source repos must be cloned)
python3 compile.py \
  --registry ../a2knowledge/schemas/registry.yaml \
  --output .well-known/agent-resources.json

# Export any schema as a CASE CFPackage (for LMS import)
python3 case_export.py \
  --registry ../a2knowledge/schemas/registry.yaml \
  --output exports/case/
```

---

## Standards alignment

| Standard | Relationship |
|---|---|
| **[ARD spec](https://agenticresourcediscovery.org)** | `/.well-known/ai-catalog.json` and `agent-resources.json` follow the Agentic Resource Discovery well-known path convention |
| **Google A2A** | `/.well-known/agent-card.json` follows A2A agent card convention |
| **Schema.org** | All resources typed as `EducationalOccupationalCredential` or `Course` |
| **CASE (1EdTech)** | `case_export.py` produces valid CFPackage JSON — UUID v5 identifiers, CFItemType vocabulary, `isChildOf` associations. We use CASE's structural vocabulary; we don't adopt its governance model. |
| **QTI** | Planned — `knowledge_check` atoms map directly to QTI assessment items |

**MIME type note:** Resources use `"type": "application/a2ui-knowledge+json"` — a proposed type extension for educational knowledge curricula. This is not in the IANA registry or current ARD spec; it is a proposal. Agents should treat it as an experimental extension.

---

## Cloud path

```
Now (local)               GitHub Pages / Cloud Run
────────────────          ────────────────────────
./build.sh               Dockerfile CMD: ./build.sh
local filesystem         public GitHub repos as source
```

Adding a catalogue: one new `clone_or_pull` line in `build.sh`.

---

## Related

- [a2knowledge](https://github.com/curtiskrygier/a2knowledge) — the knowledge pipeline this ARD indexes
- [a2ui](https://github.com/curtiskrygier/a2ui) — the atom vocabulary and GAS renderer
