# Chapter Graph Technology Research

**Date:** 2026-06-13
**Scope:** Issues [#169](https://github.com/animesh0911/qs-paper-generator/issues/169),
[#170](https://github.com/animesh0911/qs-paper-generator/issues/170), and
[#171](https://github.com/animesh0911/qs-paper-generator/issues/171)

## Decision

Build the first teacher-facing chapter graph with:

- existing React 19, TypeScript, Vite, Tailwind, Mantine, and Lucide;
- [`@xyflow/react`](https://reactflow.dev/) for the interactive graph canvas;
- [`@dagrejs/dagre`](https://github.com/dagrejs/dagre) for deterministic
  top-to-bottom hierarchy layout;
- the existing corpus API as the semantic source of truth;
- a synchronized HTML outline and source-details panel as equal navigation
  surfaces, not as graph fallbacks;
- existing Vitest coverage, plus frontend interaction-test setup and
  Playwright/Chrome performance traces for #171.

Do not add a graph database, Graphology, Cytoscape.js, Sigma.js, G6, Zustand,
or a server-side layout engine for this slice. Do not store graph coordinates
in Postgres.

Use ELK.js only if the #169 fixture demonstrates a specific Dagre failure such
as unacceptable compound-node layout or unresolvable edge crossings. Load it
dynamically if adopted.

## Why This Fits the Product

The current `ChapterMapNode` and `ChapterMapEdge` API already provides the hard
part:

- stable semantic node and edge identities;
- document, hierarchy, node type, source range, page range, count, and preview;
- deterministic `contains`, `next`, and evidence-backed `references` edges;
- a node-detail endpoint returning exact `TextbookElements`, excerpts, pages,
  element types, and assets.

The browser therefore needs a navigational projection of canonical data, not a
new graph model. The representative graph is 40–100 nodes and hierarchy-first.
Rich topic cards, readable labels, keyboard focus, deterministic reading order,
and synchronized source inspection matter more than rendering thousands of
points.

## What GitNexus Does Well

GitNexus currently uses Sigma.js, Graphology, ForceAtlas2, no-overlap layout,
and custom tree/circle layouts. Its renderer choice is rational for arbitrary
repositories that may contain thousands of densely connected symbols.

The transferable part is its interaction architecture:

1. One selected-node state synchronizes canvas, tree, search, and detail panel.
2. Search focuses and selects a result instead of merely filtering labels.
3. The left tree auto-expands to reveal the graph selection.
4. Selection emphasizes the node and neighborhood while dimming unrelated
   content.
5. Users can focus the camera, fit the graph, clear selection, filter edge
   types, and restrict visible depth.
6. Expensive layout work is separated from simple hover and selection styling.

Relevant source:

- [GraphCanvas selection and view synchronization](https://github.com/abhigyanpatwari/GitNexus/blob/6dc6544365aff48faa1129b0eb9ce5b6b7fc0843/gitnexus-web/src/components/GraphCanvas.tsx)
- [Search and keyboard result navigation](https://github.com/abhigyanpatwari/GitNexus/blob/6dc6544365aff48faa1129b0eb9ce5b6b7fc0843/gitnexus-web/src/components/Header.tsx)
- [Synchronized searchable tree](https://github.com/abhigyanpatwari/GitNexus/blob/6dc6544365aff48faa1129b0eb9ce5b6b7fc0843/gitnexus-web/src/components/FileTreePanel.tsx)
- [Reducer-based node and edge emphasis](https://github.com/abhigyanpatwari/GitNexus/blob/6dc6544365aff48faa1129b0eb9ce5b6b7fc0843/gitnexus-web/src/hooks/useSigma.ts)

We should copy those interaction principles, not GitNexus's rendering stack.
For the NCERT map, a force layout would make the same chapter move between
visits and weaken the textbook's authored hierarchy.

## Recommended Browser Experience

Use a three-surface workspace:

```text
┌────────────────┬──────────────────────────────┬─────────────────────┐
│ Search/Outline │ Chapter graph               │ NCERT source        │
│                │                              │                     │
│ Carbon...      │ Chapter → Section → Topic   │ Title, pages, type  │
│  4.1 ...       │         ↘ landmarks          │ Excerpt/elements    │
│  4.2 ...       │                              │ Figures/tables      │
└────────────────┴──────────────────────────────┴─────────────────────┘
```

### Default view

- Show `contains` edges only.
- Use a vertical layered layout matching textbook reading order.
- Render document, section/topic, and landmark nodes differently.
- Fit the initial graph once; do not continuously run layout.
- Keep `next` and `references` hidden until a later explicit overlay.

### Explore

- Hover or keyboard focus highlights ancestors, immediate children, and their
  hierarchy edges without changing the locked selection.
- Click or Enter locks selection and loads source details.
- Search selects, expands the outline path, focuses the camera, and opens the
  same details.
- Escape or canvas click clears locked selection.
- Collapse/expand recomputes layout only when the visible node set changes.
- Animate node-position and viewport changes after collapse/expand; respect
  `prefers-reduced-motion`.
- If the full chapter becomes noisy, show the selected/expanded subtree with
  breadcrumbs back to the chapter root.

### Accessible navigation

React Flow provides keyboard and screen-reader support, but the graph must not
be the only navigation mechanism. The outline should use ordinary focusable
HTML controls with hierarchical labels, visible focus, expansion state, and
selection state. The details panel should have a stable heading and receive
programmatic focus only when the user's action warrants it.

State must not rely on color alone. Combine color with border weight, opacity,
icons, labels, and `aria-current`/expanded state. Respect
`prefers-reduced-motion`.

## Frontend Architecture

Keep one page-level state owner:

```ts
type ChapterGraphState = {
  selectedNodeId: string | null;
  previewNodeId: string | null;
  expandedNodeIds: Set<string>;
  searchQuery: string;
};
```

Treat `expandedNodeIds` as immutable React state: every change creates a new
`Set` reference. Do not mutate the current set in place.

Derive the rest with pure functions:

- `mapChapterGraph(apiResponse)` validates and indexes nodes/edges.
- `getVisibleSubgraph(graph, expandedNodeIds, selectedNodeId)` filters nodes.
- `layoutChapterGraph(nodes, containsEdges)` returns React Flow positions.
- `getEmphasis(graph, previewNodeId, selectedNodeId)` returns active and dimmed
  node/edge ID sets.

Use `Map` and `Set` adjacency indexes. At 40–100 nodes, a graph-analysis
framework is unnecessary. Memoize the API mapping, visible subgraph, layout
result, and custom node components. Hover should update only emphasis state; it
must not call the API or layout function.

The API exposes parent IDs rather than an explicit hierarchy depth. Build and
validate depth from parent pointers while mapping the response; do not infer
depth from title numbering. Give graph nodes a fixed width with bounded,
wrapped/truncated titles and pass explicit width/height estimates to Dagre so
layout remains deterministic without a render-measure-relayout cycle.

Suggested module boundaries:

```text
frontend/src/pages/chapter-graph.page.tsx
frontend/src/components/chapter-graph/
  chapter-graph-workspace.component.tsx
  chapter-graph-canvas.component.tsx
  chapter-map-node.component.tsx
  chapter-map-outline.component.tsx
  chapter-map-source-panel.component.tsx
frontend/src/hooks/useChapterGraph.hook.ts
frontend/src/lib/chapter-graph.ts
frontend/src/lib/chapter-graph-layout.ts
```

The route should address an explicit `TextbookDocument`, for example
`/corpus/documents/:documentId/map`. Do not resolve a graph from chapter slug
alone because multiple immutable extractions may later exist for one Chapter.

## Technology Comparison

Versions and registry metadata were checked on 2026-06-13. Approximate bundle
figures come from a disposable esbuild production bundle with React and
ReactDOM externalized. They are comparative measurements, not final Vite build
budgets.

| Stack                        | Approx. gzip | Fit                                                                                                               | Decision                               |
| ---------------------------- | -----------: | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| React Flow 12.11 + Dagre 3.0 |        72 KB | HTML custom nodes, React state, pan/zoom, selection, deterministic layered layout                                 | **Use**                                |
| React Flow + ELK.js 0.11     |       500 KB | Strong compound/layered layout, but much heavier and EPL-2.0                                                      | Fallback only                          |
| Sigma 3 + Graphology 0.26    |        38 KB | Excellent WebGL scale and graph algorithms; canvas labels/nodes are less suitable for rich accessible topic cards | Do not use now                         |
| Cytoscape.js 3.34            |       141 KB | Mature graph analysis and many layouts; imperative integration and less natural React/HTML node UI                | Reconsider for dense conceptual graphs |
| AntV G6 5.1                  |       422 KB | Broad all-in-one graph framework                                                                                  | Too large and broad for this slice     |
| Reagraph 4.31                | Not selected | React/WebGL, but pulls Three.js, react-three-fiber, force layouts, and related dependencies                       | Wrong complexity profile               |

The React Flow core measured about 59 KB gzip and Dagre about 14 KB gzip in
isolation. Issue #169 should record the actual route chunk delta from the
project's Vite build because lazy-loading the page should keep this cost away
from the dashboard and editor routes.

## Delivery Across Issues

### #169: tracer bullet

1. Add Zod contracts and API functions for chapter map and node details.
2. Add a lazy authenticated route addressed by `documentId`.
3. Build the deterministic mapper and Dagre layout as pure tested functions.
4. Render the three synchronized surfaces.
5. Show hierarchy only and fetch source details on locked selection.
6. Add loading, error, empty, and missing-source states.
7. Record the actual route chunk delta and tablet/desktop screenshots.

### #170: interaction

1. Add preview versus locked-selection state.
2. Precompute parent/children adjacency and ancestor paths.
3. Add search, outline auto-expansion, collapse/expand, and subtree focus.
4. Apply 150–250 ms opacity, stroke, and transform transitions only.
5. Add keyboard parity and predictable focus restoration.

### #171: measured acceptance

1. Commit a deterministic 40–100 node fixture.
2. Add browser tests for hover, keyboard selection, search, collapse, and
   graph/outline synchronization.
3. Capture Chrome traces for hover, pan, zoom, selection, and expansion.
4. Verify hover does not run layout, fetch, or recreate every node.
5. Check long tasks, frame timing, reduced motion, contrast, and responsive
   widths.

The 60 FPS target should be treated as an interaction measurement, not a claim
that every frame of every browser trace must be exactly 16.7 ms. Repeated tasks
over 50 ms are the actionable failure signal.

## Future Extensions

### Topic-scoped question generation

Do not send topic labels to generation. Send stable
`ChapterMapNode.stable_node_id` values together with explicit
`TextbookDocument` identity. The backend can resolve those IDs to source ranges
and later to `RetrievalChunks`.

Keep graph exploration selection separate from a future multi-select
"generation scope." A teacher may inspect one node while choosing several
nodes for a paper.

This preserves the domain distinction between corpus-owned
`ChapterMapNode` and freeform `Question.topic_names`.

### Frequently asked or "hot" topics

This requires a data relationship, not a different renderer. The current
`QuestionUsage` records approved-paper use per Question, while
`Question.topic_names` is freeform and cannot safely identify a
`ChapterMapNode`.

A later slice should create an evidence-backed association from Question to
one or more ChapterMapNodes, then return metrics keyed by stable node ID:

```json
{
  "stable_node_id": "section:4.2.1",
  "question_count": 18,
  "approved_usage_count": 42,
  "recent_usage_count": 9
}
```

Render metrics as an optional overlay (badge, border intensity, or heat scale)
without changing the canonical layout. Keep the semantic chapter-map endpoint
separate from teacher-specific analytics where practical.

### Conceptual relationships

If later evidence-backed conceptual edges produce a dense network rather than
a hierarchy, first test Cytoscape.js in a separate exploration view. Do not
replace the stable hierarchy view. Sigma.js becomes attractive only when graph
size reaches hundreds or thousands of visible nodes and WebGL scale outweighs
rich HTML-node and accessibility requirements.

## Risks and Guardrails

- **Graph becomes decorative:** every node action must lead to useful source
  inspection or generation scope.
- **Layout instability:** sort nodes and edges by stable semantic keys before
  Dagre; never use random jitter.
- **Too much visible structure:** default to hierarchy; reveal references only
  on demand.
- **Hover causes rerenders:** keep node data stable and derive emphasis as ID
  sets.
- **Canvas-only accessibility:** keep the synchronized outline first-class.
- **Premature analytics model:** do not equate `Question.topic_names` with
  ChapterMapNode identity.
- **Bundle leakage:** lazy-load the route and measure the Vite chunk.
- **Missing interaction-test runtime:** #171 must add `@testing-library/react`
  with a jsdom Vitest environment and `@playwright/test` with a frontend
  Playwright configuration before its required interaction/browser tests.

## Primary Sources

- [React Flow documentation](https://reactflow.dev/)
- [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility)
- [React Flow performance guidance](https://reactflow.dev/learn/advanced-use/performance)
- [React Flow Dagre example](https://reactflow.dev/examples/layout/dagre)
- [Dagre repository](https://github.com/dagrejs/dagre)
- [ELK.js repository](https://github.com/kieler/elkjs)
- [Cytoscape.js documentation](https://js.cytoscape.org/)
- [Sigma.js documentation](https://www.sigmajs.org/docs/)
- [Graphology documentation](https://graphology.github.io/)
- [AntV G6 documentation](https://g6.antv.antgroup.com/en/)
- [GitNexus repository](https://github.com/abhigyanpatwari/GitNexus)
- [MDN `prefers-reduced-motion`](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion)
- [web.dev long-task guidance](https://web.dev/articles/optimize-long-tasks)
- [WCAG 2.2 contrast criterion](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
