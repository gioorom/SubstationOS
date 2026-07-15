export interface Document {
  id: number;
  project_id: number | null;
  filename: string;
  file_path: string;
  file_format: string;
  category: string;
  revision: string;
  project_name: string;
  uploaded_at: string;
}