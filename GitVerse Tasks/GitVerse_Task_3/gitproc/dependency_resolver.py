"""
Dependency resolver for service startup order management.
"""

from typing import Dict, List, Set
from collections import defaultdict, deque


class DependencyResolver:
    """
    Resolves service dependencies and determines startup order.
    
    Uses topological sorting (Kahn's algorithm) to determine the correct
    order to start services based on their After directives. Also detects
    circular dependencies using DFS.
    """
    
    def __init__(self):
        """Initialize the dependency resolver with an empty graph."""
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.all_services: Set[str] = set()
    
    def add_dependency(self, service: str, depends_on: str):
        """
        Add a dependency relationship to the graph.
        
        Args:
            service: The service that depends on another service
            depends_on: The service that must start before 'service'
        
        Example:
            If service A has "After=B", call add_dependency("A", "B")
            This means B must start before A.
        """
        self.graph[depends_on].append(service)
        self.all_services.add(service)
        self.all_services.add(depends_on)
    
    def get_start_order(self, services: List[str]) -> List[str]:
        """
        Get the correct startup order for services using topological sort.
        
        Uses Kahn's algorithm for topological sorting:
        1. Calculate in-degree (number of dependencies) for each service
        2. Start with services that have no dependencies (in-degree = 0)
        3. Process services in order, removing edges as we go
        4. Return the sorted order
        
        Args:
            services: List of service names to order
        
        Returns:
            List of service names in the order they should be started
        
        Raises:
            ValueError: If circular dependencies are detected
        """
        # Build subgraph for only the requested services
        service_set = set(services)
        subgraph: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {service: 0 for service in services}
        
        # Build the subgraph and calculate in-degrees
        for node in service_set:
            if node in self.graph:
                for neighbor in self.graph[node]:
                    if neighbor in service_set:
                        subgraph[node].append(neighbor)
                        in_degree[neighbor] += 1
        
        # Find all services with no dependencies (in-degree = 0)
        queue = deque([service for service in services if in_degree[service] == 0])
        result = []
        
        # Process services in topological order
        while queue:
            current = queue.popleft()
            result.append(current)
            
            # Remove edges from current service
            if current in subgraph:
                for neighbor in subgraph[current]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        
        # If we couldn't process all services, there's a cycle
        if len(result) != len(services):
            cycles = self.detect_cycles()
            cycle_str = ", ".join([" -> ".join(cycle) for cycle in cycles])
            raise ValueError(f"Circular dependencies detected: {cycle_str}")
        
        return result
    
    def detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies in the graph using DFS.
        
        Returns:
            List of cycles, where each cycle is a list of service names
            forming a circular dependency. Returns empty list if no cycles.
        
        Example:
            If A depends on B, B depends on C, and C depends on A,
            returns [["A", "B", "C", "A"]]
        """
        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []
        
        def dfs(node: str) -> bool:
            """
            Depth-first search to detect cycles.
            
            Args:
                node: Current node being visited
            
            Returns:
                True if a cycle is detected, False otherwise
            """
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            if node in self.graph:
                for neighbor in self.graph[node]:
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        # Found a cycle - extract it from the path
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        cycles.append(cycle)
                        return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        # Check all nodes for cycles
        for service in self.all_services:
            if service not in visited:
                dfs(service)
        
        return cycles
    
    def clear(self):
        """Clear all dependency information."""
        self.graph.clear()
        self.all_services.clear()
