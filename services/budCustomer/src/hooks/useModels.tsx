export interface Model {
  id: string;
  name: string;
  type: string;
}

export interface ScanResult {
  id: string;
  modelId: string;
  status: string;
}