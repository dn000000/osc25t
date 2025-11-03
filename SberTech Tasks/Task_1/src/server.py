"""
Web server module for serving dependency graph visualization.

This module provides a Flask-based web server with API endpoints
for accessing dependency graph data and serving the visualization interface.
"""

import logging
from pathlib import Path
from typing import Dict, Optional
from flask import Flask, render_template, jsonify, send_from_directory, request
from werkzeug.exceptions import HTTPException
import json
import re

from src.validation import validate_file_path, validate_file_size, ValidationError

logger = logging.getLogger(__name__)


def validate_graph_type(graph_type: str) -> bool:
    """
    Validate graph type parameter.

    Args:
        graph_type: Graph type to validate

    Returns:
        True if valid, False otherwise
    """
    # Only allow alphanumeric characters and underscores
    return bool(re.match(r"^[a-zA-Z0-9_]+$", graph_type)) and graph_type in ["build", "runtime"]


def create_app(
    data_dir: str = "data", template_dir: str = "templates", static_dir: str = "static"
) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        data_dir: Directory containing graph JSON files
        template_dir: Directory containing HTML templates
        static_dir: Directory containing static files (CSS, JS)

    Returns:
        Configured Flask application instance
    """
    # Get the project root directory (parent of src/)
    project_root = Path(__file__).parent.parent
    
    # Convert relative paths to absolute paths from project root
    template_path = project_root / template_dir
    static_path = project_root / static_dir
    data_path = project_root / data_dir
    
    app = Flask(
        __name__, 
        template_folder=str(template_path), 
        static_folder=str(static_path), 
        static_url_path="/static"
    )

    # Store configuration
    app.config["DATA_DIR"] = str(data_path)
    app.config["JSON_SORT_KEYS"] = False

    # Configure logging
    app.logger.setLevel(logging.INFO)

    logger.info(f"Flask app created with data_dir={data_path}, template_dir={template_path}, static_dir={static_path}")

    return app


# Create the Flask application instance
app = create_app()


@app.route("/")
def index():
    """
    Serve the main HTML page for graph visualization.

    Returns:
        Rendered HTML template
    """
    logger.info("Serving main page")
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    """
    Serve static files (CSS, JavaScript).

    Args:
        filename: Path to static file

    Returns:
        Static file content
    """
    # Validate filename to prevent directory traversal
    try:
        # Ensure filename doesn't contain path traversal attempts
        if ".." in filename or filename.startswith("/") or "\\" in filename:
            logger.warning(f"Suspicious static file request: {filename}")
            return jsonify({"error": "Invalid file path"}), 400

        # Validate the full path is within static folder
        full_path = Path(app.static_folder) / filename
        validate_file_path(str(full_path), base_dir=app.static_folder, must_exist=True)

    except ValidationError as e:
        logger.warning(f"Invalid static file request: {filename} - {e}")
        return jsonify({"error": "Invalid file path"}), 400

    return send_from_directory(app.static_folder, filename)


def load_graph_file(graph_type: str) -> Optional[Dict]:
    """
    Load a graph JSON file from the data directory.

    Args:
        graph_type: Type of graph ('build' or 'runtime')

    Returns:
        Graph data as dictionary, or None if file not found
    """
    # Validate graph_type to prevent path traversal
    if not validate_graph_type(graph_type):
        logger.warning(f"Invalid graph type requested: {graph_type}")
        return None

    data_dir = Path(app.config["DATA_DIR"])
    graph_file = data_dir / f"{graph_type}_graph.json"

    try:
        # Validate file path is within data directory
        validate_file_path(str(graph_file), base_dir=str(data_dir), must_exist=True)

        # Validate file size (allow larger graphs for big repositories)
        validate_file_size(graph_file, max_size_mb=500)

        with open(graph_file, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        logger.info(
            f"Loaded {graph_type} graph: {len(graph_data.get('nodes', []))} nodes, "
            f"{len(graph_data.get('edges', []))} edges"
        )
        return graph_data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {graph_file}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading graph file {graph_file}: {e}")
        return None


@app.route("/api/graphs")
def list_graphs():
    """
    List available dependency graphs.

    Returns:
        JSON response with list of available graphs and their metadata
    """
    logger.info("API request: list graphs")

    data_dir = Path(app.config["DATA_DIR"])
    available_graphs = []

    # Check for runtime graph
    runtime_file = data_dir / "runtime_graph.json"
    if runtime_file.exists():
        try:
            with open(runtime_file, "r", encoding="utf-8") as f:
                runtime_data = json.load(f)
            available_graphs.append(
                {
                    "type": "runtime",
                    "name": "Runtime Dependencies",
                    "nodes": len(runtime_data.get("nodes", [])),
                    "edges": len(runtime_data.get("edges", [])),
                    "available": True,
                }
            )
        except Exception as e:
            logger.error(f"Error reading runtime graph metadata: {e}")
            available_graphs.append(
                {
                    "type": "runtime",
                    "name": "Runtime Dependencies",
                    "available": False,
                    "error": str(e),
                }
            )
    else:
        available_graphs.append(
            {
                "type": "runtime",
                "name": "Runtime Dependencies",
                "available": False,
                "error": "Graph file not found",
            }
        )

    # Check for build graph
    build_file = data_dir / "build_graph.json"
    if build_file.exists():
        try:
            with open(build_file, "r", encoding="utf-8") as f:
                build_data = json.load(f)
            available_graphs.append(
                {
                    "type": "build",
                    "name": "Build Dependencies",
                    "nodes": len(build_data.get("nodes", [])),
                    "edges": len(build_data.get("edges", [])),
                    "available": True,
                }
            )
        except Exception as e:
            logger.error(f"Error reading build graph metadata: {e}")
            available_graphs.append(
                {"type": "build", "name": "Build Dependencies", "available": False, "error": str(e)}
            )
    else:
        available_graphs.append(
            {
                "type": "build",
                "name": "Build Dependencies",
                "available": False,
                "error": "Graph file not found",
            }
        )

    return jsonify({"graphs": available_graphs, "data_directory": str(data_dir)})


@app.route("/api/graph/build")
def get_build_graph():
    """
    Get the build dependency graph data.

    Returns:
        JSON response with build dependency graph
    """
    logger.info("API request: get build graph")

    graph_data = load_graph_file("build")

    if graph_data is None:
        return (
            jsonify(
                {
                    "error": "Build dependency graph not found",
                    "message": "Please run the main.py script to generate dependency graphs",
                }
            ),
            404,
        )

    return jsonify(graph_data)


@app.route("/api/graph/runtime")
def get_runtime_graph():
    """
    Get the runtime dependency graph data.

    Returns:
        JSON response with runtime dependency graph
    """
    logger.info("API request: get runtime graph")

    graph_data = load_graph_file("runtime")

    if graph_data is None:
        return (
            jsonify(
                {
                    "error": "Runtime dependency graph not found",
                    "message": "Please run the main.py script to generate dependency graphs",
                }
            ),
            404,
        )

    return jsonify(graph_data)


@app.errorhandler(404)
def not_found_error(error):
    """
    Handle 404 Not Found errors.

    Args:
        error: The error object

    Returns:
        JSON response with error details
    """
    logger.warning(f"404 error: {request.url}")

    return (
        jsonify(
            {
                "error": "Not Found",
                "message": f"The requested resource was not found: {request.path}",
                "status": 404,
            }
        ),
        404,
    )


@app.errorhandler(500)
def internal_error(error):
    """
    Handle 500 Internal Server errors.

    Args:
        error: The error object

    Returns:
        JSON response with error details
    """
    logger.error(f"500 error: {error}", exc_info=True)

    return (
        jsonify(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please check the server logs.",
                "status": 500,
            }
        ),
        500,
    )


@app.errorhandler(Exception)
def handle_exception(error):
    """
    Handle all unhandled exceptions.

    Args:
        error: The error object

    Returns:
        JSON response with error details
    """
    # Pass through HTTP errors
    if isinstance(error, HTTPException):
        return error

    # Log the error
    logger.error(f"Unhandled exception: {error}", exc_info=True)

    # Return 500 error
    return (
        jsonify(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please check the server logs.",
                "status": 500,
            }
        ),
        500,
    )


@app.before_request
def log_request():
    """Log incoming requests for debugging and monitoring."""
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")


@app.after_request
def log_response(response):
    """
    Log response status for debugging and monitoring.

    Args:
        response: Flask response object

    Returns:
        Unmodified response object
    """
    logger.info(f"{request.method} {request.path} -> {response.status_code}")
    return response


if __name__ == "__main__":
    # Run the development server
    logger.info("Starting Flask development server...")
    app.run(host="0.0.0.0", port=5000, debug=True)
