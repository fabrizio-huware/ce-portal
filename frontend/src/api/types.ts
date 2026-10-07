import type { components } from "./schema";

type S = components["schemas"];
export type CeDetail = S["CEDetail"];
export type CeListItem = S["CEListItem"];
export type ViewerListItem = S["ViewerListItem"];
export type ViewerCe = S["ViewerCE"];
export type UserOut = S["UserOut"];
export type ClientRef = S["ClientRef"];
export type VersionListItem = S["VersionListItem"];
export type HistoryItem = S["HistoryItem"];
export type Actions = S["Actions"];
export type PhaseOut = S["PhaseOut"];
export type LineOut = S["LineOut"];
export type Calculation = S["CalculationOut"];
export type PageOf<T> = { items: T[]; total: number; limit: number; offset: number };
