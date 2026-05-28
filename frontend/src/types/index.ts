export interface Question {
  id: number;
  section: string;
  qtype: string;
  marks: number;
  text: string;
  options: { label: string; text: string }[];
  // Only present on dedicated answer-key endpoints; the default question
  // serializer omits it so paper-assemble responses do not leak the key.
  answer?: string;
}

export interface PaperItem {
  order: number;
  section: string;
  question: Question;
}

export interface Paper {
  id: number;
  title: string;
  total_marks: number;
  created_at: string;
  items: PaperItem[];
}
