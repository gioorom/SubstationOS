"use client";

import type {
  EngineeringEntity,
  EngineeringEvidence,
  EngineeringFact,
  SemanticStatement,
} from "@/lib/contracts";
import {
  ENTITY_TYPE_LABELS,
  EVIDENCE_TYPE_LABELS,
  FACT_PREDICATE_LABELS,
  SEMANTIC_STATEMENT_LABELS,
} from "@/lib/contracts";
import {
  buildSupportChain,
  describeLocation,
  ENTITY_STATUS_TONES,
  entityLabel,
  EVIDENCE_STATUS_TONES,
  FACT_STATUS_TONES,
  locationOfProvenance,
  PREDICATE_DESCRIPTIONS,
  resolveStatementQuantity,
  SEMANTIC_STATUS_TONES,
  STATEMENT_TYPE_DESCRIPTIONS,
  type Selection,
  type SelectionKind,
  type WorkspaceDiagnostic,
  type WorkspaceIndex,
} from "@/lib/workspace";

import ChainStep from "./ChainStep";
import InspectorField from "./InspectorField";
import StateBadge from "./StateBadge";

interface InspectorPanelProps {
  selection: Selection | null;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}

/**
 * The selected artefact, its identity, and what supports it.
 *
 * The Inspector is where the canonical form of everything stays visible:
 * keys, rule identifiers, policy versions and the backend's own status
 * words. The explorers can afford a readable label; this panel may not
 * substitute one, because it is the panel an engineer opens when the
 * readable label is exactly what they have stopped trusting.
 *
 * It offers no action that writes. Inspecting, navigating and copying an
 * identifier are the whole of it - see `docs/architecture/
 * engineering_workspace.md` on why a Human Review bounded context, not a
 * button, is what an approval would require.
 */
export default function InspectorPanel({
  selection,
  index,
  entityLabels,
  onSelect,
}: InspectorPanelProps) {
  return (
    <section
      aria-label="Ispettore"
      className="flex min-h-0 flex-col rounded-3xl border border-slate-200 bg-white/80"
    >
      <header className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Ispettore</h2>

        <p className="mt-0.5 text-xs text-muted-foreground">
          Identità, regola, versione e catena di supporto dell&apos;artefatto
          selezionato.
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-auto px-4 py-3">
        <InspectorBody
          selection={selection}
          index={index}
          entityLabels={entityLabels}
          onSelect={onSelect}
        />
      </div>
    </section>
  );
}

function InspectorBody({
  selection,
  index,
  entityLabels,
  onSelect,
}: InspectorPanelProps) {
  if (selection === null) {
    return (
      <p className="text-sm leading-6 text-muted-foreground">
        Nessun artefatto selezionato. Scegli un&apos;affermazione, un
        fatto, un&apos;entità, un&apos;evidenza o una diagnostica per
        vederne l&apos;identità completa e risalire alla riga di origine.
      </p>
    );
  }

  const artefact = lookup(index, selection);

  if (artefact === null) {
    return (
      <div role="alert" className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3">
        <p className="text-sm font-medium text-amber-900">
          Nessun artefatto corrisponde a questa selezione.
        </p>

        <p className="mt-1 font-mono text-xs break-all text-amber-900">
          {selection.kind}: {selection.key}
        </p>

        <p className="mt-2 text-sm leading-6 text-amber-800">
          La chiave non esiste in questo documento, oppure lo stage che la
          produce non è stato eseguito. Nessuna corrispondenza approssimata
          viene tentata.
        </p>
      </div>
    );
  }

  switch (selection.kind) {
    case "evidence":
      return (
        <EvidenceDetail
          evidence={artefact as EngineeringEvidence}
          index={index}
          entityLabels={entityLabels}
          onSelect={onSelect}
        />
      );

    case "entity":
      return (
        <EntityDetail
          entity={artefact as EngineeringEntity}
          index={index}
          entityLabels={entityLabels}
          onSelect={onSelect}
        />
      );

    case "fact":
      return (
        <FactDetail
          fact={artefact as EngineeringFact}
          index={index}
          entityLabels={entityLabels}
          onSelect={onSelect}
        />
      );

    case "semantic":
      return (
        <SemanticDetail
          statement={artefact as SemanticStatement}
          index={index}
          entityLabels={entityLabels}
          onSelect={onSelect}
        />
      );

    case "diagnostic":
      return (
        <DiagnosticDetail
          diagnostic={artefact as WorkspaceDiagnostic}
          index={index}
          entityLabels={entityLabels}
          onSelect={onSelect}
        />
      );
  }
}

/** A lookup in an index already loaded - never a request. */
function lookup(index: WorkspaceIndex, selection: Selection): unknown {
  switch (selection.kind) {
    case "evidence":
      return index.evidenceByKey.get(selection.key) ?? null;
    case "entity":
      return index.entitiesByKey.get(selection.key) ?? null;
    case "fact":
      return index.factsByKey.get(selection.key) ?? null;
    case "semantic":
      return index.semanticsByKey.get(selection.key) ?? null;
    case "diagnostic":
      return index.diagnosticsByKey.get(selection.key) ?? null;
  }
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h3>
  );
}

// --- Evidence ------------------------------------------------------------

function EvidenceDetail({
  evidence,
  index,
  entityLabels,
  onSelect,
}: {
  evidence: EngineeringEvidence;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}) {
  const location = locationOfProvenance(
    index.documentId,
    evidence.provenance,
  );

  const entityKeys = index.entityKeysByEvidence.get(
    evidence.evidence_key,
  ) ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-base font-semibold text-foreground">
          {evidence.observed_text}
        </span>

        <StateBadge
          tone={EVIDENCE_STATUS_TONES[evidence.status]}
          value={evidence.status}
        />
      </div>

      <dl className="mt-4">
        <InspectorField label="Chiave evidenza" copyValue={evidence.evidence_key}>
          <span className="font-mono text-xs break-all">
            {evidence.evidence_key}
          </span>
        </InspectorField>

        <InspectorField label="Tipo">
          {EVIDENCE_TYPE_LABELS[evidence.evidence_type]}{" "}
          <span className="font-mono text-xs text-muted-foreground">
            ({evidence.evidence_type})
          </span>
        </InspectorField>

        <InspectorField label="Regola di estrazione">
          <span className="font-mono text-xs">
            {evidence.rule_id}@{evidence.rule_version}
          </span>
        </InspectorField>

        {evidence.quantity !== null && (
          <InspectorField label="Grandezza normalizzata">
            <span className="font-mono tabular-nums">
              {evidence.quantity.value} {evidence.quantity.unit}
            </span>
            {evidence.quantity.base_value !== null && (
              <span className="ml-2 text-xs text-muted-foreground">
                {`= ${evidence.quantity.base_value} ${evidence.quantity.base_unit}`}
              </span>
            )}
          </InspectorField>
        )}

        {evidence.designation !== null && (
          <InspectorField label="Sigla normalizzata">
            <span className="font-mono">
              {evidence.designation.normalized}
            </span>
          </InspectorField>
        )}

        <InspectorField label="Posizione nel sorgente">
          {describeLocation(location)}
        </InspectorField>

        <InspectorField label="Token">
          <span className="tabular-nums">
            {location.token_start}–{location.token_end}
          </span>
        </InspectorField>

        <InspectorField
          label="Riga canonica"
          copyValue={evidence.provenance.source_text}
        >
          <span className="block rounded-lg bg-slate-50 px-2 py-1 font-mono text-xs leading-5">
            {evidence.provenance.source_text}
          </span>
        </InspectorField>
      </dl>

      <Heading>Entità che la citano</Heading>

      {entityKeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nessuna entità caricata dichiara questa osservazione. La
          risoluzione potrebbe non essere stata eseguita.
        </p>
      ) : (
        <div className="space-y-2">
          {entityKeys.map((key) => (
            <ChainStep
              key={key}
              kind="entity"
              artefactKey={key}
              resolved={index.entitiesByKey.has(key)}
              title={entityLabel(entityLabels, key)}
              detail={key}
              onSelect={() => onSelect("entity", key)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// --- Entity --------------------------------------------------------------

function EntityDetail({
  entity,
  index,
  entityLabels,
  onSelect,
}: {
  entity: EngineeringEntity;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}) {
  const evidenceKeys =
    index.evidenceKeysByEntity.get(entity.entity_key) ?? [];
  const factKeys = index.factKeysByEntity.get(entity.entity_key) ?? [];
  const statementKeys =
    index.semanticKeysByEntity.get(entity.entity_key) ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-base font-semibold text-foreground">
          {entity.label}
        </span>

        <StateBadge
          tone={ENTITY_STATUS_TONES[entity.status]}
          value={entity.status}
        />
      </div>

      <dl className="mt-4">
        <InspectorField label="Chiave entità" copyValue={entity.entity_key}>
          <span className="font-mono text-xs break-all">
            {entity.entity_key}
          </span>
        </InspectorField>

        <InspectorField label="Tipo">
          {ENTITY_TYPE_LABELS[entity.entity_type]}{" "}
          <span className="font-mono text-xs text-muted-foreground">
            ({entity.entity_type})
          </span>
        </InspectorField>

        <InspectorField label="Regola di risoluzione">
          <span className="font-mono text-xs">
            {entity.resolution_rule_id}@{entity.resolution_rule_version}
          </span>
        </InspectorField>

        <InspectorField label="Versione entità">
          <span className="font-mono text-xs">{entity.entity_version}</span>
        </InspectorField>

        {entity.quantity !== null && (
          <InspectorField label="Grandezza">
            <span className="font-mono tabular-nums">
              {entity.quantity.value} {entity.quantity.unit}
            </span>
          </InspectorField>
        )}

        {entity.designation !== null && (
          <InspectorField label="Sigla">
            <span className="font-mono">{entity.designation.normalized}</span>
          </InspectorField>
        )}

        <InspectorField label="Osservazioni dichiarate">
          <span className="tabular-nums">{entity.evidence_count}</span>
        </InspectorField>
      </dl>

      <Heading>Evidenze di supporto</Heading>

      {evidenceKeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          L&apos;entità non elenca osservazioni contribuenti. Nessuna viene
          dedotta confrontando testo o valori.
        </p>
      ) : (
        <div className="space-y-2">
          {evidenceKeys.map((key) => {
            const evidence = index.evidenceByKey.get(key) ?? null;

            return (
              <ChainStep
                key={key}
                kind="evidence"
                artefactKey={key}
                resolved={evidence !== null}
                title={evidence?.observed_text ?? key}
                detail={
                  evidence === null
                    ? undefined
                    : describeLocation(
                        locationOfProvenance(
                          index.documentId,
                          evidence.provenance,
                        ),
                      )
                }
                onSelect={() => onSelect("evidence", key)}
              />
            );
          })}
        </div>
      )}

      <Heading>Fatti che la nominano</Heading>

      {factKeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nessun fatto caricato nomina questa entità.
        </p>
      ) : (
        <div className="space-y-2">
          {factKeys.map((key) => (
            <FactStep
              key={key}
              factKey={key}
              index={index}
              entityLabels={entityLabels}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}

      <Heading>Affermazioni semantiche</Heading>

      {statementKeys.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nessuna affermazione semantica riguarda questa entità. Un
          soggetto senza significato interpretato non ne riceve uno qui.
        </p>
      ) : (
        <div className="space-y-2">
          {statementKeys.map((key) => {
            const statement = index.semanticsByKey.get(key) ?? null;

            return (
              <ChainStep
                key={key}
                kind="semantic"
                artefactKey={key}
                resolved={statement !== null}
                title={
                  statement === null
                    ? key
                    : `${entityLabel(entityLabels, statement.subject_entity_key)} — ${statement.statement_type}`
                }
                onSelect={() => onSelect("semantic", key)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// --- Fact ----------------------------------------------------------------

function FactStep({
  factKey,
  index,
  entityLabels,
  onSelect,
}: {
  factKey: string;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}) {
  const fact = index.factsByKey.get(factKey) ?? null;

  return (
    <ChainStep
      kind="fact"
      artefactKey={factKey}
      resolved={fact !== null}
      title={
        fact === null
          ? factKey
          : `${entityLabel(entityLabels, fact.subject_entity_key)} ${fact.predicate} ${entityLabel(entityLabels, fact.object_entity_key)}`
      }
      detail={
        fact === null ? undefined : FACT_PREDICATE_LABELS[fact.predicate]
      }
      onSelect={() => onSelect("fact", factKey)}
    />
  );
}

function FactDetail({
  fact,
  index,
  entityLabels,
  onSelect,
}: {
  fact: EngineeringFact;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}) {
  const statementKeys = index.semanticKeysByFact.get(fact.fact_key) ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold text-foreground">
          {entityLabel(entityLabels, fact.subject_entity_key)}
        </span>
        <span className="font-mono text-xs uppercase text-sky-700">
          {fact.predicate}
        </span>
        <span className="font-mono text-sm font-semibold text-foreground">
          {entityLabel(entityLabels, fact.object_entity_key)}
        </span>

        <StateBadge
          tone={FACT_STATUS_TONES[fact.status]}
          value={fact.status}
        />
      </div>

      <p className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
        {PREDICATE_DESCRIPTIONS[fact.predicate]}
      </p>

      <dl className="mt-4">
        <InspectorField label="Chiave fatto" copyValue={fact.fact_key}>
          <span className="font-mono text-xs break-all">{fact.fact_key}</span>
        </InspectorField>

        <InspectorField label="Predicato canonico">
          <span className="font-mono">{fact.predicate}</span>
        </InspectorField>

        <InspectorField label="Regola di costruzione">
          <span className="font-mono text-xs">
            {fact.construction_rule_id}@{fact.construction_rule_version}
          </span>
        </InspectorField>

        <InspectorField label="Versione fatto">
          <span className="font-mono text-xs">{fact.fact_version}</span>
        </InspectorField>

        <InspectorField label="Tipi di evidenza a supporto">
          {[...new Set(fact.support.map((item) => item.evidence_type))]
            .map((type) => EVIDENCE_TYPE_LABELS[type])
            .join(", ") || "—"}
        </InspectorField>
      </dl>

      <Heading>Entità referenziate</Heading>

      <div className="space-y-2">
        {(
          [
            ["soggetto", fact.subject_entity_key],
            ["oggetto", fact.object_entity_key],
          ] as const
        ).map(([role, key]) => (
          <ChainStep
            key={key}
            kind="entity"
            artefactKey={key}
            resolved={index.entitiesByKey.has(key)}
            title={`${entityLabel(entityLabels, key)} (${role})`}
            detail={key}
            onSelect={() => onSelect("entity", key)}
          />
        ))}
      </div>

      <Heading>Evidenze di supporto</Heading>

      <div className="space-y-2">
        {fact.support.map((support) => (
          <ChainStep
            key={`${support.evidence_key}-${support.role}`}
            kind="evidence"
            artefactKey={support.evidence_key}
            resolved={index.evidenceByKey.has(support.evidence_key)}
            title={`${support.observed_text} (${support.role})`}
            detail={`p. ${support.page_number} · par. ${support.paragraph_index} · riga ${support.line_index}`}
            onSelect={() => onSelect("evidence", support.evidence_key)}
          />
        ))}
      </div>

      {statementKeys.length > 0 && (
        <>
          <Heading>Affermazioni che lo citano</Heading>

          <div className="space-y-2">
            {statementKeys.map((key) => (
              <ChainStep
                key={key}
                kind="semantic"
                artefactKey={key}
                resolved={index.semanticsByKey.has(key)}
                title={
                  index.semanticsByKey.get(key)?.statement_type ?? key
                }
                onSelect={() => onSelect("semantic", key)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// --- Semantic statement --------------------------------------------------

function SemanticDetail({
  statement,
  index,
  entityLabels,
  onSelect,
}: {
  statement: SemanticStatement;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}) {
  const chain = buildSupportChain(index, statement.statement_key);
  const quantity = resolveStatementQuantity(index, statement);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold text-foreground">
          {entityLabel(entityLabels, statement.subject_entity_key)}
        </span>
        <span className="font-mono text-xs uppercase text-sky-700">
          {statement.statement_type}
        </span>

        <StateBadge
          tone={SEMANTIC_STATUS_TONES[statement.status]}
          value={statement.status}
        />
      </div>

      <p className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
        {STATEMENT_TYPE_DESCRIPTIONS[statement.statement_type]}
      </p>

      {chain.incomplete && (
        <p
          role="alert"
          className="mt-3 rounded-2xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
        >
          Catena di supporto incompleta: {chain.missing.length}{" "}
          riferimento/i non corrisponde ad alcun artefatto caricato.
          L&apos;affermazione è mostrata così com&apos;è, senza colmare il
          vuoto.
        </p>
      )}

      <dl className="mt-4">
        <InspectorField
          label="Chiave affermazione"
          copyValue={statement.statement_key}
        >
          <span className="font-mono text-xs break-all">
            {statement.statement_key}
          </span>
        </InspectorField>

        <InspectorField label="Tipo di affermazione">
          {SEMANTIC_STATEMENT_LABELS[statement.statement_type]}{" "}
          <span className="font-mono text-xs text-muted-foreground">
            ({statement.statement_type})
          </span>
        </InspectorField>

        <InspectorField label="Valore risolto">
          {quantity === null ? (
            <span className="text-amber-800">
              L&apos;entità grandezza referenziata non è caricata: nessun
              valore viene mostrato.
            </span>
          ) : quantity.quantity === null ? (
            <span className="font-mono">{quantity.label}</span>
          ) : (
            <>
              <span className="font-mono tabular-nums">
                {quantity.quantity.value} {quantity.quantity.unit}
              </span>
              <span className="ml-2 text-xs text-muted-foreground">
                letto dall&apos;entità {quantity.entity_key}
              </span>
            </>
          )}
        </InspectorField>

        <InspectorField label="Regola semantica">
          <span className="font-mono text-xs">
            {statement.semantic_rule_id}@{statement.semantic_rule_version}
          </span>
        </InspectorField>

        <InspectorField label="Contratto semantico">
          <span className="font-mono text-xs">
            {statement.semantic_contract_version}
          </span>
        </InspectorField>
      </dl>

      <Heading>Catena di supporto</Heading>

      <ol className="space-y-2">
        {chain.facts.map((factLink) => (
          <li key={factLink.key}>
            <FactStep
              factKey={factLink.key}
              index={index}
              entityLabels={entityLabels}
              onSelect={onSelect}
            />
          </li>
        ))}

        {chain.entities.map((entityLink) => (
          <li key={entityLink.key}>
            <ChainStep
              kind="entity"
              artefactKey={entityLink.key}
              resolved={entityLink.artefact !== null}
              title={entityLink.artefact?.label ?? entityLink.key}
              detail={
                entityLink.artefact === null
                  ? undefined
                  : ENTITY_TYPE_LABELS[entityLink.artefact.entity_type]
              }
              onSelect={() => onSelect("entity", entityLink.key)}
            />
          </li>
        ))}

        {chain.evidence.map((evidenceLink) => (
          <li key={evidenceLink.key}>
            <ChainStep
              kind="evidence"
              artefactKey={evidenceLink.key}
              resolved={evidenceLink.artefact !== null}
              title={evidenceLink.artefact?.observed_text ?? evidenceLink.key}
              detail={
                evidenceLink.artefact === null
                  ? undefined
                  : describeLocation(
                      locationOfProvenance(
                        index.documentId,
                        evidenceLink.artefact.provenance,
                      ),
                    )
              }
              onSelect={() => onSelect("evidence", evidenceLink.key)}
            />
          </li>
        ))}
      </ol>
    </div>
  );
}

// --- Diagnostic ----------------------------------------------------------

function DiagnosticDetail({
  diagnostic,
  index,
  entityLabels,
  onSelect,
}: {
  diagnostic: WorkspaceDiagnostic;
  index: WorkspaceIndex;
  entityLabels: ReadonlyMap<string, string>;
  onSelect: (kind: SelectionKind, key: string) => void;
}) {
  return (
    <div>
      <StateBadge tone="declined" />

      <p className="mt-3 text-sm leading-6 text-foreground">
        {diagnostic.explanation}
      </p>

      <dl className="mt-4">
        <InspectorField label="Motivo dichiarato">
          <span className="font-mono text-xs">{diagnostic.reason}</span>
        </InspectorField>

        <InspectorField label="Origine">
          {diagnostic.origin === "fact"
            ? "Costruzione dei fatti"
            : "Interpretazione semantica"}
        </InspectorField>

        <InspectorField label="Posizione nel sorgente">
          {diagnostic.location === null
            ? "Nessuna: la diagnostica riguarda un soggetto, non una riga."
            : describeLocation(diagnostic.location)}
        </InspectorField>
      </dl>

      {diagnostic.entityKeys.length > 0 && (
        <>
          <Heading>Entità coinvolte</Heading>

          <div className="space-y-2">
            {diagnostic.entityKeys.map((key) => (
              <ChainStep
                key={key}
                kind="entity"
                artefactKey={key}
                resolved={index.entitiesByKey.has(key)}
                title={entityLabel(entityLabels, key)}
                detail={key}
                onSelect={() => onSelect("entity", key)}
              />
            ))}
          </div>
        </>
      )}

      {diagnostic.factKeys.length > 0 && (
        <>
          <Heading>Fatti candidati</Heading>

          <div className="space-y-2">
            {diagnostic.factKeys.map((key) => (
              <FactStep
                key={key}
                factKey={key}
                index={index}
                entityLabels={entityLabels}
                onSelect={onSelect}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
