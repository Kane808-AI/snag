import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { ReactElement } from "react";
import { MobileNav } from "@/components/snag/shell";
import { buildActionQueue, type SnagItem } from "@/lib/snag-store";

function item(id: string, impact: number, effort: number): SnagItem {
  return {
    id,
    title: id,
    sourceType: "Web",
    sourceUrl: "https://example.com",
    contentType: "article",
    stage: "Worth Acting On",
    impact,
    effort,
    engagement: {},
    summary: id,
    keyIdeas: [],
    whyItWorked: "",
    whyItMatters: "",
    reusablePattern: "",
    action: "Act",
    actionType: "Try",
    tags: [],
    thumb: "",
    thumbAlt: "",
    savedAt: "2026-08-31",
  };
}

describe("mobile Actions navigation", () => {
  it("keeps the Act now tab in the mobile navigation", () => {
    type NavLink = ReactElement<{
      to: string;
      className?: string;
    }>;
    const nav = MobileNav();
    const links = nav.props.children as NavLink[];
    const actions = links.find((link) => link.props.to === "/actions");

    assert.ok(actions);
    assert.doesNotMatch(String(actions.props.className), /(^|\s)hidden(\s|$)/);
  });
});

describe("Actions queue ranking", () => {
  it("keeps input order when impact-to-effort ratios are equal", () => {
    const first = item("first", 4, 2);
    const second = item("second", 2, 1);
    const higher = item("higher", 5, 1);

    assert.deepEqual(buildActionQueue([first, second, higher]).map(({ id }) => id), [
      "higher",
      "first",
      "second",
    ]);
  });
});
