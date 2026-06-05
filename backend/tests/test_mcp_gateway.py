"""Unit tests for the MCP gateway pure helpers.

Run from the backend/ directory:
    pytest tests/test_mcp_gateway.py -q
"""
from app.api.v1.mcp_gateway import _auto_scope, _slugify


class TestAutoScope:
    def test_basic_prefix_and_tool(self):
        assert _auto_scope("mcp.crm", "contacts.read") == "mcp.crm.contacts.read"

    def test_normalizes_spaces_and_punctuation(self):
        # "Send Email!" -> lowercase, non [a-z0-9.] collapsed to "_", trimmed
        assert _auto_scope("mcp", "Send Email!") == "mcp.send_email"

    def test_empty_prefix_defaults_to_mcp(self):
        assert _auto_scope("", "foo") == "mcp.foo"

    def test_trailing_dot_in_prefix_is_trimmed(self):
        assert _auto_scope("mcp.crm.", "x") == "mcp.crm.x"

    def test_empty_tool_name_falls_back_to_prefix(self):
        assert _auto_scope("mcp", "") == "mcp"

    def test_preserves_existing_dotted_tool_names(self):
        assert _auto_scope("mcp.db", "tables.query") == "mcp.db.tables.query"


class TestSlugify:
    def test_simple(self):
        assert _slugify("Production CRM MCP") == "production-crm-mcp"

    def test_strips_and_collapses(self):
        assert _slugify("  Foo!!  Bar  ") == "foo-bar"

    def test_empty_defaults(self):
        assert _slugify("") == "server"

    def test_truncates_to_64(self):
        assert len(_slugify("x" * 200)) <= 64
