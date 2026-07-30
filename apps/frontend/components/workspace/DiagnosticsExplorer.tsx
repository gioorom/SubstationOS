"use client";

import {
  describeLocation,
  entityLabel,
  reconcileDiagnosticStatus,
  type StageStatus,
  type WorkspaceDiagnostic,
} from "@/lib/workspace";

import ArtefactButton from "./ArtefactButton";
import ExplorerList from "./ExplorerList";
import StateBadge from "./StateBadge";

interface DiagnosticsExplorerProps {
  diagnostics: readonly WorkspaceDiagnostic[];
  /** Both stages that emit diagnostics, so an unrun one is not "none". */
  factStatus: StageStatus;
  semanticStatus: StageStatus;
  selectedKey: string | null;
  onSelect: (diagnosticKey: string) => void;
  entityLabels: ReadonlyMap<string, string>;
}

const ORIGIN_LABELS: Record<WorkspaceDiagnostic["origin"], string> = {
  fact: "Costruzione del fatto declinata",
  semantic: "Interpretazione semantica declinata",
};

/**
 * Declined results, as content rather than as a warning banner.
 *
 * A diagnostic is the rules working: candidates existed, the rule was
 * evaluated, and it deliberately produced nothing rather than guess.
 * That is why these are shown as artefacts an engineer can select and
 * navigate from, and why the tone is `declinato` - not `fallito`, which
 * would say the system broke, and not `ambiguo`, which is a property an
 * artefact that *does* exist can carry.
 *
 * The list is not empty when there are no diagnostics but a stage never
 * ran: those two are reported separately, because a document with no
 * declined interpretations and a document that was never interpreted are
 * not the same document.
 */
export default function DiagnosticsExplorer({
  diagnostics,
  factStatus,
  semanticStatus,
  selectedKey,
  onSelect,
  entityLabels,
}: DiagnosticsExplorerProps) {
  const status = reconcileDiagnosticStatus(
    factStatus,
    semanticStatus,
    diagnostics.length,
  );

  return (
    <div className="space-y-4">
      <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-700">
        Una diagnostica non è un fallimento e non è un&apos;affermazione:
        è una regola che, di fronte a più candidati, ha scelto di non
        dedurre. Il soggetto resta senza significato interpretato, e in
        nessun elenco di questa pagina compare come se ne avesse uno.
      </p>

      <ExplorerList
        items={diagnostics}
        keyOf={(diagnostic) => diagnostic.key}
        status={status}
        noun="diagnostiche"
        label="Diagnostiche"
        render={(diagnostic) => (
          <ArtefactButton
            selected={diagnostic.key === selectedKey}
            onSelect={() => onSelect(diagnostic.key)}
            label={`${ORIGIN_LABELS[diagnostic.origin]}: ${diagnostic.explanation}`}
          >
            <span className="flex flex-wrap items-center gap-2">
              <StateBadge tone="declined" />

              <span className="text-sm font-medium text-foreground">
                {ORIGIN_LABELS[diagnostic.origin]}
              </span>

              <span className="font-mono text-xs text-slate-600">
                {diagnostic.reason}
              </span>
            </span>

            <span className="mt-1 block text-xs leading-5 text-muted-foreground">
              {diagnostic.explanation}
            </span>

            <span className="mt-1 block text-xs text-muted-foreground">
              {diagnostic.location === null
                ? "Nessuna riga di origine: la diagnostica riguarda un soggetto, non una riga."
                : describeLocation(diagnostic.location)}
              {diagnostic.entityKeys.length > 0 && (
                <>
                  {" · "}
                  {diagnostic.entityKeys
                    .map((key) => entityLabel(entityLabels, key))
                    .join(", ")}
                </>
              )}
            </span>
          </ArtefactButton>
        )}
      />
    </div>
  );
}
