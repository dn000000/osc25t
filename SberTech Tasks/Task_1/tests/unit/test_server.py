"""
Unit tests for web server module.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.server import validate_graph_type, create_app, load_graph_file


class TestValidateGraphType:
    """Tests for validate_graph_type function"""

    def test_validate_build_type(self):
        """Test that 'build' is a valid graph type"""
        assert validate_graph_type("build") is True

    def test_validate_runtime_type(self):
        """Test that 'runtime' is a valid graph type"""
        assert validate_graph_type("runtime") is True

    def test_reject_invalid_type(self):
        """Test that invalid types are rejected"""
        assert validate_graph_type("invalid") is False
        assert validate_graph_type("other") is False

    def test_reject_path_traversal(self):
        """Test that path traversal attempts are rejected"""
        assert validate_graph_type("../build") is False
        assert validate_graph_type("build/../runtime") is False
        assert validate_graph_type("/etc/passwd") is False

    def test_reject_special_characters(self):
        """Test that special characters are rejected"""
        assert validate_graph_type("build;rm -rf") is False
        assert validate_graph_type("runtime|cat") is False
        assert validate_graph_type("build graph") is False

    def test_reject_empty_string(self):
        """Test that empty string is rejected"""
        assert validate_graph_type("") is False


class TestCreateApp:
    """Tests for create_app function"""

    def test_create_app_default_dirs(self):
        """Test app creation with default directories"""
        test_app = create_app()

        assert test_app is not None
        # Check that DATA_DIR ends with 'data' (can be absolute or relative)
        assert test_app.config["DATA_DIR"].endswith("data")
        assert test_app.config["JSON_SORT_KEYS"] is False

    def test_create_app_custom_dirs(self):
        """Test app creation with custom directories"""
        test_app = create_app(
            data_dir="custom_data", template_dir="custom_templates", static_dir="custom_static"
        )

        # Check that paths end with expected directory names
        assert test_app.config["DATA_DIR"].endswith("custom_data")
        assert test_app.template_folder.endswith("custom_templates")
        assert test_app.static_folder.endswith("custom_static")

    def test_create_app_logging_configured(self):
        """Test that logging is configured"""
        test_app = create_app()

        assert test_app.logger is not None


class TestLoadGraphFile:
    """Tests for load_graph_file function"""

    @patch("src.server.app")
    def test_load_valid_graph_file(self, mock_app):
        """Test loading a valid graph file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_data = {
                "graph_type": "runtime",
                "nodes": [{"id": "pkg1", "label": "pkg1"}],
                "edges": [{"source": "pkg1", "target": "pkg2"}],
            }

            graph_file = Path(tmpdir) / "runtime_graph.json"
            with open(graph_file, "w") as f:
                json.dump(graph_data, f)

            # Mock the app config
            mock_app.config = {"DATA_DIR": tmpdir}

            result = load_graph_file("runtime")

            assert result is not None
            assert result["graph_type"] == "runtime"
            assert len(result["nodes"]) == 1
            assert len(result["edges"]) == 1

    @patch("src.server.app")
    def test_load_nonexistent_file(self, mock_app):
        """Test loading a non-existent graph file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()

            mock_app.config = {"DATA_DIR": str(empty_dir)}

            result = load_graph_file("runtime")

            assert result is None

    @patch("src.server.app")
    def test_load_invalid_json(self, mock_app):
        """Test loading a file with invalid JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_file = Path(tmpdir) / "runtime_graph.json"
            graph_file.write_text("{ invalid json }")

            mock_app.config = {"DATA_DIR": tmpdir}

            result = load_graph_file("runtime")

            assert result is None

    def test_load_invalid_graph_type(self):
        """Test loading with invalid graph type"""
        result = load_graph_file("invalid_type")
        assert result is None


class TestRoutes:
    """Tests for Flask routes using the global app instance"""

    def test_validate_graph_type_in_routes(self):
        """Test that route validation works correctly"""
        # Test valid types
        assert validate_graph_type("build") is True
        assert validate_graph_type("runtime") is True

        # Test invalid types
        assert validate_graph_type("../etc/passwd") is False
        assert validate_graph_type("invalid") is False

    def test_app_has_required_routes(self):
        """Test that the app has all required routes"""
        from src.server import app

        # Get all registered routes
        routes = [str(rule) for rule in app.url_map.iter_rules()]

        # Check for required routes
        assert "/" in routes
        assert "/api/graphs" in routes
        assert "/api/graph/runtime" in routes
        assert "/api/graph/build" in routes
        assert "/static/<path:filename>" in routes

    def test_app_has_error_handlers(self):
        """Test that error handlers are registered"""
        from src.server import app

        # Check that error handlers exist
        assert 404 in app.error_handler_spec[None]
        assert 500 in app.error_handler_spec[None]
        assert None in app.error_handler_spec[None]  # Generic exception handler


class TestServerConfiguration:
    """Tests for server configuration and setup"""

    def test_app_configuration(self):
        """Test that app is properly configured"""
        from src.server import app

        assert app is not None
        assert "DATA_DIR" in app.config
        assert app.config["JSON_SORT_KEYS"] is False

    def test_app_has_before_request_handler(self):
        """Test that before_request handler is registered"""
        from src.server import app

        # Check that before_request handlers exist
        assert len(app.before_request_funcs[None]) > 0

    def test_app_has_after_request_handler(self):
        """Test that after_request handler is registered"""
        from src.server import app

        # Check that after_request handlers exist
        assert len(app.after_request_funcs[None]) > 0
