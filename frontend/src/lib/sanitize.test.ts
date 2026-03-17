import { describe, it, expect } from "vitest";
import { sanitizeHtml } from "./sanitize";

describe("sanitizeHtml", () => {
  it("removes script tags", () => {
    const html = '<p>Hello</p><script>alert(1)</script>';
    expect(sanitizeHtml(html)).not.toContain("<script>");
    expect(sanitizeHtml(html)).not.toContain("alert(1)");
  });

  it("removes onerror and other event handlers", () => {
    const html = '<img src="x" onerror="window.__xss=1">';
    expect(sanitizeHtml(html)).not.toContain("onerror");
    expect(sanitizeHtml(html)).not.toContain("__xss");
  });

  it("removes javascript: URLs from href", () => {
    const html = '<a href="javascript:alert(1)">click</a>';
    const result = sanitizeHtml(html);
    expect(result).not.toContain("javascript:");
    expect(result).not.toContain("alert(1)");
  });

  it("removes data: URLs that could execute", () => {
    const html = '<a href="data:text/html,<script>alert(1)</script>">x</a>';
    const result = sanitizeHtml(html);
    expect(result).not.toContain("data:text/html");
  });

  it("preserves safe formatting: bold, italic, lists", () => {
    const html = "<strong>bold</strong> <em>italic</em> <ul><li>item</li></ul>";
    const result = sanitizeHtml(html);
    expect(result).toContain("<strong>");
    expect(result).toContain("bold");
    expect(result).toContain("<em>");
    expect(result).toContain("italic");
    expect(result).toContain("<ul>");
    expect(result).toContain("<li>");
  });

  it("preserves headings and code", () => {
    const html = "<h1>Title</h1><code>code</code>";
    const result = sanitizeHtml(html);
    expect(result).toContain("<h1>");
    expect(result).toContain("Title");
    expect(result).toContain("<code>");
    expect(result).toContain("code");
  });

  it("returns empty string for empty input", () => {
    expect(sanitizeHtml("")).toBe("");
  });
});
