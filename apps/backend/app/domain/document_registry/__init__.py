"""
The Document Registry: what documents this installation holds, and how
one of them is found.

Until this milestone there was **no Document bounded context at all**.
Documents existed only as ORM rows, which routers serialised straight
onto the wire - so `file_path`, a server-side storage location, was a
public API field, and every list read the whole table. Both facts were
found by the frontend integration audit (EPIC 30.1.2).

This context owns the registry read model: which documents exist, what
an engineer may know about one, and the governed queries by which a
caller reaches them. It deliberately does **not** own:

- document *content* - that is `document_identity`'s two ports, and the
  only route to bytes;
- document *meaning* - evidence, entities, facts and semantics each have
  their own context and consume the canonical pipeline, not this one;
- ingestion *lifecycle* - `document_ingestion` owns that state machine.

The one rule that shapes everything here: **where a document's bytes are
stored is private backend state.** No value object in this context has a
field for it, so no schema built from one can leak it.
"""
