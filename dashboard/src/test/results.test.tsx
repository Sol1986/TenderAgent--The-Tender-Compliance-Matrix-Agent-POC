import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultTabs } from "@/components/result-tabs";
import { completedSnapshot } from "./fixtures";
import { categoryNames } from "@/lib/contracts";
import { categoryLabel, requirementCounts, requirementRows } from "@/lib/requirements";
function populated() {
  const result = completedSnapshot();
  const categories = result.output.tender_analysis!.categories;
  categories[0] = { category: "submission", status: "FOUND", requirements: [
    { requirement: "Signed bid $1,250.00", requirement_type: "MANDATORY", status: "FOUND", source_sections: ["BA01"], evidence: ["Sign the bid."] },
    { requirement: "Security per SC02", requirement_type: "CONDITIONAL", status: "EXTERNAL_REFERENCE", source_sections: ["SC02"], evidence: ["Consult SC02."] },
    { requirement: "Insurance waived", requirement_type: "MANDATORY", status: "NOT_REQUIRED", source_sections: [], evidence: [] },
    { requirement: "<img src=x onerror=alert(1)>", requirement_type: "INFORMATIONAL", status: "FOUND", source_sections: [], evidence: ["<script>evil()</script>"] },
  ] };
  return result;
}
describe("Tender review", () => {
  it("defaults to Decision Support and renders every returned report field", () => {
    const result = populated();
    const report = result.output.decision_support_report!;
    for (const key of Object.keys(report)) if (key !== "executive_summary") (report as unknown as Record<string, string[]>)[key] = [key + " test item"];
    render(<ResultTabs snapshot={result} />);
    expect(screen.getByRole("tab", { name: "Decision Support" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(report.executive_summary)).toBeVisible();
    for (const key of Object.keys(report).filter(k => k !== "executive_summary")) expect(screen.getByText(key + " test item")).toBeVisible();
    expect(screen.getByText("Your team makes the final Bid / No-Bid decision.")).toBeVisible();
  });
  it("counts final requirements with waivers excluded and overlapping external references", () => {
    const rows = requirementRows(populated().output.tender_analysis!);
    expect(requirementCounts(rows)).toEqual({ total: 4, mandatory: 1, conditional: 1, external: 1 });
    rows.push({ ...rows[0], id: "extra", status: "EXTERNAL_REFERENCE" });
    expect(requirementCounts(rows)).toEqual({ total: 5, mandatory: 2, conditional: 1, external: 2 });
  });
  it("navigates all categories, exposes evidence, and distinguishes absence from waiver", () => {
    render(<ResultTabs snapshot={populated()} />);
    fireEvent.click(screen.getByRole("button", { name: "Review structured evidence" }));
    for (const name of categoryNames) expect(screen.getByRole("button", { name: new RegExp("^" + categoryLabel(name) + " ") })).toBeVisible();
    const panel = within(screen.getByRole("tabpanel"));
    fireEvent.click(panel.getAllByText("Source & evidence")[0]);
    expect(panel.getByText("Sign the bid.")).toBeVisible();
    fireEvent.click(panel.getByRole("button", { name: "Insurance 0" }));
    expect(panel.getByText("NOT_FOUND")).toBeVisible();
    expect(panel.getByText(/No evidence was extracted/)).toBeVisible();
  });
  it("combines search, type, and external filters and shares them with the matrix", () => {
    render(<ResultTabs snapshot={populated()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tender Analysis" }));
    let panel = within(screen.getByRole("tabpanel"));
    fireEvent.change(panel.getByLabelText("Search requirements"), { target: { value: "SC02" } });
    fireEvent.change(panel.getByLabelText("Requirement type"), { target: { value: "CONDITIONAL" } });
    fireEvent.click(panel.getByLabelText("External references only"));
    expect(panel.getByText("1 matching requirements")).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Compliance Matrix" }));
    panel = within(screen.getByRole("tabpanel"));
    expect(panel.getAllByRole("row")).toHaveLength(2);
    expect(panel.getByText("Security per SC02")).toBeVisible();
    fireEvent.change(panel.getByLabelText("Search requirements"), { target: { value: "missing text" } });
    expect(panel.getByText("No requirements match the current filters.")).toBeVisible();
    fireEvent.click(panel.getByRole("button", { name: "Clear filters" }));
    expect(panel.getAllByRole("row")).toHaveLength(5);
  });
  it("renders source strings literally, preserves amounts, and keeps JSON collapsed", () => {
    const view = render(<ResultTabs snapshot={populated()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tender Analysis" }));
    const panel = within(screen.getByRole("tabpanel"));
    expect(panel.getByText("Signed bid $1,250.00")).toBeVisible();
    expect(panel.getByText("<img src=x onerror=alert(1)>")).toBeVisible();
    expect(view.container.querySelector("img")).toBeNull();
    expect(view.container.querySelector("script")).toBeNull();
    expect(screen.getByText("Structured output JSON").closest("details")).not.toHaveAttribute("open");
  });
  it("supports keyboard tabs and honest empty report sections", () => {
    render(<ResultTabs snapshot={completedSnapshot()} />);
    expect(screen.getAllByText(/No items were returned in this section/)).toHaveLength(7);
    fireEvent.keyDown(screen.getByRole("tab", { name: "Decision Support" }), { key: "End" });
    expect(screen.getByRole("tab", { name: "Compliance Matrix" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("No requirements match");
  });
  it("retains partial requirements when report generation fails", () => {
    const result = populated(); result.status = "failed"; result.output.decision_support_report = null;
    render(<ResultTabs snapshot={result} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Incomplete analysis");
    expect(screen.getByText("The decision-support report could not be completed.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Review available requirements" }));
    expect(within(screen.getByRole("tabpanel")).getByText("Signed bid $1,250.00")).toBeVisible();
  });
});

