"""
Tests for the DependencyResolver class.
"""

import pytest
from gitproc.dependency_resolver import DependencyResolver


class TestDependencyResolver:
    """Test cases for DependencyResolver."""
    
    def test_simple_dependency_chain(self):
        """Test simple dependency chain: A -> B -> C"""
        resolver = DependencyResolver()
        resolver.add_dependency("C", "B")  # C depends on B
        resolver.add_dependency("B", "A")  # B depends on A
        
        order = resolver.get_start_order(["A", "B", "C"])
        assert order == ["A", "B", "C"]
    
    def test_multiple_dependencies(self):
        """Test service with multiple dependencies: A -> B, A -> C"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")  # B depends on A
        resolver.add_dependency("C", "A")  # C depends on A
        
        order = resolver.get_start_order(["A", "B", "C"])
        # A must be first, B and C can be in any order
        assert order[0] == "A"
        assert set(order[1:]) == {"B", "C"}
    
    def test_no_dependencies(self):
        """Test services with no dependencies"""
        resolver = DependencyResolver()
        
        order = resolver.get_start_order(["A", "B", "C"])
        # All services can start in any order
        assert set(order) == {"A", "B", "C"}
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection: A -> B -> A"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")  # B depends on A
        resolver.add_dependency("A", "B")  # A depends on B (creates cycle)
        
        with pytest.raises(ValueError, match="Circular dependencies detected"):
            resolver.get_start_order(["A", "B"])
    
    def test_detect_cycles_simple(self):
        """Test detect_cycles with simple circular dependency"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")
        resolver.add_dependency("A", "B")
        
        cycles = resolver.detect_cycles()
        assert len(cycles) > 0
        # Cycle should contain A and B
        cycle = cycles[0]
        assert "A" in cycle and "B" in cycle
    
    def test_detect_cycles_complex(self):
        """Test detect_cycles with three-service cycle: A -> B -> C -> A"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")
        resolver.add_dependency("C", "B")
        resolver.add_dependency("A", "C")
        
        cycles = resolver.detect_cycles()
        assert len(cycles) > 0
        cycle = cycles[0]
        assert "A" in cycle and "B" in cycle and "C" in cycle
    
    def test_no_cycles(self):
        """Test detect_cycles returns empty list when no cycles exist"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")
        resolver.add_dependency("C", "B")
        
        cycles = resolver.detect_cycles()
        assert cycles == []
    
    def test_complex_dependency_graph(self):
        """Test complex dependency graph with multiple paths"""
        resolver = DependencyResolver()
        # D depends on B and C
        # B depends on A
        # C depends on A
        resolver.add_dependency("B", "A")
        resolver.add_dependency("C", "A")
        resolver.add_dependency("D", "B")
        resolver.add_dependency("D", "C")
        
        order = resolver.get_start_order(["A", "B", "C", "D"])
        # A must be first
        assert order[0] == "A"
        # D must be last
        assert order[-1] == "D"
        # B and C must be before D and after A
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")
    
    def test_partial_service_list(self):
        """Test ordering with only a subset of services"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")
        resolver.add_dependency("C", "B")
        resolver.add_dependency("D", "C")
        
        # Only start A and B
        order = resolver.get_start_order(["A", "B"])
        assert order == ["A", "B"]
    
    def test_clear(self):
        """Test clearing the dependency graph"""
        resolver = DependencyResolver()
        resolver.add_dependency("B", "A")
        resolver.add_dependency("C", "B")
        
        resolver.clear()
        
        # After clearing, services should have no dependencies
        order = resolver.get_start_order(["A", "B", "C"])
        assert set(order) == {"A", "B", "C"}
