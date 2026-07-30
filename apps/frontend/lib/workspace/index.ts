/**
 * The Engineering Workspace read model.
 *
 * A projection over artefacts the backend already governs: it indexes,
 * navigates and describes them. It constructs no engineering knowledge,
 * and every join it makes is on a key the backend wrote down.
 */

export * from "./model";
export * from "./presentation";
export * from "./selection";
export * from "./source-location";
