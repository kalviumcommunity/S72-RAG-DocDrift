export interface SuggestedQuery {
  type: string;
  version: string;
  question: string;
  metadata: string;
  accent: "gold" | "coral" | "cyan" | "green";
}

export const suggestedQueries: SuggestedQuery[] = [
  {
    type: "Migration Guide",
    version: "v2",
    question: "How do I migrate auth tokens from v1 to v2 JWT format?",
    metadata: "+12 parameters  •  Auth0 / Okta Handlers",
    accent: "gold",
  },
  {
    type: "Changelog",
    version: "v3.1",
    question: "What are the breaking changes in the latest v3.1 release?",
    metadata: "Deprecated: legacy_session_id  •  Diff v3.0 ↔ v3.1",
    accent: "coral",
  },
  {
    type: "API Reference",
    version: "v3",
    question:
      "How to configure rate limiting on the POST /v3/webhooks endpoint?",
    metadata: "429 Too Many Requests  •  Redis Token Bucket",
    accent: "cyan",
  },
  {
    type: "SDK Guide",
    version: "v2.4",
    question: "Show example payload for bulk batch upload in v2.4",
    metadata: "TypeScript & Python Snippets  •  JSON Multipart",
    accent: "green",
  },
];