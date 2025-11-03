"""
Integration test for complete workflow with a real RPM repository.

This test validates the entire system end-to-end:
1. Downloads actual repository metadata
2. Builds both dependency graphs
3. Verifies graph completeness and accuracy
4. Tests web interface with real data
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

import pytest


# Use a small, stable public RPM repository for testing
# OpenScaler repository (smaller and tested to work)
TEST_REPO_URL = "https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/"

# Alternative test repositories (in case primary is unavailable)
FALLBACK_REPOS = [
    "https://repo.almalinux.org/almalinux/9/BaseOS/x86_64/os/",
    "https://dl.rockylinux.org/pub/rocky/9/BaseOS/x86_64/os/",
    "https://mirror.stream.centos.org/9-stream/BaseOS/x86_64/os/",
]


class TestRealRepositoryWorkflow:
    """Test complete workflow with a real RPM repository."""

    @pytest.fixture(scope="class")
    def test_output_dir(self, tmp_path_factory):
        """Create a temporary directory for test outputs."""
        output_dir = tmp_path_factory.mktemp("real_repo_test")
        return output_dir

    @pytest.fixture(scope="class")
    def test_cache_dir(self, tmp_path_factory):
        """Create a temporary directory for cache."""
        cache_dir = tmp_path_factory.mktemp("real_repo_cache")
        return cache_dir

    def test_01_download_real_repository(self, test_cache_dir, test_output_dir):
        """Test downloading actual repository metadata."""
        print(f"\n{'='*70}")
        print("TEST 1: Downloading Real Repository Metadata")
        print(f"{'='*70}")

        # Try primary repository first, then fallbacks
        repos_to_try = [TEST_REPO_URL] + FALLBACK_REPOS
        success = False
        last_error = None

        for repo_url in repos_to_try:
            print(f"\nAttempting to download from: {repo_url}")
            
            try:
                # Run main.py to download and process repository
                cmd = [
                    sys.executable,
                    "-m",
                    "src.main",
                    "--repo-url",
                    repo_url,
                    "--cache-dir",
                    str(test_cache_dir),
                    "--output-dir",
                    str(test_output_dir),
                    "--verbose",
                ]

                print(f"Running command: {' '.join(cmd)}")
                start_time = time.time()

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout
                )

                elapsed_time = time.time() - start_time
                print(f"\nExecution time: {elapsed_time:.2f} seconds")

                if result.returncode == 0:
                    print(f"✓ Successfully downloaded and processed repository")
                    print(f"\nOutput:\n{result.stdout}")
                    success = True
                    break
                else:
                    last_error = result.stderr
                    print(f"✗ Failed with return code {result.returncode}")
                    print(f"Error: {result.stderr}")
                    continue

            except subprocess.TimeoutExpired:
                last_error = "Process timed out after 10 minutes"
                print(f"✗ {last_error}")
                continue
            except Exception as e:
                last_error = str(e)
                print(f"✗ Exception: {e}")
                continue

        if not success:
            pytest.fail(
                f"Failed to download from all repositories. Last error: {last_error}"
            )

        # Verify cache directory has content
        cache_files = list(Path(test_cache_dir).glob("*"))
        assert len(cache_files) > 0, "Cache directory is empty"
        print(f"\n✓ Cache directory contains {len(cache_files)} files")

    def test_02_verify_graph_files_created(self, test_output_dir):
        """Verify that both graph files were created."""
        print(f"\n{'='*70}")
        print("TEST 2: Verifying Graph Files")
        print(f"{'='*70}")

        runtime_graph_path = Path(test_output_dir) / "runtime_graph.json"
        build_graph_path = Path(test_output_dir) / "build_graph.json"

        # Check runtime graph
        assert runtime_graph_path.exists(), "Runtime graph file not found"
        print(f"✓ Runtime graph file exists: {runtime_graph_path}")

        # Check build graph
        assert build_graph_path.exists(), "Build graph file not found"
        print(f"✓ Build graph file exists: {build_graph_path}")

        # Check file sizes
        runtime_size = runtime_graph_path.stat().st_size
        build_size = build_graph_path.stat().st_size

        assert runtime_size > 0, "Runtime graph file is empty"
        assert build_size > 0, "Build graph file is empty"

        print(f"✓ Runtime graph size: {runtime_size:,} bytes")
        print(f"✓ Build graph size: {build_size:,} bytes")

    def test_03_verify_runtime_graph_structure(self, test_output_dir):
        """Verify runtime graph has correct structure and content."""
        print(f"\n{'='*70}")
        print("TEST 3: Verifying Runtime Graph Structure")
        print(f"{'='*70}")

        runtime_graph_path = Path(test_output_dir) / "runtime_graph.json"

        with open(runtime_graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        # Verify graph type
        assert graph_data.get("graph_type") == "runtime", "Invalid graph type"
        print(f"✓ Graph type: {graph_data['graph_type']}")

        # Verify nodes exist
        assert "nodes" in graph_data, "Missing 'nodes' field"
        nodes = graph_data["nodes"]
        assert isinstance(nodes, list), "Nodes should be a list"
        assert len(nodes) > 0, "Graph has no nodes"
        print(f"✓ Runtime graph has {len(nodes)} nodes")

        # Verify edges exist
        assert "edges" in graph_data, "Missing 'edges' field"
        edges = graph_data["edges"]
        assert isinstance(edges, list), "Edges should be a list"
        print(f"✓ Runtime graph has {len(edges)} edges")

        # Verify node structure
        sample_node = nodes[0]
        assert "id" in sample_node, "Node missing 'id' field"
        assert "label" in sample_node, "Node missing 'label' field"
        print(f"✓ Sample node: {sample_node['id']}")

        # Verify edge structure (if edges exist)
        if len(edges) > 0:
            sample_edge = edges[0]
            assert "source" in sample_edge, "Edge missing 'source' field"
            assert "target" in sample_edge, "Edge missing 'target' field"
            print(f"✓ Sample edge: {sample_edge['source']} -> {sample_edge['target']}")

        # Verify all edge references point to valid nodes
        node_ids = {node["id"] for node in nodes}
        for edge in edges:
            assert edge["source"] in node_ids, f"Edge source '{edge['source']}' not in nodes"
            assert edge["target"] in node_ids, f"Edge target '{edge['target']}' not in nodes"
        print(f"✓ All edge references are valid")

    def test_04_verify_build_graph_structure(self, test_output_dir):
        """Verify build graph has correct structure and content."""
        print(f"\n{'='*70}")
        print("TEST 4: Verifying Build Graph Structure")
        print(f"{'='*70}")

        build_graph_path = Path(test_output_dir) / "build_graph.json"

        with open(build_graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        # Verify graph type
        assert graph_data.get("graph_type") == "build", "Invalid graph type"
        print(f"✓ Graph type: {graph_data['graph_type']}")

        # Verify nodes exist
        assert "nodes" in graph_data, "Missing 'nodes' field"
        nodes = graph_data["nodes"]
        assert isinstance(nodes, list), "Nodes should be a list"
        
        # Build graph may be empty for binary repositories (this is expected)
        if len(nodes) == 0:
            print(f"⚠ Build graph is empty (expected for binary repository)")
            print(f"✓ Build graph structure is valid (empty)")
            return
        
        print(f"✓ Build graph has {len(nodes)} nodes")

        # Verify edges exist
        assert "edges" in graph_data, "Missing 'edges' field"
        edges = graph_data["edges"]
        assert isinstance(edges, list), "Edges should be a list"
        print(f"✓ Build graph has {len(edges)} edges")

        # Verify node structure
        sample_node = nodes[0]
        assert "id" in sample_node, "Node missing 'id' field"
        assert "label" in sample_node, "Node missing 'label' field"
        print(f"✓ Sample node: {sample_node['id']}")

        # Verify all edge references point to valid nodes
        node_ids = {node["id"] for node in nodes}
        for edge in edges:
            assert edge["source"] in node_ids, f"Edge source '{edge['source']}' not in nodes"
            assert edge["target"] in node_ids, f"Edge target '{edge['target']}' not in nodes"
        print(f"✓ All edge references are valid")

    def test_05_verify_graph_completeness(self, test_output_dir):
        """Verify graphs contain reasonable amount of data."""
        print(f"\n{'='*70}")
        print("TEST 5: Verifying Graph Completeness")
        print(f"{'='*70}")

        runtime_graph_path = Path(test_output_dir) / "runtime_graph.json"
        build_graph_path = Path(test_output_dir) / "build_graph.json"

        with open(runtime_graph_path, "r", encoding="utf-8") as f:
            runtime_data = json.load(f)

        with open(build_graph_path, "r", encoding="utf-8") as f:
            build_data = json.load(f)

        runtime_nodes = len(runtime_data["nodes"])
        runtime_edges = len(runtime_data["edges"])
        build_nodes = len(build_data["nodes"])
        build_edges = len(build_data["edges"])

        # Real repositories should have at least some packages
        # Runtime graph should have data for binary repositories
        assert runtime_nodes >= 10, f"Runtime graph has too few nodes: {runtime_nodes}"
        
        # Build graph may be empty for binary repositories (this is expected)
        if build_nodes == 0:
            print(f"⚠ Build graph is empty (expected for binary repository)")
        else:
            print(f"✓ Build graph: {build_nodes} nodes, {build_edges} edges")

        print(f"✓ Runtime graph: {runtime_nodes} nodes, {runtime_edges} edges")

        # Calculate graph density (edges / possible_edges)
        if runtime_nodes > 1:
            max_edges = runtime_nodes * (runtime_nodes - 1)
            density = runtime_edges / max_edges if max_edges > 0 else 0
            print(f"✓ Runtime graph density: {density:.4f}")

        if build_nodes > 1:
            max_edges = build_nodes * (build_nodes - 1)
            density = build_edges / max_edges if max_edges > 0 else 0
            print(f"✓ Build graph density: {density:.4f}")

    def test_06_test_web_server_startup(self, test_output_dir):
        """Test that web server can start and serve the graphs."""
        print(f"\n{'='*70}")
        print("TEST 6: Testing Web Server")
        print(f"{'='*70}")

        # Copy graph files to default data directory for server
        import shutil

        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        runtime_src = Path(test_output_dir) / "runtime_graph.json"
        build_src = Path(test_output_dir) / "build_graph.json"
        runtime_dst = data_dir / "runtime_graph.json"
        build_dst = data_dir / "build_graph.json"

        shutil.copy2(runtime_src, runtime_dst)
        shutil.copy2(build_src, build_dst)
        print(f"✓ Copied graph files to {data_dir}")

        # Start server in background
        server_process = subprocess.Popen(
            [sys.executable, "-m", "src.server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for server to start
            print("Waiting for server to start...")
            time.sleep(3)

            # Check if server is running
            if server_process.poll() is not None:
                stdout, stderr = server_process.communicate()
                pytest.fail(f"Server failed to start. Error: {stderr}")

            print("✓ Server started successfully")

            # Test API endpoints using requests
            try:
                import requests

                base_url = "http://localhost:5000"

                # Test main page
                response = requests.get(base_url, timeout=5)
                assert response.status_code == 200, f"Main page returned {response.status_code}"
                print(f"✓ Main page accessible (status: {response.status_code})")

                # Test graphs list endpoint
                response = requests.get(f"{base_url}/api/graphs", timeout=5)
                assert response.status_code == 200, f"Graphs API returned {response.status_code}"
                graphs_data = response.json()
                assert "graphs" in graphs_data, "Missing 'graphs' field in response"
                print(f"✓ Graphs API accessible: {len(graphs_data['graphs'])} graphs available")

                # Test runtime graph endpoint
                response = requests.get(f"{base_url}/api/graph/runtime", timeout=5)
                assert (
                    response.status_code == 200
                ), f"Runtime graph API returned {response.status_code}"
                runtime_data = response.json()
                assert "nodes" in runtime_data, "Missing 'nodes' in runtime graph"
                print(f"✓ Runtime graph API accessible: {len(runtime_data['nodes'])} nodes")

                # Test build graph endpoint
                response = requests.get(f"{base_url}/api/graph/build", timeout=5)
                assert (
                    response.status_code == 200
                ), f"Build graph API returned {response.status_code}"
                build_data = response.json()
                assert "nodes" in build_data, "Missing 'nodes' in build graph"
                print(f"✓ Build graph API accessible: {len(build_data['nodes'])} nodes")

            except ImportError:
                print("⚠ requests library not available, skipping HTTP tests")
            except Exception as e:
                pytest.fail(f"HTTP request failed: {e}")

        finally:
            # Stop server
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            print("✓ Server stopped")

    def test_07_verify_processing_time(self, test_cache_dir, test_output_dir):
        """Verify that processing completes within 10 minutes (requirement 1.5)."""
        print(f"\n{'='*70}")
        print("TEST 7: Verifying Processing Time")
        print(f"{'='*70}")

        # Clear cache to test full processing time
        import shutil

        if Path(test_cache_dir).exists():
            shutil.rmtree(test_cache_dir)
        Path(test_cache_dir).mkdir(parents=True, exist_ok=True)

        # Run with timing
        cmd = [
            sys.executable,
            "-m",
            "src.main",
            "--repo-url",
            TEST_REPO_URL,
            "--cache-dir",
            str(test_cache_dir),
            "--output-dir",
            str(test_output_dir),
        ]

        print(f"Running full workflow with timing...")
        start_time = time.time()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)

        print(f"✓ Processing completed in {minutes}m {seconds}s")

        # Verify it completed within 10 minutes (requirement 1.5)
        assert elapsed_time < 600, f"Processing took too long: {elapsed_time:.2f}s (>10 minutes)"
        print(f"✓ Processing time within requirement (<10 minutes)")

        assert result.returncode == 0, f"Processing failed: {result.stderr}"
        print(f"✓ Processing completed successfully")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
