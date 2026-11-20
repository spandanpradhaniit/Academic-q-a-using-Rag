import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownRenderer } from "../components/MarkdownRenderer";

describe("MarkdownRenderer Component", () => {
  it("renders basic markdown headings and paragraphs", () => {
    render(<MarkdownRenderer content={"# Academic RAG\n\nThis is a test paragraph."} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Academic RAG");
    expect(screen.getByText("This is a test paragraph.")).toBeInTheDocument();
  });

  it("renders lists and formatted text correctly", () => {
    render(
      <MarkdownRenderer
        content={"- Item 1\n- Item 2\n\n**Bold claim** with citation [Source 1]"}
      />
    );
    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.getByText("Item 2")).toBeInTheDocument();
    expect(screen.getByText("Bold claim")).toBeInTheDocument();
  });
});
