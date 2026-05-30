Title: V: Spike OSS AI editor patterns without adopting runtime dependencies
Labels: V
GitHub: #36

## What to build

Document what we should borrow from BlockNote AI, CopilotKit, and Puck without adopting them into the MVP runtime.

## Acceptance criteria

- [ ] BlockNote AI spike documents licensing status, AI UX patterns to borrow, and why `@blocknote/xl-ai` is not used in MVP production code.
- [ ] CopilotKit spike documents whether its HITL/tool rendering can fit our Django/LiteLLM architecture without a heavy runtime pivot.
- [ ] Puck spike documents whether schema-first component editing suggests a better future `PaperDocumentV2` shape.
- [ ] Output recommends which patterns to copy into our own code and which dependencies to avoid.
- [ ] No production dependency is added by this spike.

## Blocked by

None - can start immediately.
