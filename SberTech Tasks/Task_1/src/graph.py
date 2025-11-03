"""
Graph builder module for constructing and analyzing dependency graphs.

This module provides data structures and algorithms for building dependency graphs
from package information, detecting cycles, and exporting graphs for visualization.
"""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import json


class NodeColor(Enum):
    """Colors for DFS cycle detection algorithm."""

    WHITE = "white"  # Unvisited
    GRAY = "gray"  # Visiting
    BLACK = "black"  # Visited


@dataclass
class Node:
    """Represents a package node in the dependency graph."""

    id: str
    label: str
    metadata: Dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.id)

    def to_dict(self) -> Dict[str, object]:
        """Convert node to dictionary for JSON serialization."""
        return {"id": self.id, "label": self.label, "metadata": self.metadata}


@dataclass
class Edge:
    """Represents a dependency edge in the graph."""

    source: str
    target: str
    edge_type: str = "dependency"

    def __hash__(self) -> int:
        return hash((self.source, self.target))

    def to_dict(self) -> Dict[str, str]:
        """Convert edge to dictionary for JSON serialization."""
        return {"source": self.source, "target": self.target, "type": self.edge_type}


class DependencyGraph:
    """
    Main graph structure for representing package dependencies.

    Uses adjacency list representation for efficient traversal.
    Supports cycle detection and JSON serialization.
    """

    def __init__(self):
        """Initialize an empty dependency graph."""
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adjacency: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, package: str, metadata: Optional[Dict[str, str]] = None) -> None:
        """
        Add a node to the graph.

        Args:
            package: Package name (used as node ID)
            metadata: Optional metadata dictionary for the node
        """
        if package not in self.nodes:
            self.nodes[package] = Node(id=package, label=package, metadata=metadata or {})

    def add_edge(self, from_pkg: str, to_pkg: str, edge_type: str = "dependency") -> None:
        """
        Add a directed edge from one package to another.

        Args:
            from_pkg: Source package (dependent)
            to_pkg: Target package (dependency)
            edge_type: Type of dependency relationship
        """
        # Ensure both nodes exist
        self.add_node(from_pkg)
        self.add_node(to_pkg)

        # Add edge if it doesn't already exist
        if to_pkg not in self.adjacency[from_pkg]:
            edge = Edge(source=from_pkg, target=to_pkg, edge_type=edge_type)
            self.edges.append(edge)
            self.adjacency[from_pkg].add(to_pkg)
            self.reverse_adjacency[to_pkg].add(from_pkg)

    def get_dependencies(self, package: str) -> List[str]:
        """
        Get direct dependencies of a package.

        Args:
            package: Package name

        Returns:
            List of package names that this package depends on
        """
        return list(self.adjacency.get(package, set()))

    def get_dependents(self, package: str) -> List[str]:
        """
        Get packages that depend on this package.

        Args:
            package: Package name

        Returns:
            List of package names that depend on this package
        """
        return list(self.reverse_adjacency.get(package, set()))

    def has_node(self, package: str) -> bool:
        """Check if a node exists in the graph."""
        return package in self.nodes

    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)

    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self.edges)

    def build_graph(
        self,
        dependencies: Dict[str, List[str]],
        package_metadata: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        """
        Build the dependency graph from a dependency mapping.

        Args:
            dependencies: Dictionary mapping package names to lists of their dependencies
            package_metadata: Optional dictionary of package metadata

        Raises:
            ValueError: If dependencies dictionary is invalid
        """
        if not isinstance(dependencies, dict):
            raise ValueError("Dependencies must be a dictionary")

        if not dependencies:
            # Empty graph is valid
            return

        try:
            # First pass: Add all packages as nodes
            for package in dependencies.keys():
                metadata = package_metadata.get(package, {}) if package_metadata else {}
                self.add_node(package, metadata)

            # Second pass: Add all dependencies as nodes (including missing packages)
            missing_packages = set()
            for package, deps in dependencies.items():
                if not isinstance(deps, list):
                    raise ValueError(f"Dependencies for {package} must be a list")

                for dep in deps:
                    if not self.has_node(dep):
                        # Create placeholder node for missing package
                        self.add_node(dep, {"placeholder": "true"})
                        missing_packages.add(dep)

            if missing_packages:
                from logging import getLogger

                logger = getLogger(__name__)
                logger.debug(
                    f"Created {len(missing_packages)} placeholder nodes for missing packages"
                )

            # Third pass: Add edges for all dependency relationships
            for package, deps in dependencies.items():
                for dep in deps:
                    self.add_edge(package, dep)

        except Exception as e:
            from logging import getLogger

            logger = getLogger(__name__)
            logger.error(f"Error building graph: {e}", exc_info=True)
            raise

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies in the graph using DFS with color marking.

        Returns:
            List of cycles, where each cycle is a list of package names
        """
        if not self.nodes:
            return []

        try:
            colors: Dict[str, NodeColor] = {node: NodeColor.WHITE for node in self.nodes}
            parent: Dict[str, Optional[str]] = {node: None for node in self.nodes}
            cycles: List[List[str]] = []

            def dfs_visit(node: str, path: List[str]) -> None:
                """
                Visit a node during DFS traversal.

                Args:
                    node: Current node being visited
                    path: Current path from root to this node
                """
                colors[node] = NodeColor.GRAY
                path.append(node)

                for neighbor in self.adjacency.get(node, set()):
                    if colors[neighbor] == NodeColor.WHITE:
                        parent[neighbor] = node
                        dfs_visit(neighbor, path.copy())
                    elif colors[neighbor] == NodeColor.GRAY:
                        # Found a back edge - cycle detected
                        try:
                            cycle_start_idx = path.index(neighbor)
                            cycle = path[cycle_start_idx:] + [neighbor]
                            cycles.append(cycle)
                        except ValueError:
                            # Neighbor not in path, skip
                            pass

                colors[node] = NodeColor.BLACK

            # Run DFS from each unvisited node
            for node in self.nodes:
                if colors[node] == NodeColor.WHITE:
                    dfs_visit(node, [])

            return cycles

        except Exception as e:
            from logging import getLogger

            logger = getLogger(__name__)
            logger.error(f"Error detecting cycles: {e}", exc_info=True)
            return []

    def export_to_json(self, graph_type: str = "dependency") -> str:
        """
        Export the graph to JSON format for visualization.

        Args:
            graph_type: Type of graph (e.g., "runtime", "build", "dependency")

        Returns:
            JSON string representation of the graph

        Raises:
            ValueError: If graph_type is invalid
            RuntimeError: If JSON serialization fails
        """
        if not isinstance(graph_type, str) or not graph_type:
            raise ValueError("graph_type must be a non-empty string")

        try:
            graph_data = {
                "graph_type": graph_type,
                "nodes": [node.to_dict() for node in self.nodes.values()],
                "edges": [edge.to_dict() for edge in self.edges],
            }

            return json.dumps(graph_data, indent=2, ensure_ascii=False)

        except (TypeError, ValueError) as e:
            from logging import getLogger

            logger = getLogger(__name__)
            logger.error(f"Failed to serialize graph to JSON: {e}", exc_info=True)
            raise RuntimeError(f"JSON serialization failed: {e}") from e

    def to_dict(self, graph_type: str = "dependency") -> Dict:
        """
        Convert the graph to a dictionary.

        Args:
            graph_type: Type of graph (e.g., "runtime", "build", "dependency")

        Returns:
            Dictionary representation of the graph
        """
        return {
            "graph_type": graph_type,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }
