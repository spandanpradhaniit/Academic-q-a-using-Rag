export type DocumentStatus = "Uploaded" | "Processing" | "Indexed" | "Failed";

export interface SourceCitation {
  documentId: string;
  document: string;
  page: number;
  excerpt: string;
  relevance: number;
  semanticRank?: number | null;
  semanticScore?: number | null;
  keywordRank?: number | null;
  keywordScore?: number | null;
  rerankedPosition?: number | null;
  rerankScore?: number | null;
  rrfScore?: number | null;
}

export interface RetrievalDetails {
  rewrittenQuestion: string;
  sources: SourceCitation[];
  reranker?: string;
}

export interface AcademicDocument {
  id: string;
  name: string;
  subject: string;
  pages: number;
  size: string;
  date: string;
  status: DocumentStatus;
  chunks: number;
  type: string;
  processingProgress?: number;
  processingError?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceCitation[];
  retrievalDetails?: RetrievalDetails;
  followUpQuestions?: string[];
  timestamp: string;
  feedback?: "positive" | "negative";
}

export interface Conversation {
  id: string;
  title: string;
  updated: string;
  messages: ChatMessage[];
}

export interface User {
  name: string;
  email: string;
  avatar: string;
}

export interface AuthResponse {
  access_token: string;
  csrf_token?: string;
  user: User;
}

export interface AskResponse {
  message_id?: string;
  conversation_id?: string;
  answer: string;
  sources: SourceCitation[];
  confidence: number;
  follow_up_questions?: string[];
}
