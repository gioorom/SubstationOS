export type CommissioningAssetType =
  | "line-bay"
  | "power-transformer"
  | "medium-voltage-feeder"
  | "petersen-coil"
  | "auxiliary-services"
  | "remote-control";

export type CommissioningAssetStatus =
  | "not-started"
  | "in-progress"
  | "blocked"
  | "ready-for-review"
  | "completed";

export type CommissioningPriority =
  | "low"
  | "medium"
  | "high"
  | "critical";

export type CommissioningActivityStatus =
  | "pending"
  | "in-progress"
  | "blocked"
  | "completed"
  | "not-applicable";

export type CommissioningEvidenceType =
  | "document"
  | "photo"
  | "test-report"
  | "certificate"
  | "drawing"
  | "note";

export type CommissioningResponsibleRole =
  | "commissioning-engineer"
  | "protection-engineer"
  | "site-manager"
  | "automation-engineer"
  | "contractor"
  | "client"
  | "vendor";

export type CommissioningDocumentStatus =
  | "missing"
  | "incomplete"
  | "complete"
  | "under-review"
  | "rejected";

export type CommissioningDocumentCategory =
  | "instrument-transformer"
  | "protection"
  | "configuration"
  | "telecontrol"
  | "general";

export type ElectricalSectionColor =
  | "red"
  | "green"
  | "neutral";

export type CommissioningDocumentScope =
  | "single-asset"
  | "asset-group"
  | "project";

export interface CommissioningResponsible {
  id: string;
  name: string;
  role: CommissioningResponsibleRole;
  company?: string;
  avatarUrl?: string;
}

export interface CommissioningEvidence {
  id: string;
  name: string;
  type: CommissioningEvidenceType;
  url?: string;
  uploadedAt: string;
  uploadedBy?: CommissioningResponsible;
}

export interface CommissioningDocumentFile {
  id: string;
  fileName: string;
  mimeType: "application/pdf";
  sizeBytes?: number;
  url?: string;
  revision?: string;
  notes?: string;
  uploadedAt: string;
  uploadedBy?: CommissioningResponsible;
}

export interface CommissioningDocumentRequirement {
  id: string;
  code: string;
  title: string;
  description?: string;
  category: CommissioningDocumentCategory;
  scope: CommissioningDocumentScope;

  /**
   * Numero esatto di file PDF richiesti.
   * Esempio: Report Protezione TR richiede 2 file.
   */
  requiredFiles: number;

  /**
   * File effettivamente caricati per questo requisito.
   */
  uploadedFiles: CommissioningDocumentFile[];

  status: CommissioningDocumentStatus;
  mandatory: boolean;

  /**
   * Ordine di visualizzazione all'interno dell'asset.
   */
  order: number;

  /**
   * Usato per requisiti condivisi, ad esempio:
   * - un file GESI per tutte le LMT rosse;
   * - un file GESI per entrambe le isole Petersen.
   */
  relatedAssetIds?: string[];

  notes?: string;
  updatedAt: string;
}

export interface CommissioningActivity {
  id: string;
  code: string;
  title: string;
  description?: string;
  status: CommissioningActivityStatus;
  priority: CommissioningPriority;
  progress: number;
  estimatedHours?: number;
  responsible?: CommissioningResponsible;
  dueDate?: string;
  completedAt?: string;
  notes?: string;
  evidence?: CommissioningEvidence[];
}

export interface CommissioningAssetMetrics {
  totalActivities: number;
  completedActivities: number;
  blockedActivities: number;
  openIssues: number;
  documents: number;
  progress: number;

  /**
   * Metriche documentali reali.
   * Sono opzionali per mantenere compatibili i dati demo esistenti.
   */
  requiredDocuments?: number;
  uploadedDocuments?: number;
  completedDocumentRequirements?: number;
  totalDocumentRequirements?: number;
  documentCompletion?: number;
}

export interface CommissioningAsset {
  id: string;
  projectId: string;
  slug: string;
  code: string;
  name: string;
  shortName: string;
  description: string;
  type: CommissioningAssetType;
  status: CommissioningAssetStatus;
  priority: CommissioningPriority;

  /**
   * Sezione elettrica dell'asset.
   * Esempi: rosso, verde o neutro.
   */
  sectionColor?: ElectricalSectionColor;

  /**
   * Indice progressivo usato soprattutto per le Linee MT.
   * Esempio: LMT Rossa 1, LMT Rossa 2, LMT Verde 1.
   */
  sequenceNumber?: number;

  location?: string;
  system?: string;
  vendor?: string;
  responsible?: CommissioningResponsible;
  plannedStartDate?: string;
  plannedEndDate?: string;
  actualStartDate?: string;
  actualEndDate?: string;

  metrics: CommissioningAssetMetrics;
  activities: CommissioningActivity[];

  /**
   * Matrice dei report obbligatori dell'asset.
   */
  documentRequirements?: CommissioningDocumentRequirement[];

  tags?: string[];
  updatedAt: string;
}

export interface CommissioningSummary {
  totalAssets: number;
  completedAssets: number;
  inProgressAssets: number;
  blockedAssets: number;
  notStartedAssets: number;
  readyForReviewAssets: number;
  overallProgress: number;
  openIssues: number;

  requiredDocuments?: number;
  uploadedDocuments?: number;
  missingDocuments?: number;
  documentCompletion?: number;
}

export interface MediumVoltageFeederConfiguration {
  redFeedersCount: number;
  greenFeedersCount: number;
}

export interface ProjectCommissioningConfiguration {
  mediumVoltageFeeders: MediumVoltageFeederConfiguration;

  /**
   * Nome del sistema di telecontrollo.
   * Per Distributore Nazionale il valore predefinito sarà "GESI".
   */
  telecontrolSystemName: string;

  configuredAt?: string;
  configuredBy?: CommissioningResponsible;
}

export interface ProjectCommissioning {
  projectId: string;
  configuration: ProjectCommissioningConfiguration;
  assets: CommissioningAsset[];

  /**
   * Requisiti trasversali non appartenenti a un singolo asset,
   * come alcuni report GESI condivisi.
   */
  projectDocumentRequirements?: CommissioningDocumentRequirement[];

  summary: CommissioningSummary;
  updatedAt: string;
}