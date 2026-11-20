import axios, { type InternalAxiosRequestConfig } from "axios";
import type {
  AcademicDocument,
  AskResponse,
  AuthResponse,
  User,
} from "../types";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";
const configuredMockMode = import.meta.env.VITE_USE_MOCKS;
export const useMocks =
  import.meta.env.MODE === "demo" ||
  (import.meta.env.MODE !== "production" &&
    (configuredMockMode
      ? configuredMockMode === "true"
      : !import.meta.env.VITE_API_BASE_URL));
export const demoCredentials = {
  email: "reader@scholar.demo",
  password: "ScholarDemo26!",
};
const tokenKey = "scholar_access_token";
let csrfToken: string | null = null;
let refreshPromise: Promise<string> | null = null;

const getAuthHeaders = (): Record<string, string> => {
  const token =
    localStorage.getItem(tokenKey) || sessionStorage.getItem(tokenKey);
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const refreshApi = axios.create({
  baseURL,
  timeout: 30000,
  withCredentials: true,
});

export const api = axios.create({
  baseURL,
  timeout: 30000,
  withCredentials: true,
});

const clearAccessTokens = () => {
  localStorage.removeItem(tokenKey);
  sessionStorage.removeItem(tokenKey);
};

const clearSession = () => {
  csrfToken = null;
  clearAccessTokens();
  window.dispatchEvent(new Event("scholar:unauthorized"));
};

class ChatRequestError extends Error {}

async function rotateAccessToken(): Promise<string> {
  if (!refreshPromise) {
    const rotate = async () => {
      const csrfResponse = await refreshApi.get<{ csrf_token: string }>(
        "/auth/csrf"
      );
      csrfToken = csrfResponse.data.csrf_token;
      const response = await refreshApi.post<{
        access_token: string;
        csrf_token: string;
      }>(
        "/auth/refresh",
        {},
        { headers: { "X-CSRF-Token": csrfToken } }
      );
      csrfToken = response.data.csrf_token;
      const token = response.data.access_token;
      if (localStorage.getItem(tokenKey)) {
        localStorage.setItem(tokenKey, token);
      } else {
        sessionStorage.setItem(tokenKey, token);
      }
      return token;
    };
    refreshPromise = (navigator.locks
      ? navigator.locks.request("academic-qa-refresh-token", rotate)
      : rotate()
    ).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

api.interceptors.request.use((config) => {
  const token =
    localStorage.getItem(tokenKey) || sessionStorage.getItem(tokenKey);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as
      | (InternalAxiosRequestConfig & { sessionRetry?: boolean })
      | undefined;
    const url = original?.url ?? "";
    const isSessionEndpoint = [
      "/auth/login",
      "/auth/register",
      "/auth/csrf",
      "/auth/refresh",
      "/auth/logout",
    ].some((endpoint) => url.includes(endpoint));
    if (
      error.response?.status === 401 &&
      original &&
      !original.sessionRetry &&
      !isSessionEndpoint
    ) {
      original.sessionRetry = true;
      try {
        const token = await rotateAccessToken();
        original.headers.Authorization = `Bearer ${token}`;
        return await api.request(original);
      } catch (refreshError) {
        clearSession();
        return Promise.reject(refreshError);
      }
    }
    if (error.response?.status === 401 && !isSessionEndpoint) {
      clearSession();
    }
    return Promise.reject(error);
  }
);

const wait = (duration = 240) =>
  new Promise((resolve) => window.setTimeout(resolve, duration));

export const authApi = {
  async login(
    email: string,
    _password: string,
    remember = true
  ): Promise<AuthResponse> {
    if (!useMocks) {
      const response = (
        await api.post<AuthResponse>("/auth/login", {
          email,
          password: _password,
          remember,
        })
      ).data;
      csrfToken = response.csrf_token ?? null;
      return response;
    }
    await wait();
    const name = email
      .split("@")[0]
      .replace(/[._-]/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
    return {
      access_token: "demo-token",
      csrf_token: "",
      user: { name: name || "Alex Morgan", email, avatar: "AM" },
    };
  },
  async register(
    name: string,
    email: string,
    _password: string
  ): Promise<AuthResponse> {
    if (!useMocks) {
      const response = (
        await api.post<AuthResponse>("/auth/register", {
          name,
          email,
          password: _password,
        })
      ).data;
      csrfToken = response.csrf_token ?? null;
      return response;
    }
    await wait();
    return {
      access_token: "demo-token",
      csrf_token: "",
      user: {
        name,
        email,
        avatar: name
          .split(" ")
          .map((part) => part[0])
          .join("")
          .slice(0, 2)
          .toUpperCase(),
      },
    };
  },
  async me(): Promise<User | null> {
    if (!localStorage.getItem(tokenKey) && !sessionStorage.getItem(tokenKey))
      return null;
    if (!useMocks) return (await api.get<User>("/auth/me")).data;
    const saved =
      localStorage.getItem("scholar_user") ||
      sessionStorage.getItem("scholar_user");
    return saved ? (JSON.parse(saved) as User) : null;
  },
  async logout() {
    try {
      if (!useMocks) {
        const csrfResponse = await refreshApi.get<{ csrf_token: string }>(
          "/auth/csrf"
        );
        csrfToken = csrfResponse.data.csrf_token;
        await refreshApi.post(
          "/auth/logout",
          {},
          { headers: { "X-CSRF-Token": csrfToken } }
        );
      }
    } finally {
      csrfToken = null;
      clearAccessTokens();
      localStorage.removeItem("scholar_user");
      sessionStorage.removeItem("scholar_user");
    }
  },
  async deleteAccount(password: string) {
    if (useMocks) {
      throw new Error("Account deletion is unavailable in demo mode.");
    }
    await api.delete("/auth/me", { data: { password } });
    csrfToken = null;
    clearAccessTokens();
    localStorage.removeItem("scholar_user");
    sessionStorage.removeItem("scholar_user");
  },
};

export const documentsApi = {
  async list(): Promise<AcademicDocument[]> {
    if (!useMocks)
      return (await api.get<AcademicDocument[]>("/documents")).data;
    const { documents } = await import("./mockData");
    await wait();
    return [...documents];
  },
  async get(id: string): Promise<AcademicDocument | undefined> {
    if (!useMocks)
      return (await api.get<AcademicDocument>(`/documents/${id}`)).data;
    const { documents } = await import("./mockData");
    await wait(100);
    return documents.find((document) => document.id === id);
  },
  async getStatus(
    id: string
  ): Promise<Pick<AcademicDocument, "id" | "status" | "processingProgress" | "processingError" | "pages" | "chunks">> {
    if (useMocks) {
      const { documents } = await import("./mockData");
      const document = documents.find((item) => item.id === id);
      if (!document) throw new Error(`Document ${id} was not found.`);
      return {
        id,
        status: document.status,
        processingProgress: document.status === "Indexed" ? 100 : 0,
        processingError: null,
        pages: document.pages,
        chunks: document.chunks,
      };
    }
    const result = (
      await api.get<{
        status: string;
        progress: number;
        processing_error: string | null;
        pages: number;
        chunks: number;
      }>(`/documents/${id}/status`)
    ).data;
    const status = result.status.toLowerCase();
    const normalizedStatus: AcademicDocument["status"] =
      status === "uploaded"
        ? "Uploaded"
        : status === "processing"
          ? "Processing"
          : status === "indexed"
            ? "Indexed"
            : status === "failed"
              ? "Failed"
              : (() => {
                  throw new Error(`Unexpected document status: ${result.status}`);
                })();
    return {
      id,
      status: normalizedStatus,
      processingProgress: result.progress,
      processingError: result.processing_error,
      pages: result.pages,
      chunks: result.chunks,
    };
  },
  async getFile(id: string): Promise<Blob> {
    if (useMocks) {
      return new Blob([], { type: "application/pdf" });
    }
    return (await api.get<Blob>(`/documents/${id}/file`, {
      responseType: "blob",
    })).data;
  },
  async upload(
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<AcademicDocument> {
    if (!useMocks) {
      const body = new FormData();
      body.append("file", file);
      return (
        await api.post<AcademicDocument>("/documents/upload", body, {
          onUploadProgress: (event) =>
            onProgress?.(
              Math.round((event.loaded / (event.total || event.loaded)) * 100)
            ),
        })
      ).data;
    }
    for (const progress of [18, 43, 68, 100]) {
      await wait(180);
      onProgress?.(progress);
    }
    return {
      id: `doc-${Date.now()}`,
      name: file.name,
      subject: "Uncategorized",
      pages: 0,
      size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
      date: "Just now",
      status: "Processing",
      chunks: 0,
      type: "PDF document",
    };
  },
  async remove(id: string) {
    if (!useMocks) await api.delete(`/documents/${id}`);
    else await wait(140);
  },
  async reprocess(id: string) {
    if (!useMocks) await api.post(`/documents/${id}/reprocess`);
    else await wait(220);
  },
};

export const chatApi = {
  async ask(
    question: string,
    conversationId?: string
  ): Promise<AskResponse & { conversation_id?: string }> {
    if (!useMocks)
      return (
        await api.post<AskResponse & { conversation_id?: string }>(
          "/chat/ask",
          { question, conversation_id: conversationId }
        )
      ).data;
    await wait(1100);
    const { mockAnswer } = await import("./mockData");
    return mockAnswer(question);
  },
  async askStream(
    question: string,
    conversationId?: string,
    onEvent?: (event: any) => void
  ): Promise<AskResponse & { conversation_id?: string }> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    Object.assign(headers, getAuthHeaders());
    const responseForToken = async () =>
      fetch(`${baseURL}/chat/ask/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ question, conversation_id: conversationId }),
      credentials: "include",
    });
    let response = await responseForToken();
    if (!useMocks && response.status === 401) {
      try {
        const token = await rotateAccessToken();
        headers.Authorization = `Bearer ${token}`;
        response = await responseForToken();
      } catch (error) {
        clearSession();
        throw error;
      }
    }
    if (!response.ok) {
      if (response.status === 401) clearSession();
      const errorPayload = await response.json().catch(() => null);
      const detail = errorPayload?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : typeof detail?.message === "string"
            ? detail.message
            : typeof errorPayload?.error?.message === "string"
              ? errorPayload.error.message
            : `Chat request failed (${response.status}).`;
      throw new ChatRequestError(message);
    }
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Streaming response not available.");
    }
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult: (AskResponse & { conversation_id?: string }) | null = null;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";
      for (const chunk of chunks) {
        const cleaned = chunk.trim();
        if (!cleaned.startsWith("data:")) continue;
        const payload = cleaned.replace(/^data:\s*/, "");
        const event = JSON.parse(payload);
        onEvent?.(event);
        if (event.type === "error") {
          throw new ChatRequestError(
            typeof event.message === "string"
              ? event.message
              : "The answer service could not complete this request."
          );
        }
        if (event.type === "final") {
          finalResult = {
            message_id: event.message_id,
            conversation_id: event.conversation_id,
            answer: event.answer,
            sources: event.sources ?? [],
            confidence: event.confidence ?? 0,
            follow_up_questions: event.follow_up_questions ?? [],
          };
        }
      }
    }
    if (!finalResult) {
      throw new Error("Streaming response ended before the final event.");
    }
    return finalResult;
  },
  async history() {
    if (!useMocks) {
      const rows = (await api.get<any[]>("/conversations")).data;
      return rows.map((item) => ({
        id: item.conversation_id,
        title: item.title,
        updated: item.updated_at,
        messages: [],
      }));
    }
    const { conversations } = await import("./mockData");
    return conversations;
  },
  async get(id: string) {
    if (!useMocks) {
      const item = (await api.get<any>(`/conversations/${id}`)).data;
      return {
        id: item.conversation_id,
        title: item.title,
        updated: item.updated_at,
        messages: (item.messages ?? []).map((message: any) => {
          return {
            id: message.message_id,
            role: message.sender_type,
            content: message.content,
            timestamp: message.created_at,
            sources: (message.citations ?? []).map((source: any) => ({
              documentId: source.document_id,
              document: source.document_name,
              page: source.page_number,
              excerpt: source.snippet,
              relevance: source.score,
            })),
          };
        }),
      };
    }
    const { conversations } = await import("./mockData");
    return conversations.find((conversation) => conversation.id === id);
  },
  async remove(id: string) {
    if (!useMocks) {
      if (/^[0-9a-f-]{36}$/i.test(id)) await api.delete(`/conversations/${id}`);
    } else await wait(120);
  },
};

export const analyticsApi = {
  async get() {
    if (!useMocks) {
      const data = (await api.get<any>("/analytics/overview")).data;
      return {
        questionsToday: data.total_questions,
        avgResponse: `${(data.average_response_time / 1000).toFixed(1)}s`,
        successRate: data.indexed_documents ? "100%" : "0%",
      };
    }
    await wait();
    return { questionsToday: 34, avgResponse: "1.8s", successRate: "96.4%" };
  },
};

export const feedbackApi = {
  async submit(messageId: string, sentiment: "positive" | "negative") {
    if (!useMocks) {
      return api.post("/feedback", {
        message_id: messageId,
        rating: sentiment,
      });
    }
    await wait(80);
  },
};

export const healthApi = {
  async get() {
    if (!useMocks) return (await api.get("/health")).data;
    await wait(80);
    return { status: "healthy" };
  },
};

export { tokenKey };
