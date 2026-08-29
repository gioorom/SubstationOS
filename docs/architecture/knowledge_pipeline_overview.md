# Knowledge Pipeline Overview

**Status:** As-built reference, established by Milestone 12 (Knowledge
Platform Hardening), extended by Milestone 13 (Structured Retrieval
Foundation), Milestone 14 (Context Builder Foundation), Milestone 15
(Prompt Builder Foundation), Milestone 16 (LLM Provider
Abstraction Layer), Milestone 17 (LLM Invocation Runtime),
Milestone 18 (Engineering Response Foundation, EPIC 5), Milestone
19 (Engineering Session Foundation, EPIC 5), Milestone 20
(Conversation Foundation, EPIC 5), Milestone 21 (Working Memory
Foundation, EPIC 5), Milestone 22 (Engineering Request
Classification, EPIC 5), Milestone 23A (Engineering Engine
Foundation, EPIC 5), Milestone 23B.1 (Document Lookup workflow,
EPIC 5), Milestone 23B.2 (Engineering Explanation workflow,
EPIC 5), Milestone 23B.3 (Classification-to-Retrieval Bridge,
EPIC 5), Milestone 24.1 (Engineering Verification workflow,
EPIC 5), Milestone 24.2 (Engineering Comparison workflow,
EPIC 5), Milestone 25.1 (Document Ingestion Pipeline,
EPIC 2), Milestone 25.2 (Document Identity and Content
Access, EPIC 2), Milestone 26.1 (Canonical PDF
Representation, EPIC 2), Milestone 27.1 (Canonical Text
Segmentation, EPIC 2), Milestone 26.2 (PDF Consumption
Consolidation, EPIC 2), Milestone 28.1 (Engineering Evidence
Extraction, EPIC 2), Milestone 28.2 (Engineering Evidence
Evaluation Framework, EPIC 2), Milestone 29.1 (Engineering
Entity Resolution, EPIC 2), Milestone 29.2 (Engineering Fact
Construction, EPIC 2), and Milestone 30.1 (Engineering Semantic
Interpretation, EPIC 2).
Describes the governed knowledge pipeline as it
exists today — not the product vision
(`project_intelligence_architecture.md` describes vision and roadmap;
this document describes what is actually implemented, tested, and
running). Update this document when a stage's real behavior changes;
it is not an ADR and carries no historical Context/Decision record of
its own.

## The pipeline, stage by stage

```
Documents → Document Identity → Document Ingestion → Canonical PDF Representation →
Canonical Text Segmentation → Engineering Evidence Extraction →
Engineering Evidence Evaluation → Engineering Entity Resolution →
Engineering Fact Construction → Engineering Semantic Interpretation →
Governed Human Review → Governed Knowledge Graph →
Governed Structured Retrieval → Governed Context Assembly →
Prompt Builder → LLM Provider Abstraction Layer → LLM Invocation Runtime →
Engineering Response → Engineering Session → Conversation →
Working Memory → Engineering Request Classification →
Classification-to-Retrieval Bridge →
Engineering Engine (workflow selection → plan → execution)
```


**One authoritative path, since EPIC 31.4.**

```
Queryable engineering graph knowledge  =  Governed Knowledge Graph
```

The chain above is the only way engineering knowledge becomes queryable.
The Canonical Facts branch that used to sit between Canonicalization and
Context Builder - `Graph Builder → Project Knowledge Graph → Graph Query
→ Structured Retrieval` - is **retired**
([ADR-0028](adr/0028-retire-the-canonical-facts-graph.md)): 20 routes
withdrawn, its packages deleted, its seven tables dropped by migration
`f4a90c27b615`.

**Proposed Claims, Review Workflow and Canonicalization survive** and
still serve their own routes. They hold human-authored claims and the
legacy review history over them - the *input* the retired projection was
computed from, not a queryable graph. They no longer feed anything
downstream: an approved legacy claim reaches no queryable engineering
knowledge, which is [ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md)
with nothing left behind it.

**Milestone 23B.3 made this chain traversable from a raw sentence.**
Until then the classifier decided which workflow a request wanted and the
engine required retrieval criteria only a caller who already knew the
graph's contents could supply - a seam no component crossed. The
Retrieval Bridge closes it:

```
Raw Request → Classification → Retrieval Bridge → Engine → Workflow
```

The bridge derives criteria; it executes nothing, and the engine still
receives an explicit execution request. Neither depends on the other -
enforced by dedicated architecture tests.

**Five workflows are implemented**: `KNOWLEDGE_QUERY` (Milestone 23A),
`DOCUMENT_LOOKUP` (Milestone 23B.1), `ENGINEERING_EXPLANATION`
(Milestone 23B.2), `ENGINEERING_VERIFICATION` (Milestone 24.1) and
`ENGINEERING_COMPARISON` (Milestone 24.2). Every other classified intent
returns an explicit `UNSUPPORTED` engine result and runs no downstream
component at all.

**`ENGINEERING_COMPARISON` is the first workflow whose *pipeline*
differs**, not only its prompt. It retrieves two evidence sets
independently and keeps their identity from retrieval through context,
prompt and response:

```
Raw Request
   → Classification
   → Comparison Preparation      (exactly two operands, order preserved)
   → Left Retrieval + Right Retrieval
   → Comparison Context          (two whole ContextPackages, never merged)
   → Comparison Prompt           (LEFT_KNOWLEDGE / RIGHT_KNOWLEDGE)
   → Runtime
   → EngineeringResponse
```

Its safety property is the one the domain most needs: **when either side
retrieved no evidence, the outcome is structurally forced to
`INSUFFICIENT_EVIDENCE`**, whatever the model wrote. Given evidence for
T1 and none for T2, a fluent answer would read "T2 lacks what T1 has" -
which is a statement about what the index covers, not about the
installation. Absence of retrieved evidence is not evidence of absence.

**`ENGINEERING_VERIFICATION` is the first reasoning workflow.** It
traverses the pipeline above unchanged and differs from `KNOWLEDGE_QUERY`
at the same single stage an explanation does - the prompt objective - but
asks a different *kind* of question: not "tell me about this" but "does
the project's own evidence support this statement?" Its answer carries a
machine-readable verdict (`SUPPORTED`, `NOT_SUPPORTED`,
`INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`) read from a declared
first-line protocol, and **an empty evidence set structurally forces
`INSUFFICIENT_EVIDENCE`** whatever the model wrote - a verification
cannot come back supported from a project with nothing in it. That the
pipeline absorbed a reasoning workflow with no new stage is the clearest
evidence yet that the stages model *how knowledge becomes an answer*
rather than *which question was asked*.

**`ENGINEERING_EXPLANATION` is the second LLM-powered workflow, and
traverses the pipeline above unchanged.** It differs from
`KNOWLEDGE_QUERY` at exactly one stage: it asks Prompt Builder for its
`ENGINEERING_EXPLANATION` objective rather than a direct answer. Same
Structured Retrieval, same Context Builder, same runtime, same
Engineering Response. That the pipeline absorbed a materially different
kind of engineering question without a new stage is the point - the
stages model *how knowledge becomes an answer*, not *which question was
asked*.

**The pipeline above is the knowledge-query path, not the only path.**
`DOCUMENT_LOOKUP` is the first workflow that answers **without any LLM**:
it branches off after Engineering Request Classification and reads the
Engineering Index directly, skipping Graph Query, Structured Retrieval,
Context Builder, Prompt Builder and both LLM stages entirely:

```
… → Engineering Request Classification →
Engineering Engine (DOCUMENT_LOOKUP) →
Document Retrieval (Engineering Index read side) →
Engineering Response (origin = DETERMINISTIC_RETRIEVAL)
```

This matters architecturally: it demonstrates that `EngineeringResponse`
is the pipeline's output contract regardless of *how* an answer was
produced, and that the LLM stages are one execution dependency of one
workflow - not a mandatory stage every engineering answer passes
through.

The LLM Provider Abstraction Layer and LLM Invocation Runtime stages
are deliberately not another `app/domain/**` bounded context - see the
note below the pipeline table. Engineering Response, one stage further,
*is* a genuine `app/domain/**` bounded context again, despite consuming
the LLM Invocation Runtime's own application-layer output - see
[ADR-0015](adr/0015-engineering-response-foundation.md) for how that
Dependency Rule boundary is resolved.

**Milestone 25.1 added the pipeline's first stage on the *input* side.**
Everything before it turned reviewed knowledge into answers; ingestion is
where project knowledge begins to enter the system at all. It deliberately
stops short of extraction: it records that a document was accepted, what
the repository already knows about it, and whether it is ready for a
future extractor - and nothing else. The Engineering Index and the
Knowledge Graph stay untouched, enforced by architecture test rather than
by intent.

**Milestone 30.1 finally assigned meaning - to one association, under
one rule.** Engineering Semantic Interpretation reads constructed facts
and produces `EngineeringSemanticStatement`s from a versioned catalogue
of engineering rules. The statement vocabulary has exactly one member,
`HAS_RATED_POWER`, produced by exactly one rule: a designation
associated with **exactly one** power quantity has that quantity as its
rated power. Deterministic - no LLM, no embeddings, no machine learning,
no probabilistic inference.

Three responsibilities, deliberately separated:

- **Semantic Interpretation assigns engineering meaning.**
- **The Knowledge Graph stores interpreted knowledge.**
- **Reasoning consumes interpreted knowledge.**

This stage is the first of the three, and it stops when the meaning is
assigned. Nothing here writes a node or an edge.

**Voltage was left uninterpreted on purpose.** `HAS_NOMINAL_VOLTAGE`
looks like the obvious second rule and is not: a voltage beside a
designation may be a rated voltage, a test voltage, an insulation level
or the voltage of the busbar the equipment connects to, and the
association alone does not distinguish them. `TR1 20 kV` and `TR1 240
mm²` therefore produce **no statement** - not a failure, an honest
absence. `TR1 20 kV 630 kVA` produces one statement, for the power only.
The catalogue was not widened to give every association a meaning.

**No executable engineering rule exists outside the catalogue**, enforced
by architecture test, because every stored statement cites a rule id and
version and a judgement made elsewhere would be one nobody could find or
review.

**Ambiguity produces no statement.** Two power quantities associated with
one designation yield a diagnostic in its own table and nothing else - a
fact carries entity *keys*, not values, so this stage cannot see whether
the figures agree, and reaching for them would mean depending on
entities. A boundary that forces the conservative answer is a boundary in
the right place.

**Semantic statements own no provenance and carry no value or unit.**
They cite the facts that support them; the fact cites entities, the
entity cites evidence, and the evidence cites the characters on the page.
The figure lives on the quantity entity, where a rated value has exactly
one source of truth.

**Milestone 29.2 associated those objects - and said as little as
possible about the association.** Engineering Fact Construction produces
structured statements between resolved entities under one declared rule:
a designation entity and a quantity entity are associated when
contributing observations of both occur on the **same document line**.
No proximity score, no nearest-neighbour, no geometry, no fuzzy matching,
no thresholds.

**A fact is a structured association, not a classified engineering
property.** The predicate vocabulary has exactly one member,
`HAS_ASSOCIATED_QUANTITY`, and it **does not mean rated power, voltage or
current** - a data sheet listing a *test* voltage beside a designation
produces the same predicate as one listing a rated voltage, because the
line does not say which it is. Promoting a quantity into a role is a
semantic milestone with its own rule and its own evaluation; the
quantity's evidence type stays reachable through the fact's support so
that milestone has what it needs.

**Ambiguous layout must not become a confirmed fact.** `TR1 TR2 630 kVA`
produces nothing - the line does not say which transformer the rating
belongs to, and a guess would put a rating on the wrong equipment.
Declined lines are recorded as diagnostics in their own table, so an
ambiguity is structurally invisible to anyone querying facts.

**Every fact is explainable through its entity and evidence support**:
subject entity, object entity, the observations that put them on one
line, and the rule and version that constructed it - with the
character-level chain still on the evidence, reachable by key rather than
copied. When the Knowledge Graph is eventually populated it must consume
these governed facts rather than reconstructing relationships from text,
or it would be deciding what counts as an association in a second place
under no rule version.

**Milestone 29.1 turned observations into objects - and stopped
there.** Engineering Entity Resolution groups compatible evidence into
entities: designation observations sharing a normalised designation, a
status and an extraction rule version become one
`EQUIPMENT_DESIGNATION`; each quantity observation becomes its own
`ENGINEERING_QUANTITY`. Grouping is by **declared key** - no edit
distance, no embeddings, no similarity score, no model.

**Evidence is an observation; an entity is a deterministic grouping of
observations; graph nodes will later be generated from entities.** Those
are three different things, and the layer exists to keep them apart. An
entity is a *hypothesis*: it follows from a stated rule at a stated
version and can be recomputed at any time. It is not a graph node, and
nothing in this milestone writes one.

What it deliberately does not answer: what an object *is* (no
transformer, breaker, CT, VT, relay or cable classes exist), what it
*does*, what it *belongs to*, or which quantity is whose rating. `630
kVA` beside `TR1` is two entities that do not know about each other -
adjacency is a fact about ink, attribution is a judgement. There is no
field in the model and no column in the schema in which any of that could
be recorded.

Entities **never own provenance; they aggregate it**: each cites the
evidence keys and locations that created it, while the character-level
chain stays on the evidence item, which remains authoritative. No entity
exists without at least one contributing observation.

**Milestone 28.2 made the platform able to measure its own
extraction rules.** Before entity resolution can be built on evidence,
somebody has to be able to say how good that evidence is - and an
extractor cannot grade itself. The Engineering Evidence Evaluation
Framework compares extractor output against a **version-controlled
reference corpus** of documents whose evidence a human wrote down by
hand, classifies every item as a true positive, false positive or false
negative, and computes exact `Decimal` precision, recall and F1 per
corpus, document, evidence type and rule.

**Every new extraction rule must be evaluated against the reference
corpus before it becomes part of the supported deterministic pipeline.**
A rule that has not been measured is a rule nobody knows the cost of: it
may raise recall and quietly halve precision, and the first place that
would surface is an engineer disputing an entity months later.

Only exact matches count, and **provenance is part of the match** - an
observation with the right text in the wrong place is a false positive
*and* a false negative, because a consumer that trusted its location
would be reading the wrong part of the document. Regression reports name
the exact items that changed rather than only the movement, and reports
are insert-only, so the history a comparison needs cannot be overwritten.

Evaluation is a **product capability**, not a test-suite detail: it has
its own API, its own persisted history and its own version. It never
writes engineering evidence, and it reaches no document - a corpus is
self-contained in the repository, which is what lets an evaluation run in
CI and mean the same thing next year.

**Milestone 28.1 added the first governed consumer of canonical
text.** Engineering Evidence Extraction runs a small, versioned catalogue
of deterministic rules over the segmentation and records what was
*observed*: designations, voltages, currents, powers and cable sections,
each with provenance back to the exact characters, tokens, line,
paragraph and page that produced it, and each citing the rule and rule
version that matched.

**An evidence item is an observation, not an entity.** It says `20 kV`
appeared at a place; it does not say a transformer exists, nor which one.
A quantity beside a designation is *two independent observations* -
adjacency is a fact about ink, attribution is a judgement - and there is
no field on the model and no column in the schema in which "belongs to"
could be written. Entity resolution, equipment records, technical
properties and graph population are later milestones that consume
evidence through `EngineeringEvidenceRepository`; when they arrive, graph
population must read evidence rather than document text, or it would be
re-deciding what counts as an observation under no rule version.

No LLM, no embeddings, no inference beyond the declared patterns. The
live Knowledge Graph upload path still performs ad-hoc LLM extraction and
remains recorded debt; an architecture test pins the current absence of a
dependency between the two, so migrating it will be a deliberate act.

**Milestone 26.2 made the canonical path the only path.** Until then
the pipeline drawn above described how documents *should* be read, while
the upload endpoint quietly did something else: it opened the stored PDF
with PyMuPDF and handed the result straight to the Knowledge Graph. Three
further modules could decode a PDF as well. All four are now deleted, the
upload runs the consolidated pipeline through a single application
workflow, and the Knowledge Graph receives text assembled from the
segmentation.

**Exactly one module in this system may import a PDF library**, and an
architecture test asserts that the set has precisely one member. That is
what makes the reproducibility argument in the two milestones below
actually hold - a second decoder would have quietly reintroduced every
problem they were built to prevent.

**Milestone 27.1 turned that artefact into the structure extraction
actually consumes.** The Canonical Text Segmentation maps the
representation onto `document → section → paragraph → line → token`,
using only boundaries the parser already observed - page transitions,
block boundaries, the line index preserved on every span, and whitespace.
A section **is a page**: not a chapter, not a heading, not an engineering
section, because those would have to be inferred and inferring them is
what this milestone refuses to do.

**Every semantic extractor consumes the segmentation rather than PDF
layout.** A block, a bounding box and a font size are facts about ink on
a page; "these lines form a paragraph" is a conclusion drawn from them.
If each extractor drew that conclusion itself, each would draw it
slightly differently, and two extractors disagreeing about where a
paragraph ends would produce two irreconcilable answers about one
document. Deciding it once, recording it, and versioning it under
`segmentation_version` means a rule change produces a new segmentation
beside the old one, and every conclusion drawn under the previous rules
stays explainable. Tokens also carry the full provenance chain -
`document → page → block → span → character range` - so an extractor can
point at the exact characters behind anything it claims; an extractor
starting from geometry would have to carry that chain itself, and the
first one to drop it would break the property the whole system depends
on.

**Milestone 26.1 built the artefact everything downstream will
read.** The canonical representation is the first thing in this system
that records what a document *says* - page by page, block by block, span
by span, with geometry and font style, exactly as the parser observed it.
It records and does not interpret: no merged paragraphs, no inferred
tables or sections, no engineering entities, no re-ordering of blocks,
and nowhere in the model or the schema to put any of them.

**Every future semantic extraction consumes the representation, never the
original PDF.** The PDF stays authoritative as a document; it stops being
the thing software parses. Re-decoding it later, under a different
library version, could legitimately yield different text - which would
mean a claim in the Knowledge Graph could silently stop being supported
by the document it came from, with nothing able to show what changed. The
representation is instead a fixed value bound to one checksum, one parser
version and one representation version, so "where did this claim come
from?" resolves to a specific span of a specific representation of
specific bytes. Confining PDF decoding to one adapter behind one port
also means every downstream milestone inherits *resolved* failures -
encrypted, corrupted, no extractable text - rather than handling them
again. `CanonicalRepresentationRepository` deliberately exposes no method
returning a path, a handle or raw content, so the rule is structural
rather than advisory.

**Milestone 25.2 gave that stage eyes, and only just enough of them.**
Document Identity establishes two deterministic facts about a document's
bytes - which bytes they are (SHA-256, size, accessibility) and what kind
of file they form (signature > declared MIME type > filename extension) -
and stops there. Reading at most 32 leading bytes and a streamed digest
identifies a file; it does not read a document. There is still no
parsing, no OCR, no embeddings, no LLM and no knowledge write anywhere on
the input side, and the same architecture tests now cover the new context
too. The line between *identifying* a document and *understanding* one is
the line this milestone deliberately did not cross.

Each stage trusts the stage before it completely and adds exactly one
new responsibility — no stage re-derives or second-guesses a decision
an earlier stage already made (this is the same discipline
[ADR-0007](adr/0007-project-knowledge-graph-persistence.md) names
explicitly for Graph Builder → Project Knowledge Graph, extended here
across the whole pipeline).

| Stage | Bounded context | Owns | Domain package |
|---|---|---|---|
| Documents | Document Repository | Uploaded files, scope (`PROJECT` vs `CANONICAL_LIBRARY`), and - since Milestone 25.2 - the format classified at upload rather than defaulted to `other` | `app/models/document.py`, `app/routers/documents.py` |
| Document Identity | Document Identity | Deterministic content identity (SHA-256, size, accessibility) and format classification from evidence ranked signature > declared MIME type > filename extension, behind the read-only `DocumentContentPort` (Milestone 25.2). The **one** format rule source in the system, used by upload, ingestion and the backfill alike. Identity is not deduplication: identical checksums are recorded and nothing is concluded from them | `app/domain/document_identity/**` (domain), `app/services/document_identity_service.py` |
| Document Ingestion | Document Ingestion | The deterministic lifecycle a document passes through on its way to being extractable (Milestone 25.1): an explicit `UPLOADED → QUEUED → PROCESSING → PROCESSED/FAILED` state machine with validated transitions, one typed immutable `IngestionJob` per attempt, a document-metadata snapshot taken at ingestion time, and a persisted `READY_FOR_EXTRACTION`/`FAILED` outcome a future extraction milestone consumes. Since Milestone 25.2 the snapshot also carries the content identity and classified format resolved through Document Identity, each content and format failure named rather than collapsed. **Orchestration only** - it interprets no document contents, uses no LLM, and writes neither the Engineering Index nor the Knowledge Graph | `app/domain/document_ingestion/**` (domain), `app/services/document_ingestion_service.py` |
| Canonical PDF Representation | Canonical PDF | The deterministic, reproducible textual representation of a PDF (Milestone 26.1): `CanonicalPdfDocument → Page → Block → Span`, with page number, the parser's own reading order, verbatim text, bounding boxes, font family and size, and bold/italic - bound to one content checksum, one parser version and one representation version. **The single source of truth for every future semantic extraction**, which consumes it through `CanonicalRepresentationRepository` and never re-opens the original PDF. Records what the parser observed and interprets nothing: no merged paragraphs, no inferred tables, lists, headings or sections, no entities, no OCR | `app/domain/canonical_pdf/**` (domain), `app/services/canonical_pdf_service.py` |
| Canonical Text Segmentation | Canonical Text | The semantic-neutral textual structure over the representation (Milestone 27.1): `CanonicalTextDocument → Section → Paragraph → Line → Token`, where a section **is a page**, a paragraph **is a PDF block** and a line **is a PDF line** - only boundaries the parser observed. Tokens carry the original text, a deterministic NFKC normalisation, their position in the line, and the full provenance chain back to the originating span's characters. **The structure every future extractor consumes**, through `CanonicalTextRepository`, which exposes no PDF structure at all. Assigns no engineering meaning: no entities, no equipment, no cables, no tables, no relationships | `app/domain/canonical_text/**` (domain), `app/services/canonical_text_service.py` |
| Engineering Evidence Extraction | Engineering Evidence | Deterministic engineering observation over canonical text (Milestone 28.1): `EngineeringEvidenceSet → EngineeringEvidence`, covering designations, voltages, currents, powers and cable sections under a versioned rule catalogue with one pattern source and one unit catalogue. Quantities are held as exact `Decimal`; every item carries provenance to the characters, tokens, line, paragraph and page that produced it, plus its rule id and version. **Observations only** - no entity, no relationship, no equipment type, no LLM, and no column in which any of them could be recorded | `app/domain/engineering_evidence/**` (domain), `app/services/engineering_evidence_service.py` |
| ~~Knowledge Graph ingestion (legacy consumer)~~ | — | **Retired by EPIC 31.1.** The per-project LLM entity extraction the upload endpoint fed. It wrote unreviewed extraction into the queryable graph on every upload - the ADR-0004 violation ADR-0009 quarantined. Upload now runs **no downstream consumer at all**; knowledge enters the graph only through governed promotion. Deleted with it: `entity_extractor`, `topology/**` and the second LLM client in `services/ai/**`. See [ADR-0025](adr/0025-retire-the-legacy-knowledge-graph.md) | *(deleted)* |
| Engineering Evidence Evaluation | Engineering Evidence Evaluation | The permanent framework that measures extraction quality (Milestone 28.2): a version-controlled `ReferenceCorpus` of hand-annotated documents, exact-match classification into `TRUE_POSITIVE` / `FALSE_POSITIVE` / `FALSE_NEGATIVE` **including provenance**, exact `Decimal` precision/recall/F1 per corpus, document, evidence type and rule, and regression detection that names the exact items that changed between two rule versions. Reports are insert-only; corpora are immutable at runtime. It never writes engineering evidence and reaches no document | `app/domain/evidence_evaluation/**` (domain, incl. `corpora/*.yaml`), `app/services/evidence_evaluation_service.py` |
| Engineering Entity Resolution | Engineering Entities | Deterministic grouping of evidence into entities (Milestone 29.1): `EngineeringEntitySet → EngineeringEntity`, covering `EQUIPMENT_DESIGNATION` and `ENGINEERING_QUANTITY` under a versioned rule catalogue. Identity is a SHA-256 over document, evidence source, rule and version, so the same evidence always resolves the same way and a rule bump creates a new set rather than a rewrite. Entities aggregate their evidence's provenance and can enumerate the observations that created them. **Groupings only** - no relationship, no topology, no equipment classification, no LLM, and no Knowledge Graph or Engineering Index write | `app/domain/engineering_entities/**` (domain), `app/services/engineering_entity_service.py` |
| Engineering Fact Construction | Engineering Facts | Deterministic structured associations between resolved entities (Milestone 29.2): `EngineeringFactSet → EngineeringFact`, under one rule (`same_line_association`) and one closed predicate (`HAS_ASSOCIATED_QUANTITY`) that deliberately asserts no property role. Declared cardinality policy: one designation may associate with many quantities on a line; two or more designations produce **no fact** and a diagnostic in a separate table. Facts aggregate support from subject entity, object entity and contributing evidence, and reference entities by deterministic key so fact history survives a newer entity set. **Associations only** - no classification, no topology, no LLM, no proximity scoring, no Knowledge Graph or Engineering Index write | `app/domain/engineering_facts/**` (domain), `app/services/engineering_fact_service.py` |
| Engineering Semantic Interpretation | Engineering Semantics | Deterministic assignment of engineering meaning to constructed facts (Milestone 30.1): `EngineeringSemanticSet → EngineeringSemanticStatement`, from a versioned rule catalogue that is the **only** place an executable engineering rule may live. One statement type (`HAS_RATED_POWER`) from one rule: a designation associated with exactly one power quantity has that quantity as its rated power. Voltage, current and cable section are deliberately left uninterpreted - the association does not say whether a voltage is rated, test, insulation or busbar. Two candidate powers produce **no statement** and a diagnostic in a separate table. Statements own no provenance, carry no value or unit, and cite the facts supporting them by key. **Meaning only** - no LLM, no embeddings, no machine learning, no probabilistic inference, no reasoning, no Knowledge Graph or Engineering Index write | `app/domain/engineering_semantics/**` (domain), `app/services/engineering_semantic_service.py` |
| Engineering Index | Engineering Index | A structured, per-document index of extracted content — not yet a claim about the installation. Its **read side** (Document Retrieval, Milestone 23B.1) answers "which documents mention X?" as ranked `DocumentReference`s, scored from a fixed documented weight table | `app/domain/engineering_index/**` (domain), `app/services/document_retrieval_service.py` |
| Proposed Claims | Proposed Claims | Candidate assertions derived from the index, not yet reviewed | `app/domain/proposed_claims/**` |
| Review Workflow | Review Workflow | Human review/approval state for a Proposed Claim | `app/domain/review_workflow/**` |
| Canonicalization | Canonicalization | Normalizes an **approved** claim into a `CanonicalFact` against the Canonical Domain vocabulary | `app/domain/canonicalization/**` |
| Governed Human Review | Human Review | Append-only engineering judgement over a semantic statement: a decision, a reason, a reviewer, a support fingerprint. The **only** thing that authorises knowledge into the graph | `app/domain/human_review/**` |
| Governed Knowledge Graph | Governed Knowledge Graph | The one runtime engineering knowledge graph - a rebuildable projection of semantic statements whose current review is `APPROVED` and applicable. Mandatory provenance on every node and edge; no property bag, no confidence score | `app/domain/governed_knowledge_graph/**`, [knowledge_graph.md](knowledge_graph.md) |
| Governed Structured Retrieval | Governed Retrieval | Five typed queries over the governed graph, matched against typed governed fields through documented deterministic folds. Ranks by **match strategy**, never by a score; preserves `NO_MATCH`/`UNIQUE_MATCH`/`MULTIPLE_MATCHES`; reads through a port with no write method | `app/domain/governed_retrieval/**`, [governed_structured_retrieval.md](governed_structured_retrieval.md) |
| ~~Graph Builder / Project Knowledge Graph / Graph Query / Structured Retrieval~~ | — | **Retired, EPIC 31.4.** The Canonical Facts graph-shaped projection and the retrieval over it. See [ADR-0028](adr/0028-retire-the-canonical-facts-graph.md); the historical behaviour is preserved in [structured_retrieval.md](structured_retrieval.md) | *deleted* |
| Governed Context Assembly | Context Builder | A bounded, provenance-aware, budget-enforced `ContextPackage` assembled from `GovernedRetrievalResult`s (EPIC 31.3) - selection, aggregation, coverage, budget, warnings, statistics, metadata. Every item wraps a governed result, so provenance is structurally mandatory, ambiguity survives per query, and ordering carries no score. Also a `ComparisonContextPackage`: **two whole `ContextPackage`s**, each assembled from its own governed results, paired under named left/right fields and never merged - computing a difference is the comparison's answer, not its input | `app/domain/context_builder/**`, [governed_context_assembly.md](governed_context_assembly.md) |
| Prompt Builder | Prompt Builder | A deterministic, provider-independent `PromptPackage` composed from a `ContextPackage` - fixed-order sections, versioned constraints/instructions, token estimates, statistics, self-validation. Since Milestone 23B.2 a `PromptObjective` (`DIRECT_ANSWER` / `ENGINEERING_EXPLANATION` / `ENGINEERING_VERIFICATION`) selects between fixed, versioned instruction and expected-output sets; truthfulness constraints never vary by objective, and no free-form or caller-supplied prompt text is ever accepted. Owns the closed verdict and comparison-outcome vocabularies an answer must declare (Milestones 24.1, 24.2) - the only machine-readable tokens this system asks a model for - and the `LEFT_KNOWLEDGE`/`RIGHT_KNOWLEDGE` sections that keep a comparison's two evidence groups typed apart | `app/domain/prompt_builder/**` |
| LLM Provider Abstraction Layer | *(application/infrastructure capability, not a bounded context)* | A provider-neutral `LLMRequest` mapped from a `PromptPackage`, translated by a provider adapter (Anthropic first) into a local, never-sent prepared request - no invocation, no provider SDK dependency in the application layer | `app/application/**` (contracts, mapper, registry, service), `app/infrastructure/llm/**` (adapters) |
| LLM Invocation Runtime | *(application/infrastructure capability, not a bounded context)* | Attempt sequencing, total-deadline enforcement, retry decisions, cancellation, and provider-neutral response normalization for exactly one real provider call per invocation | `app/application/services/llm_runtime.py`, `app/application/policies/**`, `app/application/validation/**` (runtime), `app/infrastructure/llm/anthropic/**` (invoker, error mapper, response mapper) |
| Engineering Response | Engineering Response | A structured, traceable `EngineeringResponse` - typed sections, structured warnings, uncertainty declarations, preserved evidence/version provenance - deterministically normalized from an `LLMResponseEnvelope`, never AI-interpreted. Since Milestone 23B.1 it also composes `DETERMINISTIC_RETRIEVAL` responses, built entirely from repository state with no provider named anywhere. Since Milestone 24.1 it reads a verification's declared verdict from the answer's first line - the one narrow, declared-protocol exception to "no semantic parsing of provider text" - and structurally overrides it to `INSUFFICIENT_EVIDENCE` when no evidence was retrieved; Milestone 24.2 applies the same device to a comparison outcome, overridden when **either** side retrieved nothing | `app/domain/engineering_response/**` (domain), `app/services/engineering_response_service.py` (the one translation seam) |
| Engineering Session | Engineering Session | The root aggregate for one engineering work session - project identity, session state, an ordered history of `EngineeringResponse`s, an append-only timeline, statistics, version metadata; owns no conversation/chat/memory/tools/agents yet | `app/domain/engineering_session/**` (domain), `app/services/engineering_session_service.py` |
| Conversation | Conversation | Structured engineering dialogue belonging to an `EngineeringSession` (referenced, never embedded) - ordered Turns owning ordered Messages and `EngineeringResponse` references; Turn, not Message, is the primary conversational unit; no memory/tools/agents yet | `app/domain/conversation/**` (domain), `app/services/conversation_service.py` |
| Working Memory | Working Memory | The temporary, deterministic engineering context needed to continue reasoning - open questions, recent `EngineeringResponse`s, their references/assumptions/constraints, all structurally derived, never AI-edited, never persisted, always rebuildable | `app/domain/working_memory/**` (domain), `app/services/working_memory_service.py` |
| Engineering Request Classification | Engineering Intent | Deterministic, rule-based classification of one explicit request into a small workflow taxonomy, with first-class evidence, categorical confidence, and ambiguity as a valid result; no LLM, no embeddings, no semantic model; depends on no other bounded context | `app/domain/engineering_intent/**` (domain), `app/services/engineering_intent_service.py` |
| Classification-to-Retrieval Bridge | Retrieval Bridge | Deterministic mapping from a classified request to the typed retrieval criteria the engine requires - designation extraction by fixed token shape, resolution against Canonicalization's own vocabulary, and an immutable intent→retrieval policy table; produces a typed unresolved result rather than broadening retrieval when evidence is insufficient or conflicting; executes nothing, and depends on the Engineering Engine not at all | `app/domain/retrieval_bridge/**` (domain), `app/services/engineering_request_preparation_service.py` |
| Engineering Engine | *(application coordination capability; its planning models are a small domain package)* | Registry-driven workflow selection, explicit deterministic `WorkflowPlan`s, step-handler execution with first-failure stop, typed failures, an append-only execution timeline, and explicit (never applied) aggregate update proposals - `KNOWLEDGE_QUERY` (23A), `DOCUMENT_LOOKUP` (23B.1), `ENGINEERING_EXPLANATION` (23B.2) and `ENGINEERING_VERIFICATION` (24.1, the first reasoning workflow) and `ENGINEERING_COMPARISON` (24.2, the first with two subjects and two independent retrievals), each added by declaration and registration alone with no change to engine decision logic; the engine evaluates and compares nothing itself | `app/domain/engineering_engine/**` (planning models), `app/services/engineering_engine/**` (registries, handlers, executor, service, composition root) |

**Note on the two LLM rows:** unlike every other stage in this table,
the LLM Provider Abstraction Layer and the LLM Invocation Runtime are
intentionally not implemented as new `app/domain/**` bounded contexts
(Milestone 16's own instruction, reaffirmed unchanged by Milestone 17:
"do not create a new engineering bounded context merely to hold
external provider details"). Provider selection, request shaping, and
now invocation lifecycle management are an application/infrastructure
concern, not new engineering domain knowledge about substations - see
[ADR-0013](adr/0013-llm-provider-abstraction-layer.md),
[llm_provider_abstraction.md](llm_provider_abstraction.md),
[ADR-0014](adr/0014-llm-invocation-runtime.md), and
[llm_invocation_runtime.md](llm_invocation_runtime.md).

## Required conceptual distinction

```
CanonicalFact = normalized approved engineering assertion (a source record; feeds no graph since EPIC 31.4)
SemanticStatement = deterministic engineering meaning assigned to a fact by a versioned rule
Review = append-only engineering judgement over a semantic statement
Governed Knowledge Graph = the one runtime engineering knowledge graph, a rebuildable projection of approved statements
Governed Structured Retrieval = typed, deterministic, provenance-preserving retrieval over the governed graph
Governed Context Assembly = bounded, provenance-aware context assembly over GovernedRetrievalResults
Prompt Builder = deterministic, provider-independent prompt-composition layer over a ContextPackage
LLM Provider Abstraction Layer = provider-neutral request contract + first (Anthropic) adapter over a PromptPackage - request preparation only, no invocation
LLM Invocation Runtime = attempt/retry/deadline/cancellation-governed execution of exactly one real provider call, behind the same LLMProviderPort - implemented, disabled by default, never exercised with a real provider in the automated test suite
Engineering Response = the canonical, domain-owned, provider-neutral representation of an AI answer - typed sections, structured warnings, uncertainty, preserved evidence - deterministically normalized from an LLMResponseEnvelope, never AI-interpreted
Engineering Session = the root aggregate for one engineering work session - owns project identity, session state, an ordered history of EngineeringResponses, a timeline, statistics, and version metadata; not a chat, owns no conversation/memory/tools/agents yet
Conversation = structured engineering dialogue belonging to an EngineeringSession - ordered Turns (the primary conversational unit, not Messages) owning ordered Messages and EngineeringResponse references; no memory/tools/agents yet
Working Memory = the temporary, deterministic engineering context needed to continue reasoning during a session - not conversation history, not project knowledge, always rebuildable, never AI-edited
Engineering Request Classification = deterministic, rule-based routing of one explicit request into a workflow category - request classification, never psychological intent detection; a classification result, never an executable command
Engineering Engine = the application coordinator that selects, plans and executes one engineering workflow - deterministic workflow structure, not an agent, an LLM brain, a reasoning engine or an orchestrator of agents; KNOWLEDGE_QUERY only today
Semantic Retrieval = future retrieval and ranking layer
AI Assistant = future consumer, not owner, of engineering truth
```

Semantic Retrieval and the AI Assistant are **not implemented**. No
code in this repository performs embedding, vector search, semantic
ranking, or natural-language query interpretation today — every read
in Graph Query is a deterministic, exact query (by id, by type, by
attribute presence, by 1-hop adjacency); Structured Retrieval
(Milestone 13) adds only deterministic, structured-criteria matching
and a fixed, documented scoring policy on top of it; Context Builder
(Milestone 14) adds only deterministic selection, budget enforcement,
and coverage/warning reporting on top of that; Prompt Builder
(Milestone 15) adds only deterministic section composition, a fixed
constraint/instruction policy, and an approximate, provider-independent
token estimate on top of that; the LLM Provider Abstraction Layer
(Milestone 16) adds only deterministic request translation and a
capability-declaring provider adapter on top of that; and the LLM
Invocation Runtime (Milestone 17) adds a governed execution path
(attempt sequencing, total-deadline enforcement, retry policy,
cancellation, response normalization) capable of a real Anthropic call
— but that path is **disabled by default**
(`LLM_RUNTIME_ENABLED=false`), and no automated test in this repository
ever calls a real provider: every test exercises either the fake
adapter or a mocked/monkeypatched Anthropic client; Engineering
Response (Milestone 18) adds only a deterministic normalization of an
already-produced `LLMResponseEnvelope` into a structured
`EngineeringResponse` (typed sections, structured warnings, uncertainty
declarations derived from structural signals) on top of that - still no
AI usage of its own, no semantic parsing of the provider's own prose;
Engineering Session (Milestone 19) adds only a deterministic root
aggregate owning a session's state, its ordered `EngineeringResponse`
history, and an append-only timeline on top of that; Conversation
(Milestone 20) adds only a deterministic Turn/Message hierarchy
referencing `EngineeringResponse`s produced during a session on top of
that; Working Memory (Milestone 21) adds only a deterministic,
structurally-derived bounded view over a conversation's open question
and recent responses on top of that; Engineering Request
Classification (Milestone 22) adds only a deterministic, rule-based
routing decision over one explicit request's own normalized text on top
of that; and the Engineering Engine (Milestone 23A) adds only
deterministic coordination of the already-existing components into one
explicit, auditable workflow execution - still no memory, tool
execution, agents, task decomposition, semantic summarization, or
autonomous behaviour of any kind (see
[structured_retrieval.md](structured_retrieval.md),
[context_builder.md](context_builder.md),
[prompt_builder.md](prompt_builder.md),
[llm_provider_abstraction.md](llm_provider_abstraction.md),
[llm_invocation_runtime.md](llm_invocation_runtime.md),
[engineering_response.md](engineering_response.md),
[engineering_session.md](engineering_session.md),
[conversation.md](conversation.md),
[working_memory.md](working_memory.md),
[engineering_intent.md](engineering_intent.md),
[engineering_engine.md](engineering_engine.md),
[ADR-0010](adr/0010-structured-retrieval-foundation.md),
[ADR-0011](adr/0011-context-builder-foundation.md),
[ADR-0012](adr/0012-prompt-builder-foundation.md),
[ADR-0013](adr/0013-llm-provider-abstraction-layer.md),
[ADR-0014](adr/0014-llm-invocation-runtime.md),
[ADR-0015](adr/0015-engineering-response-foundation.md),
[ADR-0016](adr/0016-engineering-session-foundation.md),
[ADR-0017](adr/0017-conversation-foundation.md),
[ADR-0018](adr/0018-working-memory-foundation.md),
[ADR-0019](adr/0019-engineering-request-classification.md),
[ADR-0020](adr/0020-engineering-engine-foundation.md)). Describing
Semantic Retrieval or the AI Assistant as existing would misrepresent
the system; they are named here only to mark where a future milestone
(the AI Assistant, per the Product Development Plan) will attach, and
to make clear that when it arrives, it consumes Working Memory's own
bounded view and Engineering Request Classification's own routing
result — it does not gain its own path to
engineering truth, and Anthropic remains one configurable adapter
rather than the platform's identity.

## Bounded-context dependency direction

Enforced by `tests/architecture/test_bounded_context_dependencies.py`,
a lightweight, repository-native check (Python's `ast` module — no
framework dependency added) that parses every file under
`app/domain/**` and asserts it imports only from the domain contexts
its own position in the pipeline is allowed to depend on:

```
project               (foundation - depends on nothing)
engineering_index      -> project
proposed_claims        -> project, engineering_index
review_workflow        -> project, proposed_claims
canonicalization        -> project, proposed_claims, review_workflow
graph_builder           -> project, canonicalization, proposed_claims
project_knowledge_graph -> project, graph_builder
graph_query             -> project, graph_builder
structured_retrieval    -> project, graph_builder, graph_query
context_builder         -> project, structured_retrieval
prompt_builder          -> project, context_builder, structured_retrieval
```

`app/application/**` (the LLM Provider Abstraction Layer, Milestone 16)
is not part of this table at all - it sits outside `app/domain/**` by
design (see the pipeline table's note above) and is governed by its
own, separate architecture tests
(`tests/architecture/test_llm_provider_boundaries.py`) rather than the
domain dependency-order table below.

`graph_builder`'s dependency on `proposed_claims` (in addition to
`canonicalization`, which is already downstream of `proposed_claims`)
is not a backward dependency: it is legitimate reuse of the single
shared `ClaimType` vocabulary type. `ClaimType` is defined once in
Proposed Claims, carried unchanged onto `CanonicalFact.claim_type` by
Canonicalization, and inspected again by Graph Builder's
`GraphOperationFactory.from_canonical_fact` to decide whether a fact
produces an EXISTENCE, ATTRIBUTE, or RELATIONSHIP operation — the same
"shared, stable type reused across contexts" pattern
`GraphEntityId`/`GraphRelationshipType` already use across Graph
Builder, Project Knowledge Graph, and Graph Query. The dependency-graph
test's own table documents this reasoning inline.

Two further architecture tests guard the two boundaries most at risk
of erosion:

- `test_graph_query_never_imports_graph_store` — Graph Query reads the
  Project Knowledge Graph through its **own** read port
  (`GraphQueryRepository`), never through `GraphStore` (the write-side
  port only Graph Persistence's execution service uses). A downstream
  read context reaching backward into an upstream context's private
  write infrastructure would be exactly the kind of boundary violation
  ADR-0002 and ADR-0007 both guard against.
- `test_governed_graph_path_does_not_import_legacy_knowledge_graph_code`
  — no file under Graph Builder, Project Knowledge Graph, or Graph
  Query imports anything from the legacy Knowledge Graph modules (see
  [ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md)). The
  governed and legacy graph paths must never merge.

Two more, added in Milestone 13, guard Structured Retrieval's own
boundaries: `test_structured_retrieval_domain_does_not_import_forbidden_modules`
(no SQLAlchemy, no `GraphStore`, no legacy Knowledge Graph modules, no
Proposed Claims/Review Workflow) and
`test_structured_retrieval_surface_has_no_ai_or_vector_dependency` (no
`anthropic`, `openai`, or `app.services.ai` import anywhere in the
domain, service, or router files) — the codified form of ADR-0010's
"deterministic first, no AI provider" decision.

Two more, added in Milestone 14, guard Context Builder's own
boundaries the same way: `test_context_builder_does_not_import_forbidden_modules`
(no SQLAlchemy, no `GraphStore`, no Graph Query read port/service/router,
no Structured Retrieval *service or router* - its domain models are the
one allowed, shared-vocabulary exception - no legacy Knowledge Graph
modules, no Proposed Claims/Review Workflow) and
`test_context_builder_surface_has_no_ai_or_vector_dependency` (no
`anthropic`, `openai`, or `app.services.ai` import anywhere in the
domain, service, or router files) — the codified form of ADR-0011's
"assembly only, no retrieval, no AI" decision.

Two more, added in Milestone 15, guard Prompt Builder's own boundaries
the same way: `test_prompt_builder_does_not_import_forbidden_modules`
(no SQLAlchemy, no `GraphStore`, no Graph Query read port/service/router,
no Structured Retrieval *or* Context Builder service/router - their
domain models are the one allowed, shared-vocabulary exception - no
legacy Knowledge Graph modules, no Proposed Claims/Review Workflow) and
`test_prompt_builder_surface_has_no_ai_or_provider_dependency` (no
`anthropic`, `openai`, `app.services.ai`, `ollama`, or `azure` import
anywhere in the domain, service, or router files) — the codified form
of ADR-0012's "composition only, no serialization, no provider SDK"
decision.

Milestone 16 adds a dedicated file,
`tests/architecture/test_llm_provider_boundaries.py`, rather than
extending the bounded-context dependency table above (the LLM Provider
Abstraction Layer is not a domain bounded context - see the pipeline
table's note). It enforces: the provider-neutral contract surface
(`app/application/ports/**` + `app/application/models/**`) and the
whole `app/application/**` tree import no provider SDK (`anthropic`,
`openai`, `azure`, `ollama`), no HTTP client (`requests`, `httpx`), no
SQLAlchemy, and no Graph Query/Structured Retrieval/Context
Builder/Prompt Builder *service or router* (`test_application_contracts_do_not_import_forbidden_modules`,
`test_application_llm_layer_does_not_import_forbidden_modules`); the
Anthropic adapter (`app/infrastructure/llm/anthropic/**`) imports
nothing from the `anthropic` package itself, no knowledge-graph/
retrieval/canonicalization internals, no engineering domain service, no
persistence repository, and no HTTP router
(`test_anthropic_adapter_does_not_import_forbidden_modules`,
`test_anthropic_adapter_module_never_imports_the_anthropic_sdk`); and
the fake test adapter carries no provider or network dependency of its
own (`test_fake_adapter_has_no_provider_or_network_dependency`) - the
codified form of ADR-0013's "Anthropic is an adapter, never a domain
dependency" decision.

Milestone 17 extends the same file rather than adding a new one, since
invocation is the same non-bounded-context capability, not a new
architectural surface. Milestone 16's narrow
`test_anthropic_adapter_module_never_imports_the_anthropic_sdk` is
replaced by a positive-confinement test,
`test_anthropic_sdk_is_confined_to_the_anthropic_adapter_package`,
because invocation legitimately requires the `anthropic`/`httpx`
imports Milestone 16 had forbidden: it scans every file under `app/`
and asserts that only `app/infrastructure/llm/anthropic/**` may import
`anthropic` or `httpx` — everything else in the tree, including
`app/application/**` itself, must not. The carve-out this test used to
grant the legacy `app/services/ai/**` is gone with that package, retired
by EPIC 31.1. This is the codified form of
ADR-0014's "the SDK is confined to the Anthropic adapter package, and
the runtime owns retry, not the SDK" decision.

Milestone 18 adds `engineering_response` to `ALLOWED_DOMAIN_DEPENDENCIES`
above (`{"project", "context_builder", "prompt_builder",
"structured_retrieval"}`; Milestone 23B.1 adds `"engineering_index"`,
because a document-lookup response's evidence *is* a `DocumentReference` -
the same downstream-depends-on-upstream shared-vocabulary reuse, since
Engineering Index sits upstream of Engineering Response in the order
above) and a dedicated boundary section in the same
file: `test_engineering_response_domain_does_not_import_forbidden_modules`
(no SQLAlchemy, no graph ports, no legacy Knowledge Graph path, no
Proposed Claims/Review Workflow, no Structured Retrieval/Context
Builder/Prompt Builder *service or router*, and - this milestone's own
new guarantee - no `app.application.**` of any kind, no provider SDK,
no LLM Invocation Runtime module),
`test_engineering_response_surface_has_no_ai_or_provider_dependency`
(no `anthropic`/`openai`/`app.services.ai`/`ollama`/`azure`), and the
explicit, narrowly-scoped
`test_engineering_response_domain_never_imports_the_application_layer` -
the codified form of ADR-0015's central architectural claim: this
domain context consumes an application-layer artifact's *content*
(via its own domain-owned restatement, built once in
`app/services/engineering_response_service.py`) without ever importing
the application layer itself.

Milestone 19 adds `engineering_session` to `ALLOWED_DOMAIN_DEPENDENCIES`
(`{"engineering_response"}` - the smallest dependency set of any
context in this pipeline) and its own dedicated boundary section:
`test_engineering_session_does_not_import_forbidden_modules` (no
SQLAlchemy, no graph ports, no legacy Knowledge Graph path, no Proposed
Claims/Review Workflow, no sibling *service or router* modules
including Engineering Response's own, no `app.application.**`, no
provider SDK, no LLM Invocation Runtime module),
`test_engineering_session_surface_has_no_ai_or_provider_dependency`,
and `test_engineering_session_domain_never_imports_the_application_layer`
- the last with **no exceptions anywhere**, unlike Engineering
Response's own equivalent test, since Engineering Session has no
application-layer input to translate in the first place (see
ADR-0016).

Milestone 20 adds `conversation` to `ALLOWED_DOMAIN_DEPENDENCIES`
(`{"engineering_session", "engineering_response"}`) and its own
dedicated boundary section: `test_conversation_does_not_import_forbidden_modules`,
`test_conversation_surface_has_no_ai_or_provider_dependency`, and
`test_conversation_domain_never_imports_the_application_layer` - again
with no exceptions anywhere, the same guarantee Engineering Session's
own equivalent test establishes (see ADR-0017).

Milestone 21 adds `working_memory` to `ALLOWED_DOMAIN_DEPENDENCIES`
(`{"conversation", "engineering_session", "engineering_response"}`) and
its own dedicated boundary section:
`test_working_memory_does_not_import_forbidden_modules`,
`test_working_memory_surface_has_no_ai_or_provider_dependency`, and
`test_working_memory_domain_never_imports_the_application_layer` -
again with no exceptions anywhere (see ADR-0018).

Milestone 22 adds `engineering_intent` to `ALLOWED_DOMAIN_DEPENDENCIES`
as an **empty** set - the smallest dependency surface in the pipeline -
plus its own boundary section:
`test_engineering_intent_does_not_import_forbidden_modules`,
`test_engineering_intent_surface_has_no_ai_or_provider_dependency`
(which also forbids `numpy`/`sklearn`/`torch`/`transformers`/`spacy`/
`faiss`/`tiktoken` and similar, not merely provider SDKs - the codified
form of ADR-0019's "deterministic rule engine, not an LLM classifier"
decision), and
`test_engineering_intent_domain_imports_no_other_bounded_context`.

Milestone 23A adds `engineering_engine` to
`ALLOWED_DOMAIN_DEPENDENCIES` (`{"engineering_intent",
"engineering_response"}`) plus a dedicated file,
`tests/architecture/test_engineering_engine_boundaries.py`, enforcing
both the engine's layering (its domain imports no router, schema,
FastAPI, persistence adapter, provider SDK, or application service) and
- uniquely - that **the engine core never branches over
`EngineeringIntentType`**: `test_engine_core_never_branches_over_intent_types`
parses the actual AST for comparisons and `match` statements against
intent-type members rather than grepping for the word "if", and
`test_the_engine_core_service_does_not_import_concrete_workflows`
proves a new workflow can be registered without touching the core
(see ADR-0020).

Milestone 23B.1 turned that proof from a claim into a demonstration by
registering `DOCUMENT_LOOKUP`, and hardened the same file with the
standing guarantees a future workflow must not erode: the engine core
imports no workflow definition, no concrete handler module and no
bounded context a single workflow happens to need; no core module
mentions a workflow by name anywhere in its source; `composition.py` is
the only place that registers a workflow; the executor and handler
registry depend on the `step_handler.py` contract rather than on any
concrete handler module; the document-lookup handlers can reach no
provider SDK, provider registry, runtime, prompt builder or context
builder; and the whole Document Retrieval surface (domain, adapter,
service) carries no AI, embedding or vector-store dependency at all.

Milestone 23B.3 adds `retrieval_bridge` to `ALLOWED_DOMAIN_DEPENDENCIES`
(`{"engineering_intent", "canonicalization", "structured_retrieval"}` -
all upstream of it) plus a dedicated file,
`tests/architecture/test_retrieval_bridge_boundaries.py`, enforcing three
things the bridge could plausibly grow into and must not: that it cannot
reach a provider SDK, the LLM Runtime, Prompt Builder or Context Builder
(so its determinism is verifiable, not merely intended); that it cannot
reach Engineering Engine internals or any workflow handler module, **and
that the engine cannot reach it** - the dependency runs one way only, an
engine that could call the bridge being an engine that parses natural
language; and that it executes no retrieval of its own. The same file
also proves the intent→retrieval mapping is an immutable table rather
than a branch chain, by the same AST check the engine's own
no-intent-branching test uses.

Milestone 24.2 added four more, covering the first workflow whose
pipeline differs: no engine module names a comparison outcome, the
assessment type, or any finding literal; the engine imports neither the
comparison reader nor the preparation policy; comparison prompt
instructions exist only in Prompt Builder; and **provider adapters and
the runtime remain unaware of comparison semantics** - they map sections
to messages and know nothing of left, right, or what a comparison is.

Milestone 24.1 added two more to the same file:
`test_no_verification_logic_lives_inside_the_engine` (no engine module
names a verification outcome, the assessment type, or any verdict
literal - matched on whole words, since the engine legitimately has its
own unrelated `UNSUPPORTED_INTENT`) and
`test_the_verdict_vocabulary_has_exactly_one_definition` (Engineering
Response imports Prompt Builder's tokens rather than restating them, so
the question asked and the answer read cannot drift). The first reasoning
workflow put its reasoning in the two contexts that own it, and the
coordinator gained none.

Milestone 23B.2 added one more standing guarantee to the same file:
`test_no_handler_derives_its_behaviour_from_an_intent_or_workflow_type`.
Handlers adapt to services; they must not branch over which workflow is
running. A workflow that needs a shared step to behave differently - as
`ENGINEERING_EXPLANATION` does for its Prompt Builder objective - says so
declaratively in the composition root, rather than reintroducing inside a
handler the intent switch the registry exists to remove.

## Public vocabulary boundary: entity types (Graph Query ↔ Canonicalization)

`GraphQueryValidator.validate_entity_type` can confirm an entity-type
string is *syntactically* well-formed, but cannot confirm it is a
*real, registered* entity type — Canonicalization's entity-type
registry (`_ENTITY_TYPE_REGISTRY`) is a private, underscore-prefixed
module constant, and Graph Query has no port onto it. In practice this
means a query for a syntactically valid but nonexistent entity type
(e.g. `"WIDGET"`) returns an empty result rather than a "not a real
entity type" error.

**Decision (Milestone 12, Workstream 5): retain the current syntactic
validation and document this boundary, rather than introduce a new
shared public vocabulary contract.** Two options were considered:

- **Option A — retain + document (chosen).** No new export from
  Canonicalization, no new shared module. The limitation is real but
  low-severity (an empty result set, not a wrong or misleading one),
  and no concrete defect has been demonstrated — only a documented
  gap. This matches Milestone 12's own Change Discipline ("before
  changing existing domain behavior: identify the concrete defect")
  and its general hardening-minimalism bias: the more conservative,
  lower-risk choice is preferred when no defect forces a bigger one.
- **Option B — introduce a genuinely shared public canonical
  vocabulary contract.** Rejected for this milestone: this would mean
  designing a new public export surface from Canonicalization (e.g. a
  `KnownEntityTypes` port both Canonicalization and Graph Query depend
  on) — real design work with real coupling consequences, not a
  hardening-sized change, and explicitly the kind of "expand/redesign
  the ontology this milestone" Workstream 5 forbids. It remains
  available as clearly-scoped future work if a real need (not just a
  theoretical gap) ever appears — e.g. if Graph Query needs to reject
  invalid entity-type queries with a specific error rather than an
  empty result.

## What still bypasses this pipeline

**Nothing writes engineering knowledge outside it any more.**

Until EPIC 31.1, `app/services/knowledge_graph.py::ingest_document` ran
on every document upload and wrote LLM-extracted entities straight into
the queryable graph with no review gate - the violation
[ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md) recorded
at Architecture Freeze v1.0 and
[ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md) quarantined.

That path is **deleted**: the service, its router, its schemas, its two
tables and the extractors behind it. Uploading a document now stores,
identifies and canonicalises it and does nothing else - the pipeline's
downstream consumer is `None`, and an architecture test asserts it.

Knowledge reaches the graph only by an explicit, capability-gated
promotion of a statement an engineer approved. See
[ADR-0025](adr/0025-retire-the-legacy-knowledge-graph.md).

One graph implementation remains alongside the governed one: the
Canonical Facts lineage (`graph_builder`, `project_knowledge_graph`,
`graph_query`), which Structured Retrieval and the Engineering Engine
read. It is retained deliberately and documented in
[knowledge_graph.md](knowledge_graph.md) §2, which also states what
retiring it would require.

## Inspecting the pipeline's output

The pipeline's stages are read by two different UIs, answering two
different questions:

- **Pipeline UI** (`/documents/{id}/pipeline`) — did each stage run, what
  did it produce, was an artefact re-used, under which policy versions.
- **Engineering Workspace** (`/documents/{id}/workspace`) — what does the
  platform claim about this document, and what supports each claim, all
  the way back to the line it was read from.

The Workspace makes the support chain navigable in both directions:

```
Semantic Statement → Fact → Entity → Evidence → Canonical Source Location
```

It is a **projection**, not a second engine. Every relationship it shows
comes from a key an artefact declares, and it creates no engineering
knowledge, no support relationship and no source location of its own. It
is also inspection-only: nothing in it approves, edits or overrides an
artefact, because no Human Review bounded context exists yet.

See [engineering_workspace.md](engineering_workspace.md) and
[ADR-0021](adr/0021-engineering-workspace-document-viewer.md).

## Engineering judgement is not pipeline output

Since EPIC 30.4 an engineer can record a governed decision about an
interpreted statement:

```
Document → Pipeline → Semantic Statement → Human Review → Engineering Decision
```

**Human Review never becomes part of the pipeline.** It reads pipeline
output; the pipeline does not read it, and an architecture test fails if
any engineering domain module imports the review context. Running a stage
twice under two different reviewers produces byte-identical artefacts,
exactly as it did before reviews existed - and an API test asserts the
semantic set compares equal before and after a review is recorded.

Two properties keep the separation honest:

- **A review references an artefact by key and never contains one.**
  There is no field in that context into which a statement, fact, entity
  or piece of evidence could be copied.
- **A review survives a pipeline re-run without ever being carried onto a
  differently-derived statement.** `statement_key` is a deterministic
  hash of the document, the fact source and the rule versions, so an
  identical re-run reproduces the same key and any change produces a new
  one. A judgement whose statement is gone is marked
  `requires_revalidation` - never discarded, and never silently moved.

The future Knowledge Graph will consume **deterministic semantics plus
governed review decisions**; neither replaces the other. Nothing of the
graph is implemented yet.

See [human_review.md](human_review.md) and
[ADR-0023](adr/0023-human-review-append-only-judgement.md).

## Governed knowledge: the query model

Since EPIC 31 approved engineering judgement reaches a queryable model:

```
Document → Pipeline → Semantic Statement → Human Review → Governed Knowledge Graph
```

**The graph is a projection, and never the source of truth.** It consumes
exactly one thing - a semantic statement whose current review is
`APPROVED` and whose applicability is `APPLIES` - and it may always be
dropped and rebuilt from the pipeline and the reviews. Rejected
statements, inconclusive ones, judgements awaiting revalidation and
orphaned reviews never become graph knowledge.

This is the first implementation that satisfies
[ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md), which has
recorded since Architecture Freeze v1.0 that only reviewed facts may
enter a queryable graph and that the legacy path did not comply.

Three properties keep the separation honest:

- **Derived.** Nothing originates in the graph, and the pipeline never
  learns it is projected - an architecture test fails if any engineering
  domain module imports the graph context.
- **Rebuildable.** Identities are hashes of governed keys and
  `created_at` comes from the authorising review, so the projection is a
  pure function of the statements and the reviews. Tests assert that a
  rebuild reproduces identical content.
- **Explainable.** Every node and edge carries the statement, the review,
  the reviewer, the rule and policy versions and the support fingerprint,
  and cannot be constructed without them. There is no confidence score
  anywhere.

**Three graph implementations now coexist**, fed from two different
lineages. `knowledge_graph.md` §2 states the relationship and recommends
how the older two retire; this milestone touched neither.

See [knowledge_graph.md](knowledge_graph.md),
[promotion_rules.md](promotion_rules.md) and
[ADR-0024](adr/0024-governed-knowledge-graph-as-projection.md).

## Where to look for more detail

- **Vision and roadmap:** `project_intelligence_architecture.md`.
- **Persistence/execution semantics:** [ADR-0007](adr/0007-project-knowledge-graph-persistence.md).
- **Transaction ownership:** [repository_transaction_conventions.md](repository_transaction_conventions.md).
- **Migrations:** [ADR-0008](adr/0008-database-migration-governance.md), [database_migrations.md](database_migrations.md).
- **Legacy retirement:** [ADR-0025](adr/0025-retire-the-legacy-knowledge-graph.md); the isolation it discharged is [ADR-0009](adr/0009-legacy-knowledge-graph-isolation.md).
- **Engineering Workspace:** [engineering_workspace.md](engineering_workspace.md), [ADR-0021](adr/0021-engineering-workspace-document-viewer.md).
- **Human Review:** [human_review.md](human_review.md), [ADR-0023](adr/0023-human-review-append-only-judgement.md).
- **Governed Knowledge Graph:** [knowledge_graph.md](knowledge_graph.md), [promotion_rules.md](promotion_rules.md), [ADR-0024](adr/0024-governed-knowledge-graph-as-projection.md).
- **Performance baseline:** [performance_baseline.md](performance_baseline.md).
- **Startup/health/config:** [operational_reliability.md](operational_reliability.md).
- **Governed Structured Retrieval:** [governed_structured_retrieval.md](governed_structured_retrieval.md), [ADR-0026](adr/0026-governed-structured-retrieval.md) - the Engineering Engine's retrieval since EPIC 31.2.
- **Structured Retrieval (Canonical Facts):** [structured_retrieval.md](structured_retrieval.md), [ADR-0010](adr/0010-structured-retrieval-foundation.md) - still served by its own endpoints, no longer read by the engine.
- **Context Builder:** [context_builder.md](context_builder.md), [ADR-0011](adr/0011-context-builder-foundation.md).
- **Prompt Builder:** [prompt_builder.md](prompt_builder.md), [ADR-0012](adr/0012-prompt-builder-foundation.md).
- **LLM Provider Abstraction Layer:** [llm_provider_abstraction.md](llm_provider_abstraction.md), [ADR-0013](adr/0013-llm-provider-abstraction-layer.md).
- **LLM Invocation Runtime:** [llm_invocation_runtime.md](llm_invocation_runtime.md), [ADR-0014](adr/0014-llm-invocation-runtime.md).
- **Engineering Response:** [engineering_response.md](engineering_response.md), [ADR-0015](adr/0015-engineering-response-foundation.md).
- **Engineering Session:** [engineering_session.md](engineering_session.md), [ADR-0016](adr/0016-engineering-session-foundation.md).
- **Conversation:** [conversation.md](conversation.md), [ADR-0017](adr/0017-conversation-foundation.md).
- **Working Memory:** [working_memory.md](working_memory.md), [ADR-0018](adr/0018-working-memory-foundation.md).
- **Engineering Request Classification:** [engineering_intent.md](engineering_intent.md), [ADR-0019](adr/0019-engineering-request-classification.md).
- **Documents, Document Identity, Document Ingestion, the Canonical PDF Representation and the Canonical Text Segmentation:** [document_management.md](document_management.md).
- **Engineering Evidence Extraction and its Evaluation Framework:** [engineering_evidence.md](engineering_evidence.md).
- **Engineering Entity Resolution:** [engineering_entities.md](engineering_entities.md).
- **Engineering Fact Construction:** [engineering_facts.md](engineering_facts.md).
- **Engineering Semantic Interpretation:** [engineering_semantics.md](engineering_semantics.md).
- **Classification-to-Retrieval Bridge:** [retrieval_bridge.md](retrieval_bridge.md) (no ADR of its own - it applies ADR-0019 and ADR-0020 rather than departing from either).
- **Engineering Engine:** [engineering_engine.md](engineering_engine.md), [ADR-0020](adr/0020-engineering-engine-foundation.md).
