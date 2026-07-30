"use client";

/**
 * The artefact views. One per stage, each rendering exactly what the
 * backend returned and nothing derived from it.
 *
 * Quantities are printed as the strings they arrive as: the backend
 * serialises `Decimal` to JSON strings so a rated voltage cannot pick up
 * a rounding error, and parsing them into a JS number here would undo
 * that on the last hop.
 */

import type {
  CanonicalText,
  EntitySet,
  EvidenceSet,
  FactSet,
  SemanticSet,
} from "@/lib/contracts";
import {
  ENTITY_TYPE_LABELS,
  EVIDENCE_TYPE_LABELS,
  FACT_AMBIGUITY_LABELS,
  FACT_PREDICATE_LABELS,
  SEMANTIC_AMBIGUITY_LABELS,
  SEMANTIC_STATEMENT_LABELS,
} from "@/lib/contracts";

function Table({
  headers,
  children,
}: {
  headers: string[];
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-slate-50 text-slate-700">
          <tr>
            {headers.map((header) => (
              <th key={header} className="p-3 text-left font-semibold">
                {header}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Key({ value }: { value: string }) {
  return (
    <span
      title={value}
      className="font-mono text-xs text-slate-500"
    >
      {value.slice(0, 10)}…
    </span>
  );
}

function Location({
  page,
  paragraph,
  line,
}: {
  page: number;
  paragraph: number;
  line: number;
}) {
  return (
    <span className="whitespace-nowrap text-xs text-slate-500">
      p.{page} · par.{paragraph} · riga {line}
    </span>
  );
}

export function CanonicalTextInspector({
  text,
}: {
  text: CanonicalText;
}) {
  const paragraphs = text.sections.flatMap((section) =>
    section.paragraphs.map((paragraph) => ({
      section: section.section_index,
      page: section.page_number,
      paragraph,
    })),
  );

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {text.section_count} sezioni · {text.token_count} token. Una
        sezione <strong>è</strong> una pagina, un paragrafo{" "}
        <strong>è</strong> un blocco del parser: solo confini realmente
        osservati.
      </p>

      <Table headers={["Posizione", "Righe", "Testo"]}>
        {paragraphs.slice(0, 100).map((entry) => (
          <tr
            key={`${entry.section}-${entry.paragraph.paragraph_index}`}
            className="border-t border-slate-100 align-top"
          >
            <td className="p-3">
              <span className="whitespace-nowrap text-xs text-slate-500">
                p.{entry.page} · par.
                {entry.paragraph.paragraph_index}
              </span>
            </td>

            <td className="p-3 text-slate-600">
              {entry.paragraph.lines.length}
            </td>

            <td className="p-3 text-slate-800">
              {entry.paragraph.lines
                .map((line) =>
                  line.tokens.map((token) => token.text).join(" "),
                )
                .join(" ⏎ ")}
            </td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export function EvidenceInspector({ set }: { set: EvidenceSet }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {set.evidence_count} osservazioni sotto la policy di estrazione{" "}
        <span className="font-mono">
          {set.extraction_policy_version}
        </span>
        . Ogni riga dichiara la regola che l&apos;ha prodotta e il punto
        esatto del documento da cui proviene.
      </p>

      <Table
        headers={[
          "Tipo",
          "Testo osservato",
          "Valore",
          "Regola",
          "Provenienza",
          "Stato",
        ]}
      >
        {set.evidence.map((item) => (
          <tr
            key={item.evidence_key}
            className="border-t border-slate-100 align-top"
          >
            <td className="p-3 font-medium text-slate-900">
              {EVIDENCE_TYPE_LABELS[item.evidence_type]}
            </td>

            <td className="p-3 text-slate-800">{item.observed_text}</td>

            <td className="p-3 font-mono text-slate-700">
              {item.quantity
                ? `${item.quantity.value} ${item.quantity.unit}`
                : (item.designation?.normalized ?? "—")}
            </td>

            <td className="p-3 text-xs text-slate-500">
              {item.rule_id} {item.rule_version}
            </td>

            <td className="p-3">
              <Location
                page={item.provenance.page_number}
                paragraph={item.provenance.paragraph_index}
                line={item.provenance.line_index}
              />
            </td>

            <td className="p-3 text-slate-600">{item.status}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export function EntityInspector({ set }: { set: EntitySet }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {set.entity_count} entità sotto la policy di risoluzione{" "}
        <span className="font-mono">
          {set.resolution_policy_version}
        </span>
        . Un&apos;entità è un raggruppamento deterministico di
        osservazioni: non è ancora un nodo del grafo.
      </p>

      <Table
        headers={[
          "Entità",
          "Tipo",
          "Valore",
          "Osservazioni",
          "Regola",
          "Stato",
          "Chiave",
        ]}
      >
        {set.entities.map((entity) => (
          <tr
            key={entity.entity_key}
            className="border-t border-slate-100 align-top"
          >
            <td className="p-3 font-medium text-slate-900">
              {entity.label}
            </td>

            <td className="p-3 text-slate-600">
              {ENTITY_TYPE_LABELS[entity.entity_type]}
            </td>

            <td className="p-3 font-mono text-slate-700">
              {entity.quantity
                ? `${entity.quantity.value} ${entity.quantity.unit}`
                : (entity.designation?.normalized ?? "—")}
            </td>

            <td className="p-3 text-slate-600">
              {entity.evidence_count}
            </td>

            <td className="p-3 text-xs text-slate-500">
              {entity.resolution_rule_id} {entity.resolution_rule_version}
            </td>

            <td className="p-3 text-slate-600">{entity.status}</td>

            <td className="p-3">
              <Key value={entity.entity_key} />
            </td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export function FactInspector({
  set,
  entityLabels,
}: {
  set: FactSet;
  entityLabels: Map<string, string>;
}) {
  const name = (key: string) => entityLabels.get(key) ?? key.slice(0, 10);

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        {set.fact_count} associazioni sotto la policy{" "}
        <span className="font-mono">{set.fact_policy_version}</span>. Un
        fatto dice che due entità soddisfano una regola strutturale
        dichiarata — <strong>non</strong> che una è la proprietà nominale
        dell&apos;altra.
      </p>

      <Table
        headers={["Soggetto", "Predicato", "Oggetto", "Supporto", "Stato"]}
      >
        {set.facts.map((fact) => (
          <tr
            key={fact.fact_key}
            className="border-t border-slate-100 align-top"
          >
            <td className="p-3 font-medium text-slate-900">
              {name(fact.subject_entity_key)}
            </td>

            <td className="p-3 text-slate-600">
              {FACT_PREDICATE_LABELS[fact.predicate]}
            </td>

            <td className="p-3 font-mono text-slate-800">
              {name(fact.object_entity_key)}
            </td>

            <td className="p-3">
              <ul className="space-y-1">
                {fact.support.map((support) => (
                  <li
                    key={`${support.evidence_key}-${support.role}`}
                    className="text-xs text-slate-500"
                  >
                    <span className="font-semibold">{support.role}</span>{" "}
                    “{support.observed_text}”{" "}
                    <Location
                      page={support.page_number}
                      paragraph={support.paragraph_index}
                      line={support.line_index}
                    />
                  </li>
                ))}
              </ul>
            </td>

            <td className="p-3 text-slate-600">{fact.status}</td>
          </tr>
        ))}
      </Table>

      {set.diagnostics.length > 0 && (
        <section>
          <h4 className="text-sm font-semibold text-foreground">
            Righe rifiutate ({set.diagnostics.length})
          </h4>

          <p className="mt-1 text-sm text-muted-foreground">
            Una riga che le regole rifiutano è le regole che funzionano:
            nessun fatto viene inventato.
          </p>

          <ul className="mt-3 space-y-2">
            {set.diagnostics.map((diagnostic, index) => (
              <li
                key={index}
                className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
              >
                {FACT_AMBIGUITY_LABELS[diagnostic.reason]}{" "}
                <Location
                  page={diagnostic.page_number}
                  paragraph={diagnostic.paragraph_index}
                  line={diagnostic.line_index}
                />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function SemanticInspector({
  set,
  entityLabels,
}: {
  set: SemanticSet;
  entityLabels: Map<string, string>;
}) {
  const name = (key: string) => entityLabels.get(key) ?? key.slice(0, 10);

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        {set.statement_count} affermazioni sotto la policy semantica{" "}
        <span className="font-mono">
          {set.semantic_policy_version}
        </span>
        . Un&apos;affermazione non porta valore né unità: la cifra resta
        sull&apos;entità grandezza, dove ha una sola fonte di verità.
      </p>

      <Table
        headers={[
          "Soggetto",
          "Significato",
          "Oggetto",
          "Regola",
          "Stato",
          "Fatti citati",
        ]}
      >
        {set.statements.map((statement) => (
          <tr
            key={statement.statement_key}
            className="border-t border-slate-100 align-top"
          >
            <td className="p-3 font-medium text-slate-900">
              {name(statement.subject_entity_key)}
            </td>

            <td className="p-3 text-slate-700">
              {SEMANTIC_STATEMENT_LABELS[statement.statement_type]}
            </td>

            <td className="p-3 font-mono text-slate-800">
              {name(statement.object_entity_key)}
            </td>

            <td className="p-3 text-xs text-slate-500">
              {statement.semantic_rule_id} {statement.semantic_rule_version}
            </td>

            <td className="p-3 text-slate-600">{statement.status}</td>

            <td className="p-3">
              <ul className="space-y-1">
                {statement.supporting_fact_keys.map((key) => (
                  <li key={key}>
                    <Key value={key} />
                  </li>
                ))}
              </ul>
            </td>
          </tr>
        ))}
      </Table>

      {set.diagnostics.length > 0 && (
        <section>
          <h4 className="text-sm font-semibold text-foreground">
            Soggetti non interpretati ({set.diagnostics.length})
          </h4>

          <ul className="mt-3 space-y-2">
            {set.diagnostics.map((diagnostic) => (
              <li
                key={diagnostic.subject_entity_key}
                className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
              >
                <strong>{name(diagnostic.subject_entity_key)}</strong> —{" "}
                {SEMANTIC_AMBIGUITY_LABELS[diagnostic.reason]}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
