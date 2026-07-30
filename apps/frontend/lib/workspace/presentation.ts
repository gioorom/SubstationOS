/**
 * How a governed state is shown, and nothing more.
 *
 * Everything in this module is a **label attached to a value the backend
 * produced**. No mapping here changes what a value means, and none of
 * them is ever the only carrier of a distinction: the canonical
 * predicate, status and key stay on screen next to their description, so
 * an engineer reads the artefact and the explanation together.
 *
 * Two rules the copy in this file obeys:
 *
 * 1. **`interpreted` does not mean approved.** It means a versioned rule
 *    produced this statement. No human has confirmed it, and this
 *    milestone has no way for one to. The wording says so.
 * 2. **A structural association is not engineering meaning.**
 *    `HAS_ASSOCIATED_QUANTITY` says two entities appeared together on a
 *    line. It is never described as a rated value.
 */

import type {
  EntityStatus,
  EvidenceStatus,
  FactPredicate,
  FactStatus,
  SemanticStatementStatus,
  SemanticStatementType,
} from "@/lib/contracts";

/**
 * The visual vocabulary. Six states, each meaning one thing.
 *
 * `interpreted` is deliberately **not** green: green reads as approval,
 * and nothing in this milestone has been approved by anyone.
 */
export type ArtefactTone =
  | "interpreted"
  | "ambiguous"
  | "declined"
  | "empty"
  | "unrun"
  | "failed"
  | "reused";

export const TONE_CLASSES: Record<ArtefactTone, string> = {
  interpreted: "border-sky-300 bg-sky-50 text-sky-900",
  ambiguous: "border-amber-300 bg-amber-50 text-amber-900",
  declined: "border-violet-300 bg-violet-50 text-violet-900",
  empty: "border-slate-300 bg-slate-50 text-slate-700",
  unrun: "border-slate-200 bg-white text-slate-500",
  failed: "border-red-300 bg-red-50 text-red-800",
  reused: "border-teal-300 bg-teal-50 text-teal-900",
};

/**
 * A shape per tone, so the six states are distinguishable without
 * colour. Rendered as text next to the label, not as an icon-only cue.
 */
export const TONE_MARKS: Record<ArtefactTone, string> = {
  interpreted: "◆",
  ambiguous: "◇",
  declined: "⊘",
  empty: "○",
  unrun: "·",
  failed: "✕",
  reused: "↺",
};

export const TONE_LABELS: Record<ArtefactTone, string> = {
  interpreted: "Interpretato",
  ambiguous: "Ambiguo",
  declined: "Declinato",
  empty: "Vuoto",
  unrun: "Non eseguito",
  failed: "Fallito",
  reused: "Riutilizzato",
};

/** What each state means, in the terms the pipeline defines them. */
export const TONE_DESCRIPTIONS: Record<ArtefactTone, string> = {
  interpreted:
    "Prodotto da una regola deterministica e versionata. Non significa approvato da un ingegnere: in questo milestone nessuna validazione umana esiste.",
  ambiguous:
    "L'artefatto esiste e porta con sé un'ambiguità dichiarata a monte. Non è un rifiuto.",
  declined:
    "La regola è stata valutata e ha deliberatamente prodotto nulla. È il sistema che funziona, non un errore.",
  empty:
    "Lo stage ha prodotto un insieme valido con zero artefatti. È una risposta, non un fallimento.",
  unrun:
    "Lo stage non ha ancora prodotto nulla. Assenza di esecuzione, non assenza di risultati.",
  failed:
    "La lettura o l'esecuzione è fallita. Ciò che esiste a monte resta sconosciuto.",
  reused:
    "Nessun artefatto è stato creato: quello che questi byte avevano già è stato riutilizzato.",
};

export const EVIDENCE_STATUS_TONES: Record<EvidenceStatus, ArtefactTone> = {
  observed: "interpreted",
  ambiguous: "ambiguous",
  rejected: "declined",
};

export const ENTITY_STATUS_TONES: Record<EntityStatus, ArtefactTone> = {
  resolved: "interpreted",
  ambiguous: "ambiguous",
};

export const FACT_STATUS_TONES: Record<FactStatus, ArtefactTone> = {
  constructed: "interpreted",
  ambiguous: "ambiguous",
};

export const SEMANTIC_STATUS_TONES: Record<
  SemanticStatementStatus,
  ArtefactTone
> = {
  interpreted: "interpreted",
  ambiguous: "ambiguous",
};

/**
 * What a predicate asserts, spelled out.
 *
 * This accompanies the canonical predicate; it never replaces it. The
 * wording for `has_associated_quantity` is the whole reason this map
 * exists: an association is structural, and calling it a rated value
 * would put an engineering claim on screen that no rule has made.
 */
export const PREDICATE_DESCRIPTIONS: Record<FactPredicate, string> = {
  has_associated_quantity:
    "Associazione strutturale: le due entità compaiono sulla stessa riga sotto una regola dichiarata. Non dice che la grandezza sia la potenza, la tensione o la corrente nominale del soggetto.",
};

export const STATEMENT_TYPE_DESCRIPTIONS: Record<
  SemanticStatementType,
  string
> = {
  has_rated_power:
    "Una regola versionata mappa un'associazione con una grandezza di potenza sulla potenza nominale del soggetto. Il valore resta sull'entità grandezza referenziata.",
};

/** `TR1` rather than `entity-7f3a…` where the entity set was loaded. */
export function entityLabel(
  labels: ReadonlyMap<string, string>,
  entityKey: string,
): string {
  return labels.get(entityKey) ?? entityKey;
}
