"""Shared fixtures for mageflow-mcp unit tests.

Phase 1 tests (model serialization and ABC enforcement) are pure Python and
require no fixtures. Fakeredis fixtures for tool-level tests will be added
in Phase 2 when tools need Redis-backed data retrieval.
"""
