# Changelog

All notable changes to Memory Anchor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2025-12-31

### Added

#### ContextBudgetManager (Phase 1)
- Token budget management for each memory layer (L0:500, L1:200, L2:500, L3:2000, L4:300)
- CLI command `./ma budget` to view context usage
- Configurable via `MA_BUDGET_*` environment variables

#### SafetyFilter (Phase 2)
- PII detection and redaction (email, phone, ID card, credit card, IP, API keys)
- Configurable sensitive word filtering
- Content length limits (default ≤ 2000 chars)
- Actions: `block`, `redact`, or `warn`

#### Bi-temporal Time Awareness (Phase 3)
- New fields: `valid_at` (effective time) and `expires_at` (expiration time)
- `TemporalQuery` class for time-based queries:
  - `at_time(t)` - query memories valid at a specific time
  - `in_range(start, end)` - query memories within a time range
  - `only_valid()` - query only non-expired memories
- MCP tools updated with `as_of`, `start_time`, `end_time`, `include_expired` parameters
- Backward compatible: `valid_at=None` means immediately effective

#### ConflictDetector MVP (Phase 4)
- Rule-based conflict detection engine (no LLM required)
- Conflict types:
  - `temporal`: overlapping valid_at within 7 days
  - `source`: different created_by but similar content
  - `confidence`: confidence difference > 0.3
- CLI command `./ma conflicts --project NAME --verbose`
- Non-blocking: returns `conflict_warning` without preventing writes

### Changed
- `MemoryKernel` now auto-initializes `ConflictDetector` (can be disabled)
- `add_memory()` returns `conflict_warning` field when conflicts detected

### Technical
- 621 tests passing (up from 498 in v2.1.0)
- References: MemoryAgentBench (arXiv:2507.05257), Zep Temporal KG (arXiv:2501.13956)

---

## [2.1.0] - 2025-12-28

### Added
- Memory Graph visualization (D3.js force-directed graph)
- Timeline visualization (Recharts stacked area chart)
- Batch operations (multi-select delete/verify)
- Multi-project isolation (ProjectSelector component)
- i18n internationalization (Chinese/English, 143 translation keys)
- Memory Refiner with CoDA context decoupling

### Changed
- Updated test suite to 498 tests

---

## [2.0.0] - 2025-12-24

### Added
- Five-layer cognitive memory model:
  - L0: identity_schema (core identity, 3x approval)
  - L1: active_context (working memory, in-process only)
  - L2: event_log (episodic memory with TTL)
  - L3: verified_fact (semantic memory, permanent)
  - L4: operational_knowledge (procedural, .ai/operations/)
- Constitution layer with 3x approval mechanism
- Event logging with when/where/who fields
- Memory promotion (L2 → L3)
- Checklist integration (战略层 + 战术层)

### Changed
- Renamed layers for cognitive science alignment
- Backward compatible: old names (`constitution`, `fact`, `session`) still work

---

## [1.0.0] - 2025-12-15

### Added
- Initial release
- Three-layer memory model (constitution/fact/session)
- Qdrant vector storage integration
- MCP Server for Claude Code
- Basic CLI tools (init, serve, status, doctor)
- FastAPI HTTP API
