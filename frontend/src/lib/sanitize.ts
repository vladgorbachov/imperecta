/**
 * HTML sanitization for safe rendering of user-controlled or external content.
 * Uses DOMPurify to strip scripts, event handlers, javascript: URLs, and other dangerous markup.
 */

import DOMPurify from "dompurify";

/**
 * Sanitizes HTML for safe insertion via dangerouslySetInnerHTML.
 * Preserves safe formatting tags (h1-h6, strong, em, code, ul, li, br, etc.).
 * Removes scripts, event handlers, javascript:/data: URLs, and other dangerous content.
 */
export function sanitizeHtml(html: string): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "h1", "h2", "h3", "h4", "h5", "h6",
      "strong", "em", "b", "i", "u", "code", "pre",
      "ul", "ol", "li", "p", "br", "span", "div",
      "a",
    ],
    ALLOWED_ATTR: ["href", "class", "target", "rel"],
    ADD_ATTR: ["target"],
  });
}
