import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

describe("foundation", () => {
  it("renders a node", () => {
    render(<div>snag</div>);
    expect(screen.getByText("snag")).toBeTruthy();
  });
});
