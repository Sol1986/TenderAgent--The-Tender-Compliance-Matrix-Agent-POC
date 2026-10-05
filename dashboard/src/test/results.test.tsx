import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultPreview } from "@/components/result-preview";
import { completedSnapshot, snapshot } from "./fixtures";

describe("Excel deliverable", () => {
  it("shows a download only when the workbook is ready", () => {
    const { rerender } = render(<ResultPreview snapshot={snapshot()} />);
    expect(screen.queryByRole("link", { name: /Download Excel matrix/ })).not.toBeInTheDocument();
    rerender(<ResultPreview snapshot={completedSnapshot()} />);
    expect(screen.getByRole("link", { name: /Download Excel matrix/ })).toHaveAttribute("href", expect.stringContaining("/compliance-matrix.xlsx"));
    expect(screen.getByText("18")).toBeVisible();
  });
});
