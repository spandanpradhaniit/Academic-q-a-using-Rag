import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type DragEvent,
} from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Atom,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Database,
  FileCheck2,
  FilePlus2,
  FileSearch,
  FileText,
  Filter,
  Gauge,
  HardDrive,
  Layers3,
  Lightbulb,
  ListFilter,
  LockKeyhole,
  MessageCircle,
  Bell,
  BrainCircuit,
  LogOut,
  Menu,
  Moon,
  Plus,
  MoreHorizontal,
  PanelRightClose,
  RefreshCw,
  Search,
  Scissors,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Upload,
  Users,
  X,
  Sun,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  PageHeading,
  StatCard,
  StatusPill,
  EmptyState,
} from "../components/Shared";
import { MarkdownRenderer } from "../components/MarkdownRenderer";
import { useAuth } from "../context/AuthContext";
import {
  analyticsApi,
  chatApi,
  documentsApi,
  feedbackApi,
  healthApi,
  useMocks,
} from "../services/api";
import type {
  AcademicDocument,
  ChatMessage,
  Conversation,
  RetrievalDetails,
  SourceCitation,
} from "../types";

const questionIdeas = [
  {
    icon: Atom,
    title: "Explain a concept",
    question:
      "How does self-attention differ from recurrence in a Transformer?",
  },
  {
    icon: FileSearch,
    title: "Find a detail",
    question: "How does an operating system virtualize the CPU?",
  },
  {
    icon: Layers3,
    title: "Connect the dots",
    question: "What do my documents say about memory and attention?",
  },
];

const SubjectDistributionChart = lazy(() =>
  import("../components/SubjectDistributionChart").then((module) => ({
    default: module.SubjectDistributionChart,
  }))
);

function useLibraryDocuments() {
  const [documents, setDocuments] = useState<AcademicDocument[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!useMocks);

  useEffect(() => {
    let active = true;
    documentsApi
      .list()
      .then((items) => {
        if (active) {
          setDocuments(items);
          setLoadError(null);
          setLoading(false);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setLoadError(
            error instanceof Error
              ? error.message
              : "Could not load your documents."
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return { documents, setDocuments, loadError, loading };
}

function useAnalyticsSummary() {
  const [summary, setSummary] = useState<Awaited<
    ReturnType<typeof analyticsApi.get>
  > | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    analyticsApi
      .get()
      .then((data) => {
        if (active) {
          setSummary(data);
          setLoadError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setLoadError(
            error instanceof Error
              ? error.message
              : "Could not load analytics."
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return { summary, loadError };
}

function getConversationPeriod(updated: string) {
  if (updated === "Just now" || updated === "Today") return "Today";
  if (updated === "Yesterday") return "Yesterday";

  const date = new Date(updated);
  if (Number.isNaN(date.getTime())) return "Earlier";

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  date.setHours(0, 0, 0, 0);
  const daysAgo = Math.floor((today.getTime() - date.getTime()) / 86_400_000);
  if (daysAgo <= 0) return "Today";
  if (daysAgo === 1) return "Yesterday";
  if (daysAgo < 7) return "Previous 7 days";
  return "Earlier";
}

function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  useEffect(() => {
    const timeout = window.setTimeout(onClose, 3000);
    return () => window.clearTimeout(timeout);
  }, [onClose]);
  return (
    <motion.div
      className="toast-message"
      role="status"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
    >
      <Check size={15} />
      {message}
      <button aria-label="Dismiss notification" onClick={onClose}>
        <X size={14} />
      </button>
    </motion.div>
  );
}

function DocumentRow({
  document,
  onOpen,
  onRetry,
  selected,
  onSelect,
}: {
  document: AcademicDocument;
  onOpen: () => void;
  onRetry?: () => void;
  selected?: boolean;
  onSelect?: () => void;
}) {
  return (
    <tr>
      <td className="document-name-cell">
        {onSelect && (
          <input
            type="checkbox"
            aria-label={`Select ${document.name}`}
            checked={selected}
            onChange={onSelect}
          />
        )}
        <span className="pdf-icon">
          <FileText size={16} />
        </span>
        <button className="document-name-button" onClick={onOpen}>
          <b>{document.name}</b>
          <small>{document.type}</small>
        </button>
      </td>
      <td>{document.subject}</td>
      <td>{document.pages || "—"}</td>
      <td>{document.date}</td>
      <td>
        <StatusPill status={document.status} />
        {(document.status === "Processing" ||
          document.status === "Uploaded") && (
          <div
            className="document-processing-progress"
            aria-label={`${document.name} processing status`}
          >
            {document.status === "Processing" &&
            document.processingProgress !== undefined ? (
              <>
                <span>
                  <i style={{ width: `${document.processingProgress}%` }} />
                </span>
                <small>
                  {document.processingProgress > 0
                    ? `Indexing pages · ${document.processingProgress}%`
                    : "Preparing document…"}
                </small>
              </>
            ) : (
              <small>Waiting to be processed…</small>
            )}
          </div>
        )}
      </td>
      <td className="row-menu-cell">
        <span
          className={`index-indicator ${
            document.status === "Indexed" ? "is-indexed" : ""
          }`}
        >
          <i />
          {document.status === "Indexed"
            ? "Indexed"
            : document.status === "Processing"
            ? "In queue"
            : document.status === "Failed"
            ? "Needs attention"
            : document.status === "Uploaded"
            ? "Queued"
            : "Waiting"}
        </span>
        {document.status === "Failed" && (
          <div className="document-processing-error">
            <small>{document.processingError || "Processing failed."}</small>
            <button
              type="button"
              className="document-retry-button"
              onClick={onRetry}
              aria-label={`Retry processing ${document.name}`}
            >
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        )}
        <button
          className="icon-button row-more"
          aria-label={`More actions for ${document.name}`}
          onClick={() =>
            document.status === "Failed" ? onRetry?.() : onOpen()
          }
        >
          <MoreHorizontal size={17} />
        </button>
      </td>
    </tr>
  );
}

function ChatMessageView({
  message,
  onFeedback,
  onCopy,
  onAskFollowUp,
  onUploadDocuments,
  isStreaming,
}: {
  message: ChatMessage;
  onFeedback: (id: string, value: "positive" | "negative") => void;
  onCopy: (text: string) => void;
  onAskFollowUp: (question: string) => void;
  onUploadDocuments: () => void;
  isStreaming?: boolean;
}) {
  const [showAdvancedScores, setShowAdvancedScores] = useState(false);
  const { user } = useAuth();
  const isAssistant = message.role === "assistant";
  const userInitials =
    user?.name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() ?? "You";
  return (
    <article
      className={`chat-message ${
        isAssistant ? "assistant-message" : "user-message"
      }`}
    >
      <span
        className={`message-avatar ${isAssistant ? "assistant-avatar" : ""}`}
        aria-hidden="true"
      >
        {isAssistant ? <BookOpen size={16} /> : userInitials}
      </span>
      <div className="message-body">
        <div className="message-meta">
          <b>{isAssistant ? "Scholar" : "You"}</b>
          <span>{message.timestamp}</span>
          {isAssistant && (
            <span className="grounded-label">
              <ShieldCheck size={12} /> Source-grounded
            </span>
          )}
        </div>
        <div
          className="markdown-content"
          aria-live={isStreaming ? "off" : undefined}
        >
          <MarkdownRenderer content={message.content} />
          {isStreaming && (
            <>
              <span className="streaming-cursor" aria-hidden="true" />
              <span className="sr-only" role="status">
                Scholar is writing an answer.
              </span>
            </>
          )}
        </div>
        {isAssistant &&
          message.content ===
            "Information not found in the provided documents." && (
            <div className="not-found-callout">
              <b>No relevant passage found</b>
              <span>
                Try rephrasing your question or add course materials that cover
                this topic.
              </span>
              <button type="button" onClick={onUploadDocuments}>
                <Upload size={12} /> Upload documents
              </button>
            </div>
          )}
        {isAssistant &&
          message.sources?.map((source) => (
            <SourceCard
              source={source}
              compact
              key={`${source.documentId}-${source.page}`}
            />
          ))}
        {isAssistant && !isStreaming && !!message.followUpQuestions?.length && (
          <div
            className="follow-up-questions"
            aria-label="Suggested follow-up questions"
          >
            <span>Continue exploring</span>
            {message.followUpQuestions.map((followUp) => (
              <button
                key={followUp}
                type="button"
                onClick={() => onAskFollowUp(followUp)}
              >
                {followUp}
              </button>
            ))}
          </div>
        )}
        {isAssistant && message.retrievalDetails && (
          <details className="generation-details">
            <summary>How this answer was generated</summary>
            <div className="generation-details-content">
              <div>
                <b>Search question</b>
                <p>{message.retrievalDetails.rewrittenQuestion}</p>
              </div>
              {message.retrievalDetails.sources.length > 0 ? (
                <ol>
                  {message.retrievalDetails.sources.map((source) => (
                    <li key={`${source.documentId}-${source.page}`}>
                      <span>
                        {source.document}, p. {source.page}
                      </span>
                      <small>
                        Semantic rank: {source.semanticRank ?? "—"} · Keyword
                        rank: {source.keywordRank ?? "—"} · Final position:{" "}
                        {source.rerankedPosition ?? "—"}
                      </small>
                      {showAdvancedScores && (
                        <small className="retrieval-debug-scores">
                          Scores — semantic: {source.semanticScore ?? "—"} ·
                          keyword: {source.keywordScore ?? "—"} · RRF:{" "}
                          {source.rrfScore ?? "—"} · reranker:{" "}
                          {source.rerankScore ?? "—"}
                        </small>
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p>No source passages passed the relevance check.</p>
              )}
              <button
                className="retrieval-debug-toggle"
                type="button"
                onClick={() => setShowAdvancedScores((current) => !current)}
              >
                {showAdvancedScores
                  ? "Hide advanced scores"
                  : "Show advanced scores"}
              </button>
            </div>
          </details>
        )}
        {isAssistant && (
          <div className="message-toolbar">
            <button
              title="Copy answer"
              aria-label="Copy answer"
              onClick={() => onCopy(message.content)}
            >
              <Copy size={13} />
            </button>
            <span className="toolbar-divider" />
            <button
              className={
                message.feedback === "positive" ? "feedback-active" : ""
              }
              aria-label="Helpful answer"
              title="Helpful"
              onClick={() => onFeedback(message.id, "positive")}
            >
              <ThumbsUp size={13} />
            </button>
            <button
              className={
                message.feedback === "negative" ? "feedback-active" : ""
              }
              aria-label="Not helpful"
              title="Not helpful"
              onClick={() => onFeedback(message.id, "negative")}
            >
              <ThumbsDown size={13} />
            </button>
            <button
              onClick={() =>
                onAskFollowUp("Can you explain this in more detail?")
              }
            >
              <MessageCircle size={13} />
              <span>Ask a follow-up</span>
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

function SourceCard({
  source,
  compact = false,
  onOpen,
}: {
  source: SourceCitation;
  compact?: boolean;
  onOpen?: () => void;
}) {
  return (
    <article
      className={`source-card ${compact ? "source-card-compact" : ""}`}
      onClick={onOpen}
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onKeyDown={
        onOpen
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onOpen();
              }
            }
          : undefined
      }
    >
      <div className="source-file-icon">
        <FileText size={15} />
      </div>
      <div className="source-card-body">
        <div className="source-card-title">
          <b>{source.document}</b>
          <span>p. {source.page}</span>
        </div>
        <p>{source.excerpt}</p>
        <div className="source-relevance">
          <span className="relevance-track">
            <i style={{ width: `${source.relevance}%` }} />
          </span>
          <small>{source.relevance}% relevant</small>
        </div>
      </div>
    </article>
  );
}

function PdfViewerModal({
  source,
  onClose,
}: {
  source: SourceCitation | null;
  onClose: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!source) return;

    let cancelled = false;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    closeButtonRef.current?.focus();
    setLoading(true);
    setError(null);

    const renderPage = async () => {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url
        ).toString();
        const blob = await documentsApi.getFile(source.documentId);
        const bytes = await blob.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: bytes });
        const pdf = await loadingTask.promise;
        const page = await pdf.getPage(source.page || 1);
        const viewport = page.getViewport({ scale: 1.2 });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        const context = canvas.getContext("2d");
        if (!context) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const renderContext = {
          canvas,
          canvasContext: context,
          viewport,
        };
        await page.render(renderContext).promise;
      } catch {
        if (!cancelled) {
          setError("The PDF preview could not be loaded.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    renderPage();
    return () => {
      cancelled = true;
      previousFocus?.focus();
    };
  }, [source]);

  if (!source) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-preview-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onClose();
        } else if (event.key === "Tab") {
          event.preventDefault();
          closeButtonRef.current?.focus();
        }
      }}
    >
      <div className="modal-panel pdf-modal">
        <div className="modal-header">
          <div>
            <span className="page-eyebrow">SOURCE PREVIEW</span>
            <h3 id="source-preview-title">{source.document}</h3>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close source preview"
            ref={closeButtonRef}
          >
            <X size={16} />
          </button>
        </div>
        <div className="pdf-preview-meta">
          <span>Page {source.page}</span>
          <span>{source.relevance}% relevant</span>
        </div>
        <div className="pdf-viewer-wrap">
          {loading && <div className="pdf-loading">Loading PDF…</div>}
          {error && (
            <div className="pdf-error" role="alert">
              {error}
            </div>
          )}
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={`Page ${source.page} from ${source.document}`}
          />
          <div className="pdf-snippet-highlight">{source.excerpt}</div>
        </div>
      </div>
    </div>
  );
}

function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { documents, loadError, loading } = useLibraryDocuments();
  const { summary: stats, loadError: analyticsError } = useAnalyticsSummary();
  const firstName = user?.name.trim().split(/\s+/)[0] || "there";
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const today = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  })
    .format(new Date())
    .toUpperCase();
  const indexedDocuments = documents.filter(
    (document) => document.status === "Indexed"
  ).length;
  const indexedChunks = documents.reduce(
    (total, document) =>
      total + (document.status === "Indexed" ? document.chunks : 0),
    0
  );
  return (
    <div className="dashboard-page">
      <PageHeading
        eyebrow={today}
        title={`${greeting}, ${firstName}`}
        description="A clear view of what you've been learning."
        actions={
          <>
            <button
              className="button button-secondary"
              onClick={() => navigate("/app/documents?upload=1")}
            >
              <Upload size={15} /> Upload documents
            </button>
            <button
              className="button button-primary"
              onClick={() => navigate("/app/chat")}
            >
              <Sparkles size={15} /> Ask Scholar
            </button>
          </>
        }
      />
      {loadError && (
        <div className="document-load-error" role="alert">
          Could not load your library data: {loadError}
        </div>
      )}
      {analyticsError && (
        <div className="document-load-error" role="alert">
          Could not load analytics: {analyticsError}
        </div>
      )}
      <div className="stats-grid">
        <StatCard
          label="Documents in library"
          value={loading || loadError ? "—" : String(documents.length)}
          change="Your uploaded materials"
          icon={FileText}
          tone="blue"
        />
        <StatCard
          label="Ready to search"
          value={loading || loadError ? "—" : String(indexedDocuments)}
          change="Indexed documents"
          icon={FileCheck2}
          tone="green"
        />
        <StatCard
          label="Questions asked"
          value={stats ? String(stats.questionsToday) : "—"}
          change="Across your conversations"
          icon={MessageCircle}
          tone="violet"
        />
        <StatCard
          label="Knowledge indexed"
          value={loading || loadError ? "—" : indexedChunks.toLocaleString()}
          change="Indexed passages"
          icon={Database}
          tone="orange"
        />
      </div>
      <div className="dashboard-grid">
        <section className="dashboard-card usage-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">YOUR RESEARCH, IN FOCUS</span>
              <h2>Study activity</h2>
            </div>
          </div>
          <div className="dashboard-empty-state">
            <EmptyState
              icon={Activity}
              title="Activity history isn't available yet"
              text="Your analytics service currently provides totals, not a daily activity series."
            />
          </div>
          <div className="chart-footer">
            <button onClick={() => navigate("/app/analytics")}>
              View analytics <ArrowRight size={13} />
            </button>
          </div>
        </section>
        <section className="dashboard-card topics-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">WHAT YOU'RE EXPLORING</span>
              <h2>Popular topics</h2>
            </div>
            <button
              className="icon-button"
              aria-label="Explore analytics"
              onClick={() => navigate("/app/analytics")}
            >
              <ArrowUpRight size={16} />
            </button>
          </div>
          <div className="dashboard-empty-state">
            <EmptyState
              icon={MessageCircle}
              title="No topic insights yet"
              text="Topic summaries will appear when the analytics service provides them."
            />
          </div>
        </section>
      </div>
      <section className="dashboard-card recent-documents">
        <div className="card-heading">
          <div>
            <span className="card-kicker">YOUR KNOWLEDGE BASE</span>
            <h2>Recently added</h2>
          </div>
          <button
            className="text-link"
            onClick={() => navigate("/app/documents")}
          >
            All documents <ArrowRight size={13} />
          </button>
        </div>
        <div className="recent-doc-grid">
          {!loading && !loadError && documents.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No documents yet"
              text="Upload a PDF to start building your research library."
              action={
                <button
                  className="button button-secondary button-sm"
                  onClick={() => navigate("/app/documents?upload=1")}
                >
                  <Upload size={14} /> Upload a document
                </button>
              }
            />
          ) : loadError ? (
            <EmptyState
              icon={FileText}
              title="Documents unavailable"
              text="Your recent documents could not be loaded."
            />
          ) : loading ? (
            <div className="chart-loading" role="status">
              Loading documents…
            </div>
          ) : (
            documents.slice(0, 3).map((document) => (
              <button
                className="recent-doc-item"
                key={document.id}
                onClick={() => navigate(`/app/documents/${document.id}`)}
              >
                <span className="pdf-icon">
                  <FileText size={17} />
                </span>
                <span className="recent-doc-copy">
                  <b>{document.name}</b>
                  <small>
                    {document.subject} <i>·</i> {document.pages} pages
                  </small>
                </span>
                <StatusPill status={document.status} />
                <ArrowRight className="recent-doc-arrow" size={15} />
              </button>
            ))
          )}
        </div>
      </section>
      <div className="dashboard-bottom">
        <div className="insight-banner">
          <span className="insight-icon">
            <Lightbulb size={18} />
          </span>
          <div>
            <b>
              {documents.length
                ? "Your library is ready to explore"
                : "Start with your first source"}
            </b>
            <p>
              {documents.length
                ? `${documents.length} documents and ${indexedChunks.toLocaleString()} indexed passages are in your library.`
                : "Upload a PDF to ask questions grounded in your own reading."}
            </p>
          </div>
          <button
            onClick={() => {
              navigate(
                documents.length ? "/app/chat" : "/app/documents?upload=1"
              );
            }}
            aria-label={
              documents.length ? "Ask about your library" : "Upload a document"
            }
          >
            {documents.length ? (
              <ArrowRight size={17} />
            ) : (
              <Upload size={16} />
            )}
          </button>
        </div>
        <div className="response-kpi">
          <span className="response-icon">
            <Zap size={17} />
          </span>
          <div>
            <span>AVERAGE RESPONSE</span>
            <b>{stats?.avgResponse || "—"}</b>
            <small>
              {stats ? "From your analytics overview" : "Waiting for analytics"}
            </small>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatPage({ onToast }: { onToast: (message: string) => void }) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [history, setHistory] = useState<Conversation[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [chatSearch, setChatSearch] = useState("");
  const [selectedConversation, setSelectedConversation] = useState("");
  const [typing, setTyping] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(
    null
  );
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const [selectedSource, setSelectedSource] = useState<SourceCitation | null>(
    null
  );
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    let active = true;
    async function loadHistory() {
      try {
        const items = await chatApi.history();
        if (!active) return;
        setHistory(items);
        setHistoryError(null);
        if (items.length) {
          setSelectedConversation(items[0].id);
          if (items[0].messages.length) setMessages(items[0].messages);
          else if (
            !items[0].id.startsWith("local-")
          ) {
            try {
              const conversation = await chatApi.get(items[0].id);
              if (active) setMessages(conversation?.messages ?? []);
            } catch (error) {
              if (active) {
                setHistoryError(
                  error instanceof Error
                    ? error.message
                    : "Could not load this conversation."
                );
              }
            }
          }
        }
      } catch (error) {
        if (active) {
          setHistoryError(
            error instanceof Error
              ? error.message
              : "Could not load your conversations."
          );
        }
      } finally {
        if (active) setHistoryLoading(false);
      }
    }
    void loadHistory();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (searchParams.get("new")) {
      startNew();
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  useEffect(() => {
    if (!historyOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setHistoryOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [historyOpen]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, typing]);
  function startNew() {
    const id = `local-${Date.now()}`;
    setHistoryError(null);
    setHistoryOpen(false);
    setHistory((current) => [
      { id, title: "New conversation", updated: "Just now", messages: [] },
      ...current,
    ]);
    setSelectedConversation(id);
    setMessages([]);
    setTimeout(() => inputRef.current?.focus(), 60);
  }

  function selectConversation(conversation: Conversation) {
    setHistoryOpen(false);
    setHistoryError(null);
    setSelectedConversation(conversation.id);
    if (
      conversation.messages.length ||
      conversation.id.startsWith("local-")
    ) {
      setMessages(conversation.messages);
    } else {
      chatApi
        .get(conversation.id)
        .then((item) => setMessages(item?.messages ?? []))
        .catch((error: unknown) => {
          setHistoryError(
            error instanceof Error
              ? error.message
              : "Could not load this conversation."
          );
        });
    }
  }

  async function sendMessage(
    value = question,
    baseMessages = messages,
    includeUser = true
  ) {
    const content = value.trim();
    if (!content || typing) return;
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      }),
    };
    const nextMessages = includeUser
      ? [...baseMessages, userMessage]
      : baseMessages;
    setMessages(nextMessages);
    setQuestion("");
    setTyping(true);
    setHistory((current) =>
      current.map((conversation) =>
        conversation.id === selectedConversation
          ? {
              ...conversation,
              title:
                conversation.title === "New conversation"
                  ? content.slice(0, 34)
                  : conversation.title,
              updated: "Just now",
              messages: nextMessages,
            }
          : conversation
      )
    );
    const assistantId = `msg-${Date.now()}`;
    try {
      const wasLocalConversation =
        !selectedConversation || selectedConversation.startsWith("local-");
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        sources: [],
        timestamp: new Date().toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
        }),
      };
      setMessages((current) => [...current, assistantMessage]);
      setStreamingMessageId(assistantId);
      setHistory((current) =>
        current.map((conversation) =>
          conversation.id === selectedConversation
            ? {
                ...conversation,
                messages: [...nextMessages, assistantMessage],
              }
            : conversation
        )
      );
      let retrievalDetails: RetrievalDetails | undefined;
      const result = await chatApi.askStream(
        content,
        wasLocalConversation ? undefined : selectedConversation,
        (event) => {
          if (event?.type === "meta") {
            const retrievalSources: SourceCitation[] = (
              event.sources ?? []
            ).map((source: Record<string, unknown>) => ({
              documentId: String(source.documentId ?? source.document_id ?? ""),
              document: String(source.document ?? source.document_name ?? ""),
              page: Number(source.page ?? source.page_number ?? 0),
              excerpt: String(source.excerpt ?? source.snippet ?? ""),
              relevance: Number(source.relevance ?? source.score ?? 0),
              semanticRank: source.semanticRank as number | null | undefined,
              semanticScore: source.semanticScore as number | null | undefined,
              keywordRank: source.keywordRank as number | null | undefined,
              keywordScore: source.keywordScore as number | null | undefined,
              rerankedPosition: source.rerankedPosition as
                | number
                | null
                | undefined,
              rerankScore: source.rerankScore as number | null | undefined,
              rrfScore: source.rrfScore as number | null | undefined,
            }));
            retrievalDetails = {
              rewrittenQuestion:
                event.rewritten_question ??
                event.retrieval_metadata?.rewritten_question ??
                content,
              sources: retrievalSources,
              reranker: event.retrieval_metadata?.reranker,
            };
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      sources: retrievalSources,
                      retrievalDetails,
                    }
                  : message
              )
            );
            return;
          }
          if (event?.type === "token") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: (message.content ?? "") + (event.token ?? ""),
                    }
                  : message
              )
            );
            return;
          }
          if (event?.type === "final") {
            const finalAnswer: ChatMessage = {
              id: event.message_id ?? assistantId,
              role: "assistant",
              content: event.answer ?? "",
              sources: event.sources ?? [],
              retrievalDetails,
              followUpQuestions: event.follow_up_questions ?? [],
              timestamp: new Date().toLocaleTimeString([], {
                hour: "numeric",
                minute: "2-digit",
              }),
            };
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId ? finalAnswer : message
              )
            );
            setHistory((current) =>
              current.map((conversation) =>
                conversation.id === selectedConversation ||
                conversation.id === event.conversation_id
                  ? {
                      ...conversation,
                      messages: [...nextMessages, finalAnswer],
                    }
                  : conversation
              )
            );
            if (event.conversation_id && wasLocalConversation) {
              setSelectedConversation(event.conversation_id);
            }
            setStreamingMessageId(null);
          }
        }
      );
      if (result?.conversation_id && wasLocalConversation) {
        setSelectedConversation(result.conversation_id);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error && !(error instanceof TypeError)
          ? error.message
          : "I could not connect to the chat API. Check that the backend is running and the API URL is correct.";
      const failedAssistant: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: errorMessage,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
        }),
      };
      setStreamingMessageId(null);
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId ? failedAssistant : message
        )
      );
      setHistory((current) =>
        current.map((conversation) =>
          conversation.id === selectedConversation
            ? { ...conversation, messages: [...nextMessages, failedAssistant] }
            : conversation
        )
      );
    } finally {
      setTyping(false);
    }
  }

  function clearCurrentChat() {
    setMessages([]);
    setHistory((current) =>
      current.map((conversation) =>
        conversation.id === selectedConversation
          ? { ...conversation, title: "New conversation", messages: [] }
          : conversation
      )
    );
    setStreamingMessageId(null);
    onToast("Conversation cleared.");
  }

  function regenerateLastAnswer() {
    const lastUserIndex = messages
      .map((message) => message.role)
      .lastIndexOf("user");
    if (lastUserIndex < 0) return;
    const previousMessages = messages.slice(0, lastUserIndex + 1);
    const lastQuestion = messages[lastUserIndex].content;
    setMessages(previousMessages);
    void sendMessage(lastQuestion, previousMessages, false);
  }

  async function giveFeedback(id: string, value: "positive" | "negative") {
    try {
      await feedbackApi.submit(id, value);
    } catch {
      onToast("Could not send feedback. Please try again.");
      return;
    }
    setMessages((current) =>
      current.map((message) =>
        message.id === id ? { ...message, feedback: value } : message
      )
    );
    onToast(
      value === "positive"
        ? "Thanks for the feedback."
        : "Thanks. We’ll use this to improve grounded answers."
    );
  }

  async function removeConversation(conversation: Conversation) {
    try {
      await chatApi.remove(conversation.id);
    } catch (error) {
      onToast(
        error instanceof Error
          ? `Could not delete conversation: ${error.message}`
          : "Could not delete conversation. Please try again."
      );
      return;
    }
    const next = history.filter((item) => item.id !== conversation.id);
    setHistory(next);
    setMenuFor(null);
    if (selectedConversation === conversation.id) {
      const active = next[0];
      setSelectedConversation(active?.id ?? "");
      setMessages(active?.messages ?? []);
    }
    onToast("Conversation deleted.");
  }

  const latestSources =
    [...messages].reverse().find((message) => message.role === "assistant")
      ?.sources ?? [];
  const filteredHistory = history.filter((conversation) =>
    conversation.title.toLowerCase().includes(chatSearch.toLowerCase())
  );
  const canAsk = messages.length === 0;
  const historyPeriods = ["Today", "Yesterday", "Previous 7 days", "Earlier"];

  return (
    <div className={`chat-workspace ${sourcesOpen ? "" : "sources-hidden"}`}>
      {historyOpen && (
        <button
          className="chat-history-backdrop"
          aria-label="Close conversation history"
          onClick={() => setHistoryOpen(false)}
        />
      )}
      <aside
        className={`chat-history ${historyOpen ? "mobile-open" : ""}`}
        aria-label="Conversation history"
      >
        <div className="chat-history-head">
          <div>
            <span className="chat-workspace-label">ACADEMIC ASSISTANT</span>
            <h2>Conversations</h2>
          </div>
          <button
            className="icon-button"
            title="New conversation"
            aria-label="New conversation"
            onClick={startNew}
          >
            <FilePlus2 size={16} />
          </button>
        </div>
        <div className="chat-search">
          <Search size={14} />
          <input
            aria-label="Search conversations"
            placeholder="Search chats"
            value={chatSearch}
            onChange={(event) => setChatSearch(event.target.value)}
          />
        </div>
        <button className="chat-new-button" onClick={startNew}>
          <span>
            <Plus size={15} />
          </span>{" "}
          New conversation
        </button>
        <div className="history-list">
          {historyError && (
            <div className="document-load-error" role="alert">
              Could not load conversations: {historyError}
            </div>
          )}
          {historyPeriods.map((period) => {
            const items = filteredHistory.filter((item) =>
              getConversationPeriod(item.updated) === period
            );
            return (
              items.length > 0 ? (
                <div key={period} className="history-group">
                  <span className="history-period">{period}</span>
                  {items.map((conversation) => (
                    <div
                      className={`history-item ${
                        conversation.id === selectedConversation
                          ? "selected"
                          : ""
                      }`}
                      key={conversation.id}
                    >
                      <button
                        onClick={() => selectConversation(conversation)}
                        title={conversation.title}
                      >
                        <span className="history-item-dot" />
                        {conversation.title}
                      </button>
                      <button
                        className="history-more"
                        aria-label={`Actions for ${conversation.title}`}
                        onClick={() =>
                          setMenuFor(
                            menuFor === conversation.id ? null : conversation.id
                          )
                        }
                      >
                        <MoreHorizontal size={15} />
                      </button>
                      {menuFor === conversation.id && (
                        <div className="conversation-menu">
                          <button
                            onClick={() => {
                              const title = window.prompt(
                                "Rename conversation",
                                conversation.title
                              );
                              if (title?.trim())
                                setHistory((current) =>
                                  current.map((item) =>
                                    item.id === conversation.id
                                      ? { ...item, title: title.trim() }
                                      : item
                                  )
                                );
                              setMenuFor(null);
                            }}
                          >
                            Rename
                          </button>
                          <button
                            className="danger-menu-item"
                            onClick={() =>
                              void removeConversation(conversation)
                            }
                          >
                            Delete conversation
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : null
            );
          })}
          {historyLoading ? (
            <p className="history-empty" role="status">
              Loading conversations…
            </p>
          ) : (
            filteredHistory.length === 0 && (
              <p className="history-empty">
                {chatSearch
                  ? "No matching conversations."
                  : "Your conversations will appear here."}
              </p>
            )
          )}
        </div>
        <div className="history-plan">
          <span className="plan-icon">
            <Sparkles size={14} />
          </span>
          <div>
            <b>Research workspace</b>
            <small>Private sources and conversations</small>
          </div>
          <ChevronDown size={14} />
        </div>
      </aside>
      <section className="chat-main">
        <div className="chat-toolbar">
          <div>
            <button
              className="chat-history-toggle"
              aria-expanded={historyOpen}
              aria-label={
                historyOpen ? "Close conversation history" : "Open conversation history"
              }
              onClick={() => setHistoryOpen(!historyOpen)}
            >
              <Menu size={14} />
              <span>Chats</span>
            </button>
            <span className="chat-context-dot" />
            <span>All documents</span>
            <ChevronDown size={13} />
          </div>
          <div className="chat-toolbar-actions">
            {messages.some((message) => message.role === "assistant") && (
              <>
                <button
                  className="chat-source-toggle"
                  onClick={regenerateLastAnswer}
                  disabled={typing}
                  aria-label="Regenerate last answer"
                  title="Regenerate last answer"
                >
                  <RefreshCw size={14} /> <span>Regenerate</span>
                </button>
                <button
                  className="chat-source-toggle"
                  onClick={clearCurrentChat}
                  disabled={typing}
                  aria-label="Clear conversation"
                  title="Clear conversation"
                >
                  <Trash2 size={14} /> <span>Clear</span>
                </button>
              </>
            )}
            <button
              className="chat-source-toggle"
              onClick={() => setSourcesOpen(!sourcesOpen)}
              aria-label={
                sourcesOpen ? "Hide sources panel" : "Show sources panel"
              }
              title={sourcesOpen ? "Hide sources" : "Show sources"}
            >
              <PanelRightClose size={16} /> <span>Sources</span>
            </button>
          </div>
        </div>
        <div className={`chat-messages ${canAsk ? "chat-empty-messages" : ""}`}>
          {canAsk ? (
            <div className="chat-welcome">
              <span className="welcome-orbit">
                <span />
                <Sparkles size={21} />
              </span>
              <span className="chat-welcome-kicker">
                A LITTLE MORE CLARITY, A LOT LESS HUNTING
              </span>
              <h1>
                What are you trying
                <br />
                to <em>understand?</em>
              </h1>
              <p>
                Ask a question about your research. Answers are only as good as
                the sources behind them.
              </p>
              <div className="suggestion-grid">
                {questionIdeas.map(
                  ({ icon: Icon, title, question: prompt }) => (
                    <button
                      className="suggestion-card"
                      key={title}
                      onClick={() => void sendMessage(prompt)}
                    >
                      <span>
                        <Icon size={16} />
                      </span>
                      <b>{title}</b>
                      <small>{prompt}</small>
                      <ArrowUpRight size={14} className="suggestion-arrow" />
                    </button>
                  )
                )}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message) => (
                <ChatMessageView
                  key={message.id}
                  message={message}
                  isStreaming={streamingMessageId === message.id}
                  onFeedback={giveFeedback}
                  onCopy={(text) => {
                    void navigator.clipboard?.writeText(text);
                    onToast("Answer copied to clipboard.");
                  }}
                  onAskFollowUp={(followUp) => {
                    setQuestion(followUp);
                    inputRef.current?.focus();
                  }}
                  onUploadDocuments={() => navigate("/app/documents?upload=1")}
                />
              ))}
              {typing && (
                <div className="typing-row">
                  <span className="message-avatar assistant-avatar">
                    <BookOpen size={16} />
                  </span>
                  <div>
                    <b>Scholar is checking your sources</b>
                    <div className="typing-indicator">
                      <i />
                      <i />
                      <i />
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
        <div className="chat-composer-wrap">
          <form
            className="chat-composer"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              void sendMessage();
            }}
          >
            <textarea
              ref={inputRef}
              rows={1}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about your documents..."
              aria-label="Your question"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
            />
            <div className="composer-footer">
              <div>
                <span className="composer-security">
                  <ShieldCheck size={12} /> Answers cite your sources
                </span>
                <span className="composer-divider" />
                <button
                  type="button"
                  className="source-scope"
                  onClick={() => onToast("Searching all 21 indexed documents.")}
                >
                  <FileText size={12} /> All indexed sources{" "}
                  <ChevronDown size={12} />
                </button>
              </div>
              <div>
                <span className="composer-shortcut">↵ to ask</span>
                <button
                  className="send-button"
                  type="submit"
                  disabled={!question.trim() || typing}
                  aria-label="Send question"
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          </form>
          <div className="composer-disclaimer">
            Scholar can make mistakes. Verify every important claim against the
            source.
          </div>
        </div>
      </section>
      <aside className={`sources-panel ${sourcesOpen ? "" : "closed"}`}>
        <div className="sources-heading">
          <div>
            <span className="page-eyebrow">RETRIEVAL CONTEXT</span>
            <h2>
              Sources <span>{latestSources.length}</span>
            </h2>
          </div>
          <button
            className="icon-button"
            title="Close sources panel"
            aria-label="Close sources panel"
            onClick={() => setSourcesOpen(false)}
          >
            <X size={16} />
          </button>
        </div>
        <p className="sources-intro">
          {latestSources.length
            ? "Passages that support the latest answer."
            : "The passages supporting each answer will appear here."}
        </p>
        {latestSources.length ? (
          <div className="source-results">
            {latestSources.map((source, index) => (
              <div
                className="source-result"
                key={`${source.documentId}-${source.page}`}
              >
                <span className="source-number">{index + 1}</span>
                <SourceCard
                  source={source}
                  onOpen={() => setSelectedSource(source)}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="sources-empty">
            <span>
              <FileSearch size={18} />
            </span>
            <b>No sources yet</b>
            <p>Ask a question to see matching documents and passages.</p>
          </div>
        )}
        <div className="retrieval-note">
          <ShieldCheck size={14} />
          <span>
            <b>Evidence before answers</b>
            <small>
              Responses without a relevant passage are identified clearly.
            </small>
          </span>
        </div>
      </aside>
      <PdfViewerModal
        source={selectedSource}
        onClose={() => setSelectedSource(null)}
      />
    </div>
  );
}

function DocumentsPage({ onToast }: { onToast: (message: string) => void }) {
  const { documents, setDocuments, loadError } = useLibraryDocuments();
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [category, setCategory] = useState("All subjects");
  const [status, setStatus] = useState("All statuses");
  const [sort, setSort] = useState("Recently added");
  const [selected, setSelected] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentUploadName, setCurrentUploadName] = useState("");
  const [uploadFailures, setUploadFailures] = useState<
    { file: File; error: string }[]
  >([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const subjects = [
    "All subjects",
    ...new Set(documents.map((document) => document.subject)),
  ];
  const filtered = useMemo(
    () =>
      documents
        .filter(
          (document) =>
            document.name.toLowerCase().includes(search.toLowerCase()) &&
            (category === "All subjects" || document.subject === category) &&
            (status === "All statuses" || document.status === status)
        )
        .sort((left, right) =>
          sort === "Name A–Z" ? left.name.localeCompare(right.name) : 0
        ),
    [documents, search, category, status, sort]
  );

  useEffect(() => {
    if (searchParams.get("upload") === "1") fileInputRef.current?.click();
  }, [searchParams]);

  useEffect(() => {
    if (
      !documents.some((document) =>
        ["Uploaded", "Processing"].includes(document.status)
      )
    ) {
      return;
    }
    let cancelled = false;
    const refreshStatuses = async () => {
      const pending = documents.filter((document) =>
        ["Uploaded", "Processing"].includes(document.status)
      );
      const results = await Promise.allSettled(
        pending.map((document) => documentsApi.getStatus(document.id))
      );
      if (cancelled) return;
      const updates = new Map(
        results.flatMap((result) =>
          result.status === "fulfilled"
            ? [[result.value.id, result.value] as const]
            : []
        )
      );
      setDocuments((current) => {
        let changed = false;
        const refreshed = current.map((document) => {
          const update = updates.get(document.id);
          if (!update) return document;
          const merged = { ...document, ...update };
          if (
            merged.status === document.status &&
            merged.processingProgress === document.processingProgress &&
            merged.processingError === document.processingError &&
            merged.pages === document.pages &&
            merged.chunks === document.chunks
          ) {
            return document;
          }
          changed = true;
          return merged;
        });
        return changed ? refreshed : current;
      });
    };
    void refreshStatuses();
    const timer = window.setInterval(() => void refreshStatuses(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [documents]);

  function getUploadError(error: unknown): string {
    if (
      error &&
      typeof error === "object" &&
      "response" in error &&
      error.response &&
      typeof error.response === "object" &&
      "data" in error.response &&
      error.response.data &&
      typeof error.response.data === "object" &&
      "detail" in error.response.data &&
      typeof error.response.data.detail === "string"
    ) {
      return error.response.data.detail;
    }
    if (error instanceof Error && error.message) return error.message;
    return "Upload failed. Please try again.";
  }

  async function uploadOne(file: File) {
    setCurrentUploadName(file.name);
    setUploadProgress(0);
    try {
      const uploaded = await documentsApi.upload(file, setUploadProgress);
      setDocuments((current) => [
        uploaded,
        ...current.filter((document) => document.id !== uploaded.id),
      ]);
      setUploadFailures((current) =>
        current.filter((failure) => failure.file !== file)
      );
      onToast(
        `${file.name} uploaded. Indexing will continue in the background.`
      );
      return true;
    } catch (error) {
      const message = getUploadError(error);
      setUploadFailures((current) => [
        ...current.filter((failure) => failure.file !== file),
        { file, error: message },
      ]);
      onToast(`Could not upload ${file.name}: ${message}`);
      return false;
    }
  }

  async function uploadFiles(files: FileList | File[]) {
    const pdfs = Array.from(files).filter(
      (file) =>
        file.type === "application/pdf" ||
        file.name.toLowerCase().endsWith(".pdf")
    );
    if (!pdfs.length) {
      onToast("Please choose PDF files to upload.");
      return;
    }
    setUploading(true);
    for (const file of pdfs) {
      await uploadOne(file);
    }
    setUploading(false);
    setUploadProgress(0);
    setCurrentUploadName("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function retryUpload(file: File) {
    setUploading(true);
    await uploadOne(file);
    setUploading(false);
    setUploadProgress(0);
    setCurrentUploadName("");
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void uploadFiles(event.dataTransfer.files);
  }

  async function deleteSelected() {
    if (
      !selected.length ||
      !window.confirm(
        `Delete ${selected.length} selected document${
          selected.length === 1 ? "" : "s"
        }?`
      )
    )
      return;
    await Promise.all(selected.map((id) => documentsApi.remove(id)));
    setDocuments((current) =>
      current.filter((document) => !selected.includes(document.id))
    );
    onToast(
      `${selected.length} document${selected.length === 1 ? "" : "s"} deleted.`
    );
    setSelected([]);
  }

  async function reprocess(document: AcademicDocument) {
    try {
      await documentsApi.reprocess(document.id);
      setDocuments((current) =>
        current.map((item) =>
          item.id === document.id
            ? {
                ...item,
                status: "Processing",
                processingProgress: 0,
                processingError: null,
              }
            : item
        )
      );
      onToast(`Reprocessing ${document.name}.`);
    } catch (error) {
      onToast(`Could not retry ${document.name}: ${getUploadError(error)}`);
    }
  }

  return (
    <div className="documents-page">
      <PageHeading
        eyebrow="YOUR RESEARCH LIBRARY"
        title="Documents"
        description="Organize your papers and course materials in one searchable place."
        actions={
          <button
            className="button button-primary"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={15} /> Upload PDF
          </button>
        }
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(event) =>
          event.target.files && void uploadFiles(event.target.files)
        }
      />
      <div
        className={`upload-dropzone ${dragging ? "is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node))
            setDragging(false);
        }}
        onDrop={handleDrop}
      >
        <span className="dropzone-icon">
          <Upload size={18} />
        </span>
        <div>
          <b>
            Drop your PDFs here, or{" "}
            <button onClick={() => fileInputRef.current?.click()}>
              browse files
            </button>
          </b>
          <small>
            Academic papers, textbooks, and notes · PDF · up to 50 MB each
          </small>
          {uploading && (
            <div className="upload-progress" role="status" aria-live="polite">
              <small>Uploading {currentUploadName}</small>
              <span>
                <i style={{ width: `${uploadProgress}%` }} />
              </span>
              <small>Transfer progress: {uploadProgress}%</small>
            </div>
          )}
        </div>
        <span className="dropzone-file">
          PDF <b>↗</b>
        </span>
      </div>
      {!!uploadFailures.length && (
        <div className="upload-failures" role="alert">
          {uploadFailures.map(({ file, error }) => (
            <div
              className="upload-failure"
              key={`${file.name}-${file.lastModified}`}
            >
              <span>
                <b>{file.name}</b>
                <small>{error}</small>
              </span>
              <button
                type="button"
                disabled={uploading}
                onClick={() => void retryUpload(file)}
              >
                <RefreshCw size={12} /> Retry upload
              </button>
            </div>
          ))}
        </div>
      )}
      <section className="document-list-card">
        {loadError && (
          <div className="document-load-error" role="alert">
            Could not refresh your document list: {loadError}
          </div>
        )}
        <div className="document-list-heading">
          <div>
            <span className="card-kicker">ALL MATERIALS</span>
            <h2>
              Your library <span>({documents.length})</span>
            </h2>
          </div>
          {selected.length > 0 && (
            <button
              className="button button-danger-outline"
              onClick={() => void deleteSelected()}
            >
              <Trash2 size={14} /> Delete {selected.length} selected
            </button>
          )}
        </div>
        <div className="document-filters">
          <label className="filter-search">
            <Search size={15} />
            <input
              placeholder="Search by file name..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="select-wrap">
            <Filter size={13} />
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              aria-label="Filter by subject"
            >
              {subjects.map((subject) => (
                <option key={subject}>{subject}</option>
              ))}
            </select>
            <ChevronDown size={13} />
          </label>
          <label className="select-wrap">
            <ListFilter size={13} />
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              aria-label="Filter by status"
            >
              {[
                "All statuses",
                "Indexed",
                "Processing",
                "Uploaded",
                "Failed",
              ].map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
            <ChevronDown size={13} />
          </label>
          <label className="select-wrap sort-select">
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value)}
              aria-label="Sort documents"
            >
              <option>Recently added</option>
              <option>Name A–Z</option>
            </select>
            <ChevronDown size={13} />
          </label>
        </div>
        <div className="document-table-scroll">
          <table className="document-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="Select all filtered documents"
                    checked={
                      selected.length === filtered.length && filtered.length > 0
                    }
                    onChange={() =>
                      setSelected(
                        selected.length === filtered.length
                          ? []
                          : filtered.map((document) => document.id)
                      )
                    }
                  />{" "}
                  NAME
                </th>
                <th>SUBJECT</th>
                <th>PAGES</th>
                <th>ADDED</th>
                <th>STATUS</th>
                <th>VECTOR INDEX</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((document) => (
                <DocumentRow
                  document={document}
                  key={document.id}
                  onOpen={() => navigate(`/app/documents/${document.id}`)}
                  onRetry={() => void reprocess(document)}
                  selected={selected.includes(document.id)}
                  onSelect={() =>
                    setSelected((current) =>
                      current.includes(document.id)
                        ? current.filter((id) => id !== document.id)
                        : [...current, document.id]
                    )
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <EmptyState
            icon={FileSearch}
            title="No documents match"
            text="Try a different search or subject filter."
            action={
              <button
                className="button button-secondary"
                onClick={() => {
                  setSearch("");
                  setCategory("All subjects");
                  setStatus("All statuses");
                }}
              >
                Clear filters
              </button>
            }
          />
        )}
        <div className="table-pagination">
          <span>
            Showing{" "}
            <b>
              {filtered.length ? 1 : 0}–{filtered.length}
            </b>{" "}
            of <b>{documents.length}</b> documents
          </span>
          <div>
            <button disabled aria-label="Previous page">
              <ChevronLeft size={15} />
            </button>
            <button className="current-page">1</button>
            <button aria-label="Next page" disabled>
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </section>
      <div className="document-footnote">
        <ShieldCheck size={14} />
        <span>
          Your documents are encrypted and used only to answer your questions.
        </span>
        <button onClick={() => navigate("/app/settings")}>
          Privacy settings <ArrowRight size={12} />
        </button>
      </div>
    </div>
  );
}

function DocumentDetailPage({
  onToast,
}: {
  onToast: (message: string) => void;
}) {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { documents, loadError, loading } = useLibraryDocuments();
  const document = documents.find((item) => item.id === id);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let createdUrl: string | null = null;
    documentsApi
      .getFile(id)
      .then((blob) => {
        if (!active) return;
        createdUrl = URL.createObjectURL(blob);
        setPdfUrl(createdUrl);
        setPdfError(null);
      })
      .catch((error: unknown) => {
        if (active) {
          setPdfError(
            error instanceof Error ? error.message : "Could not load this PDF."
          );
        }
      });
    return () => {
      active = false;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
      setPdfUrl(null);
    };
  }, [id]);

  if (!document) {
    return (
      <div className="detail-page">
        <EmptyState
          icon={FileSearch}
          title={loading ? "Loading document" : "Document unavailable"}
          text={
            loading
              ? "Checking your library…"
              : loadError ?? "This document could not be found in your library."
          }
          action={
            <button
              className="button button-secondary"
              onClick={() => navigate("/app/documents")}
            >
              Back to documents
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="detail-page">
      <button
        className="detail-back"
        onClick={() => navigate("/app/documents")}
      >
        <ChevronLeft size={15} /> All documents
      </button>
      <PageHeading
        eyebrow="DOCUMENT DETAILS"
        title={document.name.replace(".pdf", "")}
        description={`${document.subject} · ${document.type}`}
        actions={
          <>
            <button
              className="button button-secondary"
              onClick={() => {
                if (pdfUrl)
                  window.open(pdfUrl, "_blank", "noopener,noreferrer");
                else onToast(pdfError ?? "The PDF is still loading.");
              }}
            >
              <ArrowDownToLine size={14} /> Download
            </button>
            <button
              className="button button-primary"
              onClick={() => navigate("/app/chat")}
            >
              <Sparkles size={14} /> Ask about this
            </button>
          </>
        }
      />
      <div className="detail-layout">
        <section className="pdf-preview-panel">
          <div className="preview-toolbar">
            <span>
              <FileText size={14} /> Document preview
            </span>
            <span className="preview-page-number">
              Page <b>1</b> of {document.pages}
            </span>
            <div>
              <button aria-label="Zoom out">−</button>
              <button aria-label="Zoom in">+</button>
              <button aria-label="More preview actions">
                <MoreHorizontal size={15} />
              </button>
            </div>
          </div>
          <div className="pdf-preview-canvas">
            {pdfUrl ? (
              <iframe
                className="document-pdf-frame"
                title={`PDF preview: ${document.name}`}
                src={pdfUrl}
              />
            ) : (
              <div className="document-pdf-state">
                {pdfError ?? "Loading document preview…"}
              </div>
            )}
          </div>
        </section>
        <aside className="detail-side">
          <section className="detail-card">
            <div className="detail-card-heading">
              <h2>Document info</h2>
              <button aria-label="More document actions">
                <MoreHorizontal size={16} />
              </button>
            </div>
            <div className="detail-metadata">
              <div>
                <span>STATUS</span>
                <StatusPill status={document.status} />
              </div>
              <div>
                <span>SUBJECT</span>
                <b>{document.subject}</b>
              </div>
              <div>
                <span>PAGE COUNT</span>
                <b>{document.pages} pages</b>
              </div>
              <div>
                <span>FILE SIZE</span>
                <b>{document.size}</b>
              </div>
              <div>
                <span>UPLOADED</span>
                <b>{document.date}</b>
              </div>
              <div>
                <span>DOCUMENT TYPE</span>
                <b>{document.type}</b>
              </div>
            </div>
          </section>
          <section className="detail-card extraction-card">
            <h2>Extraction & indexing</h2>
            <div className="extraction-score">
              <span>
                <Database size={16} />
              </span>
              <div>
                <b>{document.chunks.toLocaleString()}</b>
                <small>text chunks indexed</small>
              </div>
              <span className="extraction-check">
                <CheckCheck size={15} />
              </span>
            </div>
            <div className="extraction-meter">
              <i
                style={{ width: document.status === "Indexed" ? "100%" : "0%" }}
              />
            </div>
            <div className="extraction-meta">
              <span>Text extraction</span>
              <b>{document.status === "Indexed" ? "Complete" : "Pending"}</b>
            </div>
            <div className="extraction-meta">
              <span>Embedding model</span>
              <b>text-embedding-3-small</b>
            </div>
            <div className="extraction-meta">
              <span>Vector index</span>
              <b>
                {document.status === "Indexed" ? "FAISS · Ready" : "Waiting"}
              </b>
            </div>
          </section>
          <section className="detail-card related-card">
            <h2>Related questions</h2>
            <button onClick={() => navigate("/app/chat")}>
              What are the key findings in this paper? <ArrowRight size={13} />
            </button>
            <button onClick={() => navigate("/app/chat")}>
              Explain the methodology used here <ArrowRight size={13} />
            </button>
            <button onClick={() => navigate("/app/chat")}>
              How does this relate to my other papers? <ArrowRight size={13} />
            </button>
          </section>
        </aside>
      </div>
    </div>
  );
}

function KnowledgePage() {
  const { documents, loadError, loading } = useLibraryDocuments();
  const docsTotal = documents.length;
  const indexedDocuments = documents.filter(
    (document) => document.status === "Indexed"
  ).length;
  const chunksTotal = documents
    .filter((document) => document.status === "Indexed")
    .reduce(
    (total, document) => total + document.chunks,
    0
    );
  const indexCoverage = docsTotal
    ? `${Math.round((indexedDocuments / docsTotal) * 100)}%`
    : "—";
  const subjects = [...new Set(documents.map((document) => document.subject))];
  const distribution = subjects.map((subject) => ({
    name: subject,
    value: documents.filter((document) => document.subject === subject).length,
  }));
  return (
    <div className="knowledge-page">
      <PageHeading
        eyebrow="SEMANTIC SEARCH, EXPLAINED"
        title="Knowledge base"
        description="See how your reading becomes a searchable, source-grounded library."
        actions={
          <button className="button button-secondary">
            <Settings2 size={15} /> Retrieval settings
          </button>
        }
      />
      {loadError && (
        <div className="document-load-error" role="alert">
          Could not load your library data: {loadError}
        </div>
      )}
      <div className="stats-grid">
        <StatCard
          label="Source documents"
          value={loading || loadError ? "—" : String(docsTotal)}
          change="In your library"
          icon={FileText}
          tone="blue"
        />
        <StatCard
          label="Indexed chunks"
          value={loading || loadError ? "—" : chunksTotal.toLocaleString()}
          change="Retrieved with semantic search"
          icon={Layers3}
          tone="violet"
        />
        <StatCard
          label="Documents indexed"
          value={loading || loadError ? "—" : indexCoverage}
          change={
            loading || loadError
              ? "Index status unavailable"
              : `${indexedDocuments} of ${docsTotal} documents`
          }
          icon={Gauge}
          tone="green"
        />
        <StatCard
          label="Retrievals this week"
          value="—"
          change="Not reported by the analytics service"
          icon={FileSearch}
          tone="orange"
        />
      </div>
      <section className="knowledge-flow-card">
        <div className="card-heading">
          <div>
            <span className="card-kicker">HOW YOUR ANSWERS ARE BUILT</span>
            <h2>From a paper to a supported answer</h2>
          </div>
          <span className="flow-live">
            {loading
              ? "LOADING INDEX"
              : loadError
              ? "INDEX UNAVAILABLE"
              : `${indexedDocuments} DOCUMENTS INDEXED`}
          </span>
        </div>
        <div className="knowledge-pipeline">
          {[
            {
              icon: FileText,
              title: "Documents",
              sub: `${docsTotal} PDFs · ${
                documents.filter((document) => document.status === "Indexed")
                  .length
              } indexed`,
              detail: "Academic papers and books",
            },
            {
              icon: Scissors,
              title: "Text chunks",
              sub: `${chunksTotal.toLocaleString()} passages`,
              detail: "Split for relevant context",
            },
            {
              icon: BrainCircuit,
              title: "Embeddings",
              sub: "Service configuration",
              detail: "Meaning represented as vectors",
            },
            {
              icon: Database,
              title: "Vector index",
              sub: `${indexedDocuments} indexed documents`,
              detail: "Fast similarity search",
            },
            {
              icon: Sparkles,
              title: "Cited answers",
              sub: "Page-level references",
              detail: "Verified against your sources",
            },
          ].map(({ icon: Icon, title, sub, detail }, index, steps) => (
            <div className="pipeline-stage" key={title}>
              <div className={`pipeline-icon pipeline-icon-${index}`}>
                <Icon size={19} />
              </div>
              <div className="pipeline-stage-meta">
                <b>{title}</b>
                <small>{sub}</small>
                <span>{detail}</span>
              </div>
              {index < steps.length - 1 && (
                <span className="pipeline-arrow">
                  <ArrowRight size={15} />
                </span>
              )}
            </div>
          ))}
        </div>
        <div className="pipeline-note">
          <ShieldCheck size={16} />
          <div>
            <b>Retrieval before generation</b>
            <span>
              Each answer begins with the passages retrieved from your library.
              When the sources do not support an answer, Scholar says so.
            </span>
          </div>
        </div>
      </section>
      <div className="knowledge-lower">
        <section className="dashboard-card subject-chart-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">YOUR LIBRARY BY SUBJECT</span>
              <h2>Subject distribution</h2>
            </div>
            <button className="icon-button" aria-label="View documents">
              <ArrowUpRight size={16} />
            </button>
          </div>
          {loading ? (
            <div className="chart-loading" role="status">
              Loading subject data…
            </div>
          ) : loadError ? (
            <EmptyState
              icon={Layers3}
              title="Subject data unavailable"
              text="The document service could not provide subject information."
            />
          ) : distribution.length ? (
            <div className="subject-chart-wrap">
              <Suspense
                fallback={
                  <div className="chart-loading" role="status">
                    Loading chart…
                  </div>
                }
              >
                <SubjectDistributionChart
                  data={distribution}
                  colors={chartColors}
                />
              </Suspense>
              <div className="subject-legend">
                {distribution.map((item, index) => (
                  <div key={item.name}>
                    <i
                      style={{
                        backgroundColor:
                          chartColors[index % chartColors.length],
                      }}
                    />
                    <span>{item.name}</span>
                    <b>{item.value}</b>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState
              icon={Layers3}
              title="No subject data yet"
              text="Upload documents with subject information to see your library distribution."
            />
          )}
        </section>
        <section className="dashboard-card retrieval-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">THIS WEEK</span>
              <h2>Retrieval quality</h2>
            </div>
          </div>
          <EmptyState
            icon={Gauge}
            title="No retrieval report available"
            text="Retrieval quality metrics are not included in the current service response."
          />
        </section>
      </div>
    </div>
  );
}

const chartColors = ["#6268dd", "#69b5a7", "#e4a66b", "#a98dd2", "#87a6ce"];

function AnalyticsPage() {
  const { summary, loadError } = useAnalyticsSummary();
  return (
    <div className="analytics-page">
      <PageHeading
        eyebrow="YOUR RESEARCH, MEASURED"
        title="Analytics"
        description="A summary of the analytics currently reported by your service."
      />
      {loadError && (
        <div className="document-load-error" role="alert">
          Could not load analytics: {loadError}
        </div>
      )}
      <div className="stats-grid analytics-stats">
        <StatCard
          label="Questions asked"
          value={summary ? String(summary.questionsToday) : "—"}
          change="Total reported by the service"
          icon={MessageCircle}
          tone="blue"
        />
        <StatCard
          label="Avg. response time"
          value={summary?.avgResponse || "—"}
          change="Reported by the service"
          icon={Clock3}
          tone="violet"
        />
        <StatCard
          label="Successful retrievals"
          value="—"
          change="Not included in the analytics response"
          icon={CheckCheck}
          tone="green"
        />
        <StatCard
          label="Sources referenced"
          value="—"
          change="Not included in the analytics response"
          icon={FileSearch}
          tone="orange"
        />
      </div>
      <div className="analytics-main-grid">
        <section className="dashboard-card analytics-line-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">RESEARCH ACTIVITY</span>
              <h2>Questions over time</h2>
            </div>
            <span className="analytics-total">
              <b>{summary ? summary.questionsToday : "—"}</b> total questions
            </span>
          </div>
          <EmptyState
            icon={Activity}
            title="No activity series available"
            text="The analytics service reports totals but does not provide a time series."
          />
        </section>
        <section className="dashboard-card analytics-donut-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">ANSWER QUALITY</span>
              <h2>Query outcomes</h2>
            </div>
          </div>
          <EmptyState
            icon={Gauge}
            title="No outcome breakdown available"
            text="Query outcome metrics are not included in the analytics response."
          />
        </section>
      </div>
      <div className="analytics-lower-grid">
        <section className="dashboard-card subject-bar-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">SUBJECT AREAS</span>
              <h2>Most explored subjects</h2>
            </div>
            <button className="text-link">
              View all <ArrowRight size={13} />
            </button>
          </div>
          <EmptyState
            icon={Layers3}
            title="No subject activity available"
            text="The analytics service does not report question totals by subject."
          />
        </section>
        <section className="dashboard-card upload-analytics-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">LIBRARY GROWTH</span>
              <h2>Documents added</h2>
            </div>
          </div>
          <EmptyState
            icon={FileText}
            title="No upload history available"
            text="The analytics service does not provide document activity over time."
          />
        </section>
      </div>
      <section className="dashboard-card analytics-note">
        <span>
          <Activity size={17} />
        </span>
        <div>
          <b>Analytics coverage</b>
          <p>
            This page displays only values returned by the connected analytics
            service. Unsupported breakdowns are left blank rather than
            estimated.
          </p>
        </div>
      </section>
    </div>
  );
}

function SettingsPage({ onToast }: { onToast: (message: string) => void }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [active, setActive] = useState("Profile");
  const [preferences, setPreferences] = useState({
    weekly: true,
    processing: true,
    grounded: true,
    streaming: true,
    sources: true,
    usage: false,
  });
  const [name, setName] = useState(user?.name ?? "");
  const sections = [
    { icon: Users, label: "Profile" },
    { icon: LockKeyhole, label: "Security" },
    { icon: Bell, label: "Notifications" },
    { icon: Sparkles, label: "AI preferences" },
    { icon: ShieldCheck, label: "Privacy" },
  ];
  function toggle(key: keyof typeof preferences) {
    setPreferences((value) => ({ ...value, [key]: !value[key] }));
  }
  return (
    <div className="settings-page">
      <PageHeading
        eyebrow="MAKE IT YOURS"
        title="Settings"
        description="Your account, preferences, and the way you work with sources."
      />
      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {sections.map(({ icon: Icon, label }) => (
            <button
              key={label}
              className={active === label ? "active" : ""}
              onClick={() => setActive(label)}
            >
              <Icon size={16} />
              {label}
              {active === label && <ChevronRight size={14} />}
            </button>
          ))}
        </nav>
        <section className="settings-content">
          <div className="settings-section-heading">
            <span className="settings-section-icon">
              <Users size={17} />
            </span>
            <div>
              <h2>{active}</h2>
              <p>
                {active === "Profile"
                  ? "Manage your personal information and account details."
                  : `Configure your ${active.toLowerCase()} preferences.`}
              </p>
            </div>
          </div>
          {active === "Profile" && (
            <>
              <div className="profile-settings-banner">
                <span>
                  {user?.avatar ||
                    user?.name
                      .trim()
                      .split(/\s+/)
                      .slice(0, 2)
                      .map((part) => part[0])
                      .join("")
                      .toUpperCase()}
                </span>
                <div>
                  <b>Profile photo</b>
                  <small>
                    Your initials appear in your research workspace.
                  </small>
                </div>
                <button
                  className="button button-secondary button-compact"
                  onClick={() =>
                    onToast("Profile photos are not enabled in this workspace.")
                  }
                >
                  Change photo
                </button>
              </div>
              <label className="settings-label">
                Full name
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label className="settings-label">
                Email address
                <input
                  type="email"
                  value={user?.email ?? ""}
                  disabled
                />
                <small>
                  Contact support to change the email on your account.
                </small>
              </label>
              <label className="settings-label">
                Institution
                <input placeholder="Add your institution" />
                <small>
                  Used to personalize your workspace, never shared with
                  documents.
                </small>
              </label>
              <div className="settings-save-row">
                <span>
                  Profile changes are not supported by the connected service.
                </span>
                <button
                  className="button button-primary button-compact"
                  onClick={() =>
                    onToast(
                      "Profile changes are not supported by the connected service."
                    )
                  }
                >
                  Save changes
                </button>
              </div>
              <div className="settings-separator" />
              <h3>Display</h3>
              <div className="setting-option">
                <div>
                  <b>Appearance</b>
                  <small>Choose your preferred workspace theme.</small>
                </div>
                <div className="segmented-control">
                  <button className="selected">
                    <Sun size={14} />
                    Light
                  </button>
                  <button
                    onClick={() =>
                      onToast(
                        "Dark appearance is available from the top navigation."
                      )
                    }
                  >
                    <Moon size={14} />
                    Dark
                  </button>
                </div>
              </div>
            </>
          )}
          {active === "Notifications" && (
            <div className="settings-options">
              {[
                [
                  "weekly",
                  "Weekly research summary",
                  "A short recap of your study activity.",
                ],
                [
                  "processing",
                  "Document processing updates",
                  "Let me know when an upload is ready or needs attention.",
                ],
              ].map(([key, title, description]) => (
                <SettingToggle
                  key={key}
                  title={title}
                  description={description}
                  checked={preferences[key as keyof typeof preferences]}
                  onChange={() => toggle(key as keyof typeof preferences)}
                />
              ))}
            </div>
          )}
          {active === "AI preferences" && (
            <div className="settings-options">
              {[
                [
                  "grounded",
                  "Require cited sources",
                  "Clearly flag answers when your documents do not support them.",
                ],
                [
                  "streaming",
                  "Stream answers as they are generated",
                  "Show responses progressively while sources are checked.",
                ],
                [
                  "sources",
                  "Show source context panel",
                  "Keep retrieved passages visible next to the conversation.",
                ],
              ].map(([key, title, description]) => (
                <SettingToggle
                  key={key}
                  title={title}
                  description={description}
                  checked={preferences[key as keyof typeof preferences]}
                  onChange={() => toggle(key as keyof typeof preferences)}
                />
              ))}
              <label className="settings-label settings-select-label">
                Answer style
                <select>
                  <option>Concise and direct</option>
                  <option>Detailed explanation</option>
                  <option>Explain for beginners</option>
                </select>
                <small>
                  Style changes never affect which sources support an answer.
                </small>
              </label>
            </div>
          )}
          {active === "Security" && (
            <>
              <div className="security-card">
                <span>
                  <ShieldCheck size={18} />
                </span>
                <div>
                  <b>Password authentication</b>
                  <small>Your account is protected with secure sign-in.</small>
                </div>
                <StatusPill status="Indexed" />
              </div>
              <button
                className="button button-secondary"
                onClick={() =>
                  onToast(
                    "Password reset instructions will be sent to your email."
                  )
                }
              >
                Change password
              </button>
              <div className="settings-separator" />
              <h3>Active sessions</h3>
              <div className="session-row">
                <span className="session-device">
                  <HardDrive size={16} />
                </span>
                <div>
                  <b>Mac · Current session</b>
                  <small>Last active just now · This device</small>
                </div>
                <span className="session-current">Current</span>
              </div>
            </>
          )}
          {active === "Privacy" && (
            <>
              <div className="privacy-callout">
                <ShieldCheck size={19} />
                <div>
                  <b>Your research stays private.</b>
                  <p>
                    Uploaded documents and conversations are yours. API keys and
                    model secrets are never stored in this browser.
                  </p>
                </div>
              </div>
              <div className="settings-options">
                <SettingToggle
                  title="Share anonymous usage data"
                  description="Help improve Scholar by sharing product interaction statistics."
                  checked={preferences.usage}
                  onChange={() => toggle("usage")}
                />
              </div>
              <button
                className="button button-danger-outline"
                onClick={() =>
                  onToast(
                    "Data export is available once connected to your account service."
                  )
                }
              >
                <ArrowDownToLine size={14} /> Export my data
              </button>
              <div className="settings-separator" />
              <button
                className="logout-button"
                onClick={() => void signOut().then(() => navigate("/login"))}
              >
                <LogOut size={15} /> Sign out of Scholar
              </button>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function SettingToggle({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <div className="setting-option">
      <div>
        <b>{title}</b>
        <small>{description}</small>
      </div>
      <button
        className={`toggle-switch ${checked ? "on" : ""}`}
        role="switch"
        aria-checked={checked}
        aria-label={title}
        onClick={onChange}
      >
        <i />
      </button>
    </div>
  );
}

function AdminPage() {
  const [health, setHealth] = useState<
    "Checking" | "Healthy" | "Degraded" | "Unavailable"
  >("Checking");
  const [healthError, setHealthError] = useState<string | null>(null);
  useEffect(() => {
    healthApi
      .get()
      .then((data) =>
        setHealth(data.status === "healthy" ? "Healthy" : "Degraded")
      )
      .catch((error: unknown) => {
        setHealth("Unavailable");
        setHealthError(
          error instanceof Error
            ? error.message
            : "Could not retrieve service health."
        );
      });
  }, []);
  return (
    <div className="admin-page">
      <PageHeading
        eyebrow="SYSTEM OVERVIEW"
        title="Admin overview"
        description="Service health from the connected API. Usage telemetry is not available."
        actions={
          <span className="admin-view-label">
            <ShieldCheck size={14} /> ADMIN VIEW
          </span>
        }
      />
      {healthError && (
        <div className="document-load-error" role="alert">
          Could not load service health: {healthError}
        </div>
      )}
      <section className="dashboard-card system-health-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">LIVE SERVICE STATUS</span>
              <h2>System health</h2>
            </div>
            <span
              className={`health-badge ${
                health === "Healthy" ? "healthy" : ""
              }`}
            >
              <i />
              {health}
            </span>
          </div>
      </section>
      <section className="dashboard-card admin-unavailable">
        <EmptyState
          icon={LockKeyhole}
          title="Admin telemetry is unavailable"
          text="The connected service does not provide user, model-usage, or processing-queue metrics."
        />
      </section>
    </div>
  );
}

export function WorkspacePage({
  page,
}: {
  page:
    | "dashboard"
    | "chat"
    | "documents"
    | "document"
    | "knowledge"
    | "analytics"
    | "settings"
    | "admin";
}) {
  const [toast, setToast] = useState("");
  const location = useLocation();
  useEffect(() => {
    setToast("");
  }, [location.pathname]);
  const showToast = (message: string) => setToast(message);
  return (
    <>
      {page === "dashboard" && <DashboardPage />}
      {page === "chat" && <ChatPage onToast={showToast} />}
      {page === "documents" && <DocumentsPage onToast={showToast} />}
      {page === "document" && <DocumentDetailPage onToast={showToast} />}
      {page === "knowledge" && <KnowledgePage />}
      {page === "analytics" && <AnalyticsPage />}
      {page === "settings" && <SettingsPage onToast={showToast} />}
      {page === "admin" && <AdminPage />}
      {toast && <Toast message={toast} onClose={() => setToast("")} />}
    </>
  );
}
