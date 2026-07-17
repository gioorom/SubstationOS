import type {
  CommissioningAsset,
  CommissioningAssetMetrics,
  CommissioningDocumentFile,
  CommissioningDocumentRequirement,
  CommissioningDocumentStatus,
  ElectricalSectionColor,
  ProjectCommissioning,
} from "@/types/commissioning";

const DEMO_PROJECT_ID = "1";
const DEMO_UPDATED_AT = "2026-07-18T08:00:00Z";

const RED_FEEDERS_COUNT = 3;
const GREEN_FEEDERS_COUNT = 3;

interface DocumentRequirementOptions {
  id: string;
  code: string;
  title: string;
  category: CommissioningDocumentRequirement["category"];
  requiredFiles?: number;
  order: number;
  description?: string;
  relatedAssetIds?: string[];
  uploadedFileNames?: string[];
}

interface AssetMetricsOptions {
  totalActivities: number;
  completedActivities: number;
  blockedActivities: number;
  openIssues: number;
  progress: number;
  documentRequirements: CommissioningDocumentRequirement[];
}

function createDocumentFile(
  requirementId: string,
  fileName: string,
  index: number
): CommissioningDocumentFile {
  return {
    id: `${requirementId}-file-${index + 1}`,
    fileName,
    mimeType: "application/pdf",
    revision: "Rev. 0",
    uploadedAt: DEMO_UPDATED_AT,
  };
}

function getDocumentStatus(
  uploadedFiles: number,
  requiredFiles: number
): CommissioningDocumentStatus {
  if (uploadedFiles === 0) {
    return "missing";
  }

  if (uploadedFiles < requiredFiles) {
    return "incomplete";
  }

  return "complete";
}

function createDocumentRequirement({
  id,
  code,
  title,
  category,
  requiredFiles = 1,
  order,
  description,
  relatedAssetIds,
  uploadedFileNames = [],
}: DocumentRequirementOptions): CommissioningDocumentRequirement {
  const uploadedFiles = uploadedFileNames
    .slice(0, requiredFiles)
    .map((fileName, index) =>
      createDocumentFile(id, fileName, index)
    );

  return {
    id,
    code,
    title,
    description,
    category,
    scope: relatedAssetIds?.length
      ? "asset-group"
      : "single-asset",
    requiredFiles,
    uploadedFiles,
    status: getDocumentStatus(
      uploadedFiles.length,
      requiredFiles
    ),
    mandatory: true,
    order,
    relatedAssetIds,
    updatedAt: DEMO_UPDATED_AT,
  };
}

function createAssetMetrics({
  totalActivities,
  completedActivities,
  blockedActivities,
  openIssues,
  progress,
  documentRequirements,
}: AssetMetricsOptions): CommissioningAssetMetrics {
  const requiredDocuments = documentRequirements.reduce(
    (total, requirement) =>
      total + requirement.requiredFiles,
    0
  );

  const uploadedDocuments = documentRequirements.reduce(
    (total, requirement) =>
      total + requirement.uploadedFiles.length,
    0
  );

  const completedDocumentRequirements =
    documentRequirements.filter(
      (requirement) => requirement.status === "complete"
    ).length;

  const documentCompletion =
    requiredDocuments === 0
      ? 0
      : Math.round(
          (uploadedDocuments / requiredDocuments) * 100
        );

  return {
    totalActivities,
    completedActivities,
    blockedActivities,
    openIssues,
    documents: uploadedDocuments,
    progress,
    requiredDocuments,
    uploadedDocuments,
    completedDocumentRequirements,
    totalDocumentRequirements:
      documentRequirements.length,
    documentCompletion,
  };
}

function createLatRequirements(
  assetId: string,
  assetCode: string,
  uploadedDocuments: {
    tv?: boolean;
    ta?: boolean;
    protection?: boolean;
  } = {}
): CommissioningDocumentRequirement[] {
  return [
    createDocumentRequirement({
      id: `${assetId}-tv`,
      code: `${assetCode}-TV`,
      title: "Report TV LAT",
      description:
        "Rapporto di prova dei trasformatori di tensione dello stallo LAT.",
      category: "instrument-transformer",
      order: 1,
      uploadedFileNames: uploadedDocuments.tv
        ? [`${assetCode}_Report_TV_LAT.pdf`]
        : [],
    }),
    createDocumentRequirement({
      id: `${assetId}-ta`,
      code: `${assetCode}-TA`,
      title: "Report TA LAT",
      description:
        "Rapporto di prova dei trasformatori di corrente dello stallo LAT.",
      category: "instrument-transformer",
      order: 2,
      uploadedFileNames: uploadedDocuments.ta
        ? [`${assetCode}_Report_TA_LAT.pdf`]
        : [],
    }),
    createDocumentRequirement({
      id: `${assetId}-distance-protection`,
      code: `${assetCode}-PD`,
      title: "Report Protezione Distanziometrica",
      description:
        "Rapporto completo delle prove sulla protezione distanziometrica.",
      category: "protection",
      order: 3,
      uploadedFileNames: uploadedDocuments.protection
        ? [
            `${assetCode}_Report_Protezione_Distanziometrica.pdf`,
          ]
        : [],
    }),
  ];
}

function createTransformerRequirements(
  assetId: string,
  assetCode: string,
  uploadedDocuments: {
    taAt?: boolean;
    taMt?: boolean;
    protectionFiles?: number;
  } = {}
): CommissioningDocumentRequirement[] {
  const protectionFileCount =
    uploadedDocuments.protectionFiles ?? 0;

  return [
    createDocumentRequirement({
      id: `${assetId}-ta-at`,
      code: `${assetCode}-TA-AT`,
      title: "Report TA AT TR",
      description:
        "Rapporto di prova dei trasformatori di corrente lato AT del trasformatore.",
      category: "instrument-transformer",
      order: 1,
      uploadedFileNames: uploadedDocuments.taAt
        ? [`${assetCode}_Report_TA_AT.pdf`]
        : [],
    }),
    createDocumentRequirement({
      id: `${assetId}-ta-mt`,
      code: `${assetCode}-TA-MT`,
      title: "Report TA MT TR",
      description:
        "Rapporto di prova dei trasformatori di corrente lato MT del trasformatore.",
      category: "instrument-transformer",
      order: 2,
      uploadedFileNames: uploadedDocuments.taMt
        ? [`${assetCode}_Report_TA_MT.pdf`]
        : [],
    }),
    createDocumentRequirement({
      id: `${assetId}-protection`,
      code: `${assetCode}-PROT`,
      title: "Report Protezione TR",
      description:
        "Documentazione completa delle prove delle protezioni del trasformatore.",
      category: "protection",
      requiredFiles: 2,
      order: 3,
      uploadedFileNames: Array.from(
        { length: protectionFileCount },
        (_, index) =>
          `${assetCode}_Report_Protezione_TR_${index + 1}.pdf`
      ),
    }),
  ];
}

function createFeederRequirements(
  assetId: string,
  assetCode: string,
  uploadedDocuments: {
    taTo?: boolean;
    protection?: boolean;
  } = {}
): CommissioningDocumentRequirement[] {
  return [
    createDocumentRequirement({
      id: `${assetId}-ta-to`,
      code: `${assetCode}-TA-TO`,
      title: "Report TA + TO",
      description:
        "Rapporto di prova dei trasformatori di corrente e del trasformatore omopolare della linea MT.",
      category: "instrument-transformer",
      order: 1,
      uploadedFileNames: uploadedDocuments.taTo
        ? [`${assetCode}_Report_TA_TO.pdf`]
        : [],
    }),
    createDocumentRequirement({
      id: `${assetId}-protection`,
      code: `${assetCode}-PROT`,
      title: "Report Protezione LMT",
      description:
        "Rapporto completo delle prove della protezione della linea MT.",
      category: "protection",
      order: 2,
      uploadedFileNames: uploadedDocuments.protection
        ? [`${assetCode}_Report_Protezione_LMT.pdf`]
        : [],
    }),
  ];
}

function createPetersenRequirements(
  assetId: string,
  assetCode: string,
  uploadedDocuments: {
    taTo?: boolean;
    protection?: boolean;
  } = {}
): CommissioningDocumentRequirement[] {
  return [
    createDocumentRequirement({
      id: `${assetId}-tfn-ta-to`,
      code: `${assetCode}-TA-TO`,
      title: "Report TA + TO linea MT TFN",
      description:
        "Rapporto di prova TA e TO della linea MT dedicata al TFN.",
      category: "instrument-transformer",
      order: 1,
      uploadedFileNames: uploadedDocuments.taTo
        ? [`${assetCode}_Report_TA_TO_TFN.pdf`]
        : [],
    }),
    createDocumentRequirement({
      id: `${assetId}-tfn-protection`,
      code: `${assetCode}-PROT`,
      title: "Report Protezione TFN",
      description:
        "Rapporto completo delle prove della protezione TFN.",
      category: "protection",
      order: 2,
      uploadedFileNames: uploadedDocuments.protection
        ? [`${assetCode}_Report_Protezione_TFN.pdf`]
        : [],
    }),
  ];
}

function createMediumVoltageFeeder(
  sectionColor: Exclude<
    ElectricalSectionColor,
    "neutral"
  >,
  sequenceNumber: number
): CommissioningAsset {
  const colorLabel =
    sectionColor === "red" ? "Rossa" : "Verde";

  const colorCode =
    sectionColor === "red" ? "R" : "V";

  const assetId = `lmt-${sectionColor}-${sequenceNumber}`;
  const assetCode = `LMT-${colorCode}-${sequenceNumber}`;

  const documentRequirements =
    createFeederRequirements(
      assetId,
      assetCode,
      sectionColor === "red" && sequenceNumber === 1
        ? {
            taTo: true,
            protection: true,
          }
        : {}
    );

  const completedActivities =
    sectionColor === "red"
      ? Math.max(0, 16 - sequenceNumber * 2)
      : Math.max(0, 8 - sequenceNumber);

  const totalActivities = 20;
  const progress = Math.round(
    (completedActivities / totalActivities) * 100
  );

  return {
    id: assetId,
    projectId: DEMO_PROJECT_ID,
    slug: assetId,
    code: assetCode,
    name: `Linea MT ${colorLabel} ${sequenceNumber}`,
    shortName: `LMT ${colorCode} ${sequenceNumber}`,
    description: `Linea media tensione della sezione ${colorLabel.toLowerCase()}.`,
    type: "medium-voltage-feeder",
    status:
      progress === 0
        ? "not-started"
        : progress >= 90
          ? "ready-for-review"
          : "in-progress",
    priority: "high",
    sectionColor,
    sequenceNumber,
    metrics: createAssetMetrics({
      totalActivities,
      completedActivities,
      blockedActivities: 0,
      openIssues:
        sectionColor === "red" &&
        sequenceNumber === 2
          ? 1
          : 0,
      progress,
      documentRequirements,
    }),
    activities: [],
    documentRequirements,
    tags: [
      "linea-mt",
      sectionColor,
      `linea-${sequenceNumber}`,
    ],
    updatedAt: DEMO_UPDATED_AT,
  };
}

const lat1Requirements = createLatRequirements(
  "lat-1",
  "LAT-01",
  {
    tv: true,
    ta: true,
    protection: true,
  }
);

const lat2Requirements = createLatRequirements(
  "lat-2",
  "LAT-02",
  {
    tv: true,
    ta: true,
    protection: false,
  }
);

const transformerRedRequirements =
  createTransformerRequirements(
    "tr-red",
    "TR-R",
    {
      taAt: true,
      taMt: true,
      protectionFiles: 1,
    }
  );

const transformerGreenRequirements =
  createTransformerRequirements(
    "tr-green",
    "TR-V"
  );

const petersenRedRequirements =
  createPetersenRequirements(
    "petersen-red",
    "PET-R",
    {
      taTo: true,
      protection: false,
    }
  );

const petersenGreenRequirements =
  createPetersenRequirements(
    "petersen-green",
    "PET-V"
  );

const auxiliaryRequirements: CommissioningDocumentRequirement[] =
  [
    createDocumentRequirement({
      id: "aux-panel-configuration",
      code: "AUX-CONF",
      title: "Report configurazione del quadro",
      description:
        "Report completo della configurazione del Quadro Servizi Ausiliari.",
      category: "configuration",
      order: 1,
    }),
  ];

const redFeeders = Array.from(
  { length: RED_FEEDERS_COUNT },
  (_, index) =>
    createMediumVoltageFeeder("red", index + 1)
);

const greenFeeders = Array.from(
  { length: GREEN_FEEDERS_COUNT },
  (_, index) =>
    createMediumVoltageFeeder("green", index + 1)
);

const redFeederIds = redFeeders.map(
  (asset) => asset.id
);

const greenFeederIds = greenFeeders.map(
  (asset) => asset.id
);

const petersenAssetIds = [
  "petersen-red",
  "petersen-green",
];

const telecontrolRequirements: CommissioningDocumentRequirement[] =
  [
    createDocumentRequirement({
      id: "gesi-lat-1-red",
      code: "GESI-LAT-1-R",
      title: "LAT 1 Rossa",
      description:
        "Report di verifica telecontrollo GESI dello Stallo LAT 1 Rosso.",
      category: "telecontrol",
      order: 1,
      relatedAssetIds: ["lat-1"],
      uploadedFileNames: [
        "GESI_LAT_1_Rossa.pdf",
      ],
    }),
    createDocumentRequirement({
      id: "gesi-lat-2-green",
      code: "GESI-LAT-2-V",
      title: "LAT 2 Verde",
      description:
        "Report di verifica telecontrollo GESI dello Stallo LAT 2 Verde.",
      category: "telecontrol",
      order: 2,
      relatedAssetIds: ["lat-2"],
    }),
    createDocumentRequirement({
      id: "gesi-tr-red",
      code: "GESI-TR-R",
      title: "TR Rosso",
      description:
        "Report di verifica telecontrollo GESI del Trasformatore Rosso.",
      category: "telecontrol",
      order: 3,
      relatedAssetIds: ["tr-red"],
    }),
    createDocumentRequirement({
      id: "gesi-tr-green",
      code: "GESI-TR-V",
      title: "TR Verde",
      description:
        "Report di verifica telecontrollo GESI del Trasformatore Verde.",
      category: "telecontrol",
      order: 4,
      relatedAssetIds: ["tr-green"],
    }),
    createDocumentRequirement({
      id: "gesi-lmt-red",
      code: "GESI-LMT-R",
      title: "LMT Rosse",
      description:
        "Un unico report GESI complessivo per tutte le Linee MT Rosse.",
      category: "telecontrol",
      order: 5,
      relatedAssetIds: redFeederIds,
    }),
    createDocumentRequirement({
      id: "gesi-lmt-green",
      code: "GESI-LMT-V",
      title: "LMT Verdi",
      description:
        "Un unico report GESI complessivo per tutte le Linee MT Verdi.",
      category: "telecontrol",
      order: 6,
      relatedAssetIds: greenFeederIds,
    }),
    createDocumentRequirement({
      id: "gesi-petersen-tfn",
      code: "GESI-PET-TFN",
      title: "Isola Petersen + TFN",
      description:
        "Un unico report GESI complessivo per entrambe le Isole Petersen e i relativi TFN.",
      category: "telecontrol",
      order: 7,
      relatedAssetIds: petersenAssetIds,
    }),
    createDocumentRequirement({
      id: "gesi-auxiliary-panel",
      code: "GESI-AUX",
      title: "Quadro Servizi Ausiliari",
      description:
        "Report di verifica telecontrollo GESI del Quadro Servizi Ausiliari.",
      category: "telecontrol",
      order: 8,
      relatedAssetIds: ["auxiliary-services"],
    }),
  ];

const assets: CommissioningAsset[] = [
  {
    id: "lat-1",
    projectId: DEMO_PROJECT_ID,
    slug: "stallo-lat-1",
    code: "LAT-01",
    name: "Stallo LAT 1",
    shortName: "LAT 1",
    description:
      "Stallo linea alta tensione della sezione rossa.",
    type: "line-bay",
    status: "completed",
    priority: "high",
    sectionColor: "red",
    metrics: createAssetMetrics({
      totalActivities: 48,
      completedActivities: 48,
      blockedActivities: 0,
      openIssues: 0,
      progress: 100,
      documentRequirements: lat1Requirements,
    }),
    activities: [],
    documentRequirements: lat1Requirements,
    tags: ["lat", "alta-tensione", "red"],
    updatedAt: DEMO_UPDATED_AT,
  },
  {
    id: "lat-2",
    projectId: DEMO_PROJECT_ID,
    slug: "stallo-lat-2",
    code: "LAT-02",
    name: "Stallo LAT 2",
    shortName: "LAT 2",
    description:
      "Stallo linea alta tensione della sezione verde.",
    type: "line-bay",
    status: "in-progress",
    priority: "high",
    sectionColor: "green",
    metrics: createAssetMetrics({
      totalActivities: 52,
      completedActivities: 39,
      blockedActivities: 1,
      openIssues: 2,
      progress: 75,
      documentRequirements: lat2Requirements,
    }),
    activities: [],
    documentRequirements: lat2Requirements,
    tags: ["lat", "alta-tensione", "green"],
    updatedAt: DEMO_UPDATED_AT,
  },
  {
    id: "tr-red",
    projectId: DEMO_PROJECT_ID,
    slug: "tr-rosso",
    code: "TR-R",
    name: "TR Rosso",
    shortName: "TR Rosso",
    description:
      "Trasformatore di potenza della sezione rossa.",
    type: "power-transformer",
    status: "in-progress",
    priority: "critical",
    sectionColor: "red",
    metrics: createAssetMetrics({
      totalActivities: 86,
      completedActivities: 56,
      blockedActivities: 3,
      openIssues: 4,
      progress: 65,
      documentRequirements:
        transformerRedRequirements,
    }),
    activities: [],
    documentRequirements:
      transformerRedRequirements,
    tags: ["trasformatore", "potenza", "red"],
    updatedAt: DEMO_UPDATED_AT,
  },
  {
    id: "tr-green",
    projectId: DEMO_PROJECT_ID,
    slug: "tr-verde",
    code: "TR-V",
    name: "TR Verde",
    shortName: "TR Verde",
    description:
      "Trasformatore di potenza della sezione verde.",
    type: "power-transformer",
    status: "not-started",
    priority: "high",
    sectionColor: "green",
    metrics: createAssetMetrics({
      totalActivities: 86,
      completedActivities: 0,
      blockedActivities: 0,
      openIssues: 0,
      progress: 0,
      documentRequirements:
        transformerGreenRequirements,
    }),
    activities: [],
    documentRequirements:
      transformerGreenRequirements,
    tags: ["trasformatore", "potenza", "green"],
    updatedAt: DEMO_UPDATED_AT,
  },

  ...redFeeders,
  ...greenFeeders,

  {
    id: "petersen-red",
    projectId: DEMO_PROJECT_ID,
    slug: "isola-petersen-tfn-rossa",
    code: "PET-R",
    name: "Isola Petersen + TFN Rossa",
    shortName: "Petersen Rossa",
    description:
      "Sistema Petersen e trasformatore formatore del neutro della sezione rossa.",
    type: "petersen-coil",
    status: "in-progress",
    priority: "medium",
    sectionColor: "red",
    metrics: createAssetMetrics({
      totalActivities: 22,
      completedActivities: 13,
      blockedActivities: 0,
      openIssues: 1,
      progress: 59,
      documentRequirements:
        petersenRedRequirements,
    }),
    activities: [],
    documentRequirements:
      petersenRedRequirements,
    tags: ["petersen", "tfn", "red"],
    updatedAt: DEMO_UPDATED_AT,
  },
  {
    id: "petersen-green",
    projectId: DEMO_PROJECT_ID,
    slug: "isola-petersen-tfn-verde",
    code: "PET-V",
    name: "Isola Petersen + TFN Verde",
    shortName: "Petersen Verde",
    description:
      "Sistema Petersen e trasformatore formatore del neutro della sezione verde.",
    type: "petersen-coil",
    status: "not-started",
    priority: "medium",
    sectionColor: "green",
    metrics: createAssetMetrics({
      totalActivities: 22,
      completedActivities: 0,
      blockedActivities: 0,
      openIssues: 0,
      progress: 0,
      documentRequirements:
        petersenGreenRequirements,
    }),
    activities: [],
    documentRequirements:
      petersenGreenRequirements,
    tags: ["petersen", "tfn", "green"],
    updatedAt: DEMO_UPDATED_AT,
  },
  {
    id: "auxiliary-services",
    projectId: DEMO_PROJECT_ID,
    slug: "quadro-servizi-ausiliari",
    code: "AUX",
    name: "Quadro Servizi Ausiliari",
    shortName: "Servizi Ausiliari",
    description:
      "Quadro e sistemi di alimentazione dei servizi ausiliari di cabina.",
    type: "auxiliary-services",
    status: "in-progress",
    priority: "critical",
    sectionColor: "neutral",
    metrics: createAssetMetrics({
      totalActivities: 44,
      completedActivities: 28,
      blockedActivities: 2,
      openIssues: 3,
      progress: 64,
      documentRequirements:
        auxiliaryRequirements,
    }),
    activities: [],
    documentRequirements:
      auxiliaryRequirements,
    tags: ["servizi-ausiliari", "quadro"],
    updatedAt: DEMO_UPDATED_AT,
  },
  {
    id: "telecontrol",
    projectId: DEMO_PROJECT_ID,
    slug: "telecontrollo-gesi",
    code: "GESI",
    name: "Telecontrollo - GESI",
    shortName: "GESI",
    description:
      "Verifiche di telecontrollo e supervisione per impianti Distributore Nazionale.",
    type: "remote-control",
    status: "blocked",
    priority: "critical",
    sectionColor: "neutral",
    metrics: createAssetMetrics({
      totalActivities: 18,
      completedActivities: 10,
      blockedActivities: 4,
      openIssues: 5,
      progress: 55,
      documentRequirements:
        telecontrolRequirements,
    }),
    activities: [],
    documentRequirements:
      telecontrolRequirements,
    tags: ["telecontrollo", "gesi"],
    updatedAt: DEMO_UPDATED_AT,
  },
];

const requiredDocuments = assets.reduce(
  (total, asset) =>
    total +
    (asset.metrics.requiredDocuments ?? 0),
  0
);

const uploadedDocuments = assets.reduce(
  (total, asset) =>
    total +
    (asset.metrics.uploadedDocuments ?? 0),
  0
);

const totalWeightedProgress = assets.reduce(
  (total, asset) =>
    total + asset.metrics.progress,
  0
);

const overallProgress =
  assets.length === 0
    ? 0
    : Math.round(
        totalWeightedProgress / assets.length
      );

export const demoCommissioning: ProjectCommissioning =
  {
    projectId: DEMO_PROJECT_ID,
    configuration: {
      mediumVoltageFeeders: {
        redFeedersCount: RED_FEEDERS_COUNT,
        greenFeedersCount: GREEN_FEEDERS_COUNT,
      },
      telecontrolSystemName: "GESI",
      configuredAt: DEMO_UPDATED_AT,
    },
    assets,
    summary: {
      totalAssets: assets.length,
      completedAssets: assets.filter(
        (asset) => asset.status === "completed"
      ).length,
      inProgressAssets: assets.filter(
        (asset) => asset.status === "in-progress"
      ).length,
      blockedAssets: assets.filter(
        (asset) => asset.status === "blocked"
      ).length,
      notStartedAssets: assets.filter(
        (asset) => asset.status === "not-started"
      ).length,
      readyForReviewAssets: assets.filter(
        (asset) =>
          asset.status === "ready-for-review"
      ).length,
      overallProgress,
      openIssues: assets.reduce(
        (total, asset) =>
          total + asset.metrics.openIssues,
        0
      ),
      requiredDocuments,
      uploadedDocuments,
      missingDocuments: Math.max(
        0,
        requiredDocuments - uploadedDocuments
      ),
      documentCompletion:
        requiredDocuments === 0
          ? 0
          : Math.round(
              (uploadedDocuments /
                requiredDocuments) *
                100
            ),
    },
    updatedAt: DEMO_UPDATED_AT,
  };

export const demoCommissioningAssets =
  demoCommissioning.assets;

export function getDemoCommissioningAsset(
  slug: string
): CommissioningAsset | undefined {
  return demoCommissioning.assets.find(
    (asset) => asset.slug === slug
  );
}