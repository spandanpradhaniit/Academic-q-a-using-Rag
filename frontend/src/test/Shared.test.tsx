import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageHeading, StatCard, StatusPill } from "../components/Shared";
import { BookOpen } from "lucide-react";

describe("Shared UI Components", () => {
  it("renders PageHeading with eyebrow, title, and description", () => {
    render(
      <PageHeading
        eyebrow="Academic System"
        title="Knowledge Base"
        description="Manage your research documents"
      />
    );
    expect(screen.getByText("Academic System")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Knowledge Base");
    expect(screen.getByText("Manage your research documents")).toBeInTheDocument();
  });

  it("renders StatCard with correct value and label", () => {
    render(
      <StatCard
        label="Total Documents"
        value="42"
        change="+5 this week"
        icon={BookOpen}
        tone="blue"
      />
    );
    expect(screen.getByText("Total Documents")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("+5 this week")).toBeInTheDocument();
  });

  it("renders StatusPill with correct badge styling", () => {
    const { rerender } = render(<StatusPill status="Indexed" />);
    expect(screen.getByText("Indexed")).toBeInTheDocument();

    rerender(<StatusPill status="Processing" />);
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });
});
