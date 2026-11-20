import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="page-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-heading-actions">{actions}</div>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  change,
  icon: Icon,
  tone = "blue",
}: {
  label: string;
  value: string;
  change?: string;
  icon: LucideIcon;
  tone?: "blue" | "violet" | "green" | "orange";
}) {
  return (
    <article className="stat-card">
      <span className={`stat-icon stat-${tone}`}>
        <Icon size={17} aria-hidden="true" />
      </span>
      <div className="stat-copy">
        <span>{label}</span>
        <b>{value}</b>
        <small className={change?.startsWith("+") ? "positive-change" : ""}>
          {change || "Across your library"}
        </small>
      </div>
    </article>
  );
}

export function StatusPill({
  status,
}: {
  status: "Uploaded" | "Processing" | "Indexed" | "Failed";
}) {
  const className = status.toLowerCase();
  return (
    <span className={`status-pill status-${className}`}>
      <i aria-hidden="true" />
      {status}
    </span>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  text,
  action,
}: {
  icon: LucideIcon;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={20} aria-hidden="true" />
      </span>
      <b>{title}</b>
      <p>{text}</p>
      {action}
    </div>
  );
}

export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="loading-skeleton" role="status" aria-label="Loading">
      <span className="skeleton skeleton-title" aria-hidden="true" />
      {Array.from({ length: lines }, (_, index) => (
        <span className="skeleton" aria-hidden="true" key={index} />
      ))}
    </div>
  );
}

export function UserAvatar({ initials }: { initials: string }) {
  return (
    <span className="user-avatar" role="img" aria-label={`User ${initials}`}>
      {initials}
    </span>
  );
}
