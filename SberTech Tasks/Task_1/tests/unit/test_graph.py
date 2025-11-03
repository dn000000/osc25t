"""
Unit tests for the graph builder module.
"""

import pytest
import json
from src.graph import DependencyGraph, Node, Edge, NodeColor


class TestNode:
    """Tests for Node class."""

    def test_node_creation(self):
        """Test creating a node with metadata."""
        node = Node(id="test-pkg", label="test-pkg-1.0", metadata={"version": "1.0"})
        assert node.id == "test-pkg"
        assert node.label == "test-pkg-1.0"
        assert node.metadata["version"] == "1.0"

    def test_node_to_dict(self):
        """Test node serialization to dictionary."""
        node = Node(id="test-pkg", label="test-pkg", metadata={"arch": "x86_64"})
        node_dict = node.to_dict()
        assert node_dict["id"] == "test-pkg"
        assert node_dict["label"] == "test-pkg"
        assert node_dict["metadata"]["arch"] == "x86_64"


class TestEdge:
    """Tests for Edge class."""

    def test_edge_creation(self):
        """Test creating an edge."""
        edge = Edge(source="pkg-a", target="pkg-b", edge_type="requires")
        assert edge.source == "pkg-a"
        assert edge.target == "pkg-b"
        assert edge.edge_type == "requires"

    def test_edge_to_dict(self):
        """Test edge serialization to dictionary."""
        edge = Edge(source="pkg-a", target="pkg-b")
        edge_dict = edge.to_dict()
        assert edge_dict["source"] == "pkg-a"
        assert edge_dict["target"] == "pkg-b"
        assert edge_dict["type"] == "dependency"


class TestDependencyGraph:
    """Tests for DependencyGraph class."""

    def test_empty_graph(self):
        """Test creating an empty graph."""
        graph = DependencyGraph()
        assert graph.node_count() == 0
        assert graph.edge_count() == 0

    def test_add_node(self):
        """Test adding nodes to the graph."""
        graph = DependencyGraph()
        graph.add_node("pkg-a", {"version": "1.0"})
        graph.add_node("pkg-b")

        assert graph.node_count() == 2
        assert graph.has_node("pkg-a")
        assert graph.has_node("pkg-b")
        assert graph.nodes["pkg-a"].metadata["version"] == "1.0"

    def test_add_edge(self):
        """Test adding edges to the graph."""
        graph = DependencyGraph()
        graph.add_edge("pkg-a", "pkg-b")

        assert graph.node_count() == 2
        assert graph.edge_count() == 1
        assert "pkg-b" in graph.get_dependencies("pkg-a")
        assert "pkg-a" in graph.get_dependents("pkg-b")

    def test_duplicate_edge(self):
        """Test that duplicate edges are not added."""
        graph = DependencyGraph()
        graph.add_edge("pkg-a", "pkg-b")
        graph.add_edge("pkg-a", "pkg-b")

        assert graph.edge_count() == 1

    def test_build_graph_simple(self):
        """Test building a simple dependency graph."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b", "pkg-c"], "pkg-b": ["pkg-c"], "pkg-c": []}

        graph.build_graph(dependencies)

        assert graph.node_count() == 3
        assert graph.edge_count() == 3
        assert set(graph.get_dependencies("pkg-a")) == {"pkg-b", "pkg-c"}
        assert graph.get_dependencies("pkg-b") == ["pkg-c"]
        assert graph.get_dependencies("pkg-c") == []

    def test_build_graph_with_missing_packages(self):
        """Test building a graph with missing package dependencies."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b", "missing-pkg"], "pkg-b": []}

        graph.build_graph(dependencies)

        assert graph.node_count() == 3
        assert graph.has_node("missing-pkg")
        assert graph.nodes["missing-pkg"].metadata.get("placeholder") == "true"

    def test_build_graph_with_metadata(self):
        """Test building a graph with package metadata."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b"], "pkg-b": []}
        metadata = {
            "pkg-a": {"version": "1.0", "arch": "x86_64"},
            "pkg-b": {"version": "2.0", "arch": "noarch"},
        }

        graph.build_graph(dependencies, metadata)

        assert graph.nodes["pkg-a"].metadata["version"] == "1.0"
        assert graph.nodes["pkg-b"].metadata["arch"] == "noarch"

    def test_detect_cycles_no_cycle(self):
        """Test cycle detection with no cycles."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b"], "pkg-b": ["pkg-c"], "pkg-c": []}
        graph.build_graph(dependencies)

        cycles = graph.detect_cycles()
        assert len(cycles) == 0

    def test_detect_cycles_simple_cycle(self):
        """Test cycle detection with a simple cycle."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b"], "pkg-b": ["pkg-c"], "pkg-c": ["pkg-a"]}
        graph.build_graph(dependencies)

        cycles = graph.detect_cycles()
        assert len(cycles) == 1
        cycle = cycles[0]
        assert "pkg-a" in cycle
        assert "pkg-b" in cycle
        assert "pkg-c" in cycle

    def test_detect_cycles_self_loop(self):
        """Test cycle detection with a self-loop."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-a"]}
        graph.build_graph(dependencies)

        cycles = graph.detect_cycles()
        assert len(cycles) == 1
        assert cycles[0] == ["pkg-a", "pkg-a"]

    def test_detect_cycles_multiple_cycles(self):
        """Test cycle detection with multiple independent cycles."""
        graph = DependencyGraph()
        dependencies = {
            "pkg-a": ["pkg-b"],
            "pkg-b": ["pkg-a"],
            "pkg-c": ["pkg-d"],
            "pkg-d": ["pkg-c"],
        }
        graph.build_graph(dependencies)

        cycles = graph.detect_cycles()
        assert len(cycles) == 2

    def test_export_to_json(self):
        """Test JSON serialization of the graph."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b"], "pkg-b": []}
        graph.build_graph(dependencies)

        json_str = graph.export_to_json("runtime")
        data = json.loads(json_str)

        assert data["graph_type"] == "runtime"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

        node_ids = [node["id"] for node in data["nodes"]]
        assert "pkg-a" in node_ids
        assert "pkg-b" in node_ids

        edge = data["edges"][0]
        assert edge["source"] == "pkg-a"
        assert edge["target"] == "pkg-b"

    def test_to_dict(self):
        """Test dictionary conversion of the graph."""
        graph = DependencyGraph()
        dependencies = {"pkg-a": ["pkg-b", "pkg-c"], "pkg-b": [], "pkg-c": []}
        graph.build_graph(dependencies)

        graph_dict = graph.to_dict("build")

        assert graph_dict["graph_type"] == "build"
        assert len(graph_dict["nodes"]) == 3
        assert len(graph_dict["edges"]) == 2
