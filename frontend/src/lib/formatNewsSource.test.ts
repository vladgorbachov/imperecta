import { describe, expect, it } from "vitest";
import { formatNewsSource } from "@/lib/formatNewsSource";

describe("formatNewsSource", () => {
  it("deduplicates tokens and drops Feedloaderapi", () => {
    expect(
      formatNewsSource("The Associated Press; Feedloaderapi; The Associated Press"),
    ).toBe("The Associated Press");
  });

  it("joins up to two tokens with middle dot", () => {
    expect(formatNewsSource("Retail Week, EU Business")).toBe("Retail Week · EU Business");
  });

  it("returns null for unknown-only source", () => {
    expect(formatNewsSource("unknown")).toBeNull();
  });

  it("returns null when only Feedloaderapi remains", () => {
    expect(formatNewsSource("Feedloaderapi; feedloaderapi")).toBeNull();
  });
});
