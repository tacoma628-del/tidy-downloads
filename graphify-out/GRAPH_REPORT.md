# Graph Report - tidy-downloads  (2026-08-30)

## Corpus Check
- Corpus is ~1,024 words - fits in a single context window. You may not need a graph.

## Summary
- 37 nodes · 73 edges · 8 communities (5 shown, 3 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.91)
- Token cost: 1,450 input · 2,100 output

## Community Hubs (Navigation)
- Planning Rules Under Test
- Apply And Move Logging
- CLI Entry And Arguments
- Test Fixture Setup
- Type And Month Classification
- Apply Path Test Harness
- Move Planning Core
- Collision And Overwrite Safety

## God Nodes (most connected - your core abstractions)
1. `touch()` - 9 edges
2. `apply_moves()` - 8 edges
3. `PlanMovesTest` - 7 edges
4. `plan_moves()` - 7 edges
5. `ApplyMovesTest` - 5 edges
6. `month_folder()` - 5 edges
7. `_unique_against()` - 5 edges
8. `parse_args()` - 5 edges
9. `classify()` - 4 edges
10. `is_skippable()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Move-Only, Never Delete Or Overwrite` --rationale_for--> `apply_moves()`  [INFERRED]
  README.md → tidy_downloads.py
- `Last-Modified Time As Month Source` --rationale_for--> `month_folder()`  [INFERRED]
  README.md → tidy_downloads.py
- `In-Progress Download Skipping` --references--> `is_skippable()`  [INFERRED]
  README.md → tidy_downloads.py
- `Name Collision Suffixing` --references--> `_unique_against()`  [INFERRED]
  README.md → tidy_downloads.py
- `Move Log For Undo` --references--> `apply_moves()`  [INFERRED]
  README.md → tidy_downloads.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Safety Guarantees Of A Destructive-By-Opt-In Tool** — readme_preview_by_default, readme_move_only_never_delete, readme_in_progress_download_skip, readme_collision_suffix, readme_move_log [INFERRED 0.85]

## Communities (8 total, 3 thin omitted)

### Community 0 - "Planning Rules Under Test"
Cohesion: 0.38
Nodes (3): In-Progress Download Skipping, PlanMovesTest, touch()

### Community 1 - "Apply And Move Logging"
Cohesion: 0.40
Nodes (5): Move Log For Undo, Preview By Default, Tidy Downloads (README), apply_moves(), ApplyResult

### Community 2 - "CLI Entry And Arguments"
Cohesion: 0.60
Nodes (4): Namespace, default_downloads(), main(), parse_args()

### Community 4 - "Type And Month Classification"
Cohesion: 0.50
Nodes (4): Last-Modified Time As Month Source, Type/YYYY-MM Folder Layout, classify(), month_folder()

### Community 6 - "Move Planning Core"
Cohesion: 0.83
Nodes (4): is_skippable(), plan_moves(), Path, _unique_against()

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `touch()` connect `Planning Rules Under Test` to `Apply And Move Logging`, `Test Fixture Setup`, `Apply Path Test Harness`, `Collision And Overwrite Safety`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **Why does `PlanMovesTest` connect `Planning Rules Under Test` to `Test Fixture Setup`, `Apply Path Test Harness`, `Collision And Overwrite Safety`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `apply_moves()` connect `Apply And Move Logging` to `CLI Entry And Arguments`, `Move Planning Core`, `Collision And Overwrite Safety`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `apply_moves()` (e.g. with `Move Log For Undo` and `Move-Only, Never Delete Or Overwrite`) actually correct?**
  _`apply_moves()` has 3 INFERRED edges - model-reasoned connections that need verification._