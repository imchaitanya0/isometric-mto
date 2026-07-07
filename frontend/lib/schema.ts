/**
 * TypeScript types mirroring the backend Pydantic models exactly.
 * Keep in sync with backend/models/mto.py
 */

export type ItemCategory =
  | "PIPE"
  | "FITTING"
  | "FLANGE"
  | "VALVE"
  | "GASKET"
  | "BOLT"
  | "SUPPORT"
  | "INSTRUMENT";

export type ItemUnit = "M" | "EA" | "SET" | "NO";
export type EndType = "BW" | "SW" | "THD" | "FLGD" | "PE" | "BE";
export type JobStatus = "processing" | "completed" | "failed";

export interface BoundingBox {
  x: number;      // 0–1 normalized
  y: number;
  width: number;
  height: number;
}

export interface LineNumberParsed {
  size?: string;
  service?: string;
  sequence?: string;
  material_class?: string;
  insulation?: string;
  raw?: string;
}

export interface DrawingMeta {
  drawing_no?: string;
  revision?: string;
  line_number?: string;
  line_number_parsed?: LineNumberParsed;
  nps?: string;
  material_class?: string;
  service?: string;
  design_pressure?: string;
  design_temperature?: string;
  confidence: number;
}

export interface MTOItem {
  item_no: number;
  category: ItemCategory;
  description: string;
  size_nps: string;
  schedule_rating?: string;
  material_spec?: string;
  end_type?: EndType;
  quantity: number;
  unit: ItemUnit;
  length_m?: number;
  confidence: number;
  remarks?: string;
  bbox?: BoundingBox;
}

export interface Summary {
  total_pipe_length_m: number;
  fittings: number;
  flanges: number;
  valves: number;
  gaskets: number;
  bolt_sets: number;
  field_welds: number;
  low_confidence_items: number;
}

export interface MTOResult {
  drawing_meta: DrawingMeta;
  items: MTOItem[];
  summary: Summary;
  source: "ai" | "mock";
  processing_time_s?: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  result?: MTOResult;
  error?: string;
  filename?: string;
}

export interface UploadResponse {
  job_id: string;
  filename: string;
  size_mb: number;
}
