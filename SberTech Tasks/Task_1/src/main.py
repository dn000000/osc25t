"""
Main orchestration module for RPM Dependency Graph system.

This module coordinates the entire workflow:
1. Download repository metadata
2. Parse package information
3. Extract dependencies
4. Build dependency graphs
5. Save graphs to JSON files
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Tuple

from src.repository import RepositoryDownloader, PackageInfo, RepositoryDownloadError
from src.parser import PackageMetadata, Dependency
from src.extractor import DependencyExtractor
from src.graph import DependencyGraph
from src.validation import validate_url, ValidationError
from src.file_utils import safe_write


# Configure logging
def setup_logging(verbose: bool = False, log_file: str = "rpm_dependency_graph.log") -> None:
    """
    Set up logging configuration with file rotation and proper formatting.

    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO
        log_file: Path to log file
    """
    from logging.handlers import RotatingFileHandler

    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Create formatters
    detailed_formatter = logging.Formatter(log_format, datefmt=date_format)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Console handler - less verbose for user-facing output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # File handler with rotation (max 10MB, keep 5 backup files)
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
        )
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
        file_handler.setFormatter(detailed_formatter)
        handlers = [console_handler, file_handler]
    except (OSError, IOError) as e:
        # If we can't create log file, just use console
        logger.warning(f"Could not create log file {log_file}: {e}. Logging to console only.")
        handlers = [console_handler]

    # Configure root logger
    from typing import cast

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=cast(list, handlers),
        force=True,  # Override any existing configuration
    )

    # Set third-party library log levels to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class PackageProcessingError(Exception):
    """Base exception for package processing errors"""

    pass


def download_repository(
    repo_url: str, cache_dir: str = "data/cache", extract_deps: bool = False, max_packages: int = None
) -> Tuple[Path, List[PackageInfo]]:
    """
    Download repository metadata and extract package list.

    Args:
        repo_url: URL of the RPM repository
        cache_dir: Directory for caching downloaded data
        extract_deps: If True, download RPM files and extract dependencies
        max_packages: Maximum number of packages to process (None for all)

    Returns:
        Tuple of (cache_path, package_list)

    Raises:
        RepositoryDownloadError: If download fails
    """
    logger.info(f"Downloading repository from {repo_url}")

    downloader = RepositoryDownloader(cache_dir=cache_dir)

    try:
        # Download and cache repository metadata
        cache_path = downloader.download_repository_metadata(repo_url)

        # Extract package list
        package_list = downloader.get_package_list(cache_path)

        logger.info(f"Successfully downloaded metadata for {len(package_list)} packages")
        
        # If extract_deps is enabled, download RPMs and extract dependencies
        if extract_deps:
            logger.info("=" * 70)
            logger.info("EXTRACTING DEPENDENCIES FROM RPM FILES")
            logger.info("=" * 70)
            
            # Get list of RPM filenames from package_list
            rpm_files = [pkg.location for pkg in package_list]
            
            # Download and parse RPMs
            cache_path = downloader.download_and_parse_rpms(
                repo_url, rpm_files, max_retries=3, max_packages=max_packages
            )
            
            # Re-extract package list with dependencies
            package_list = downloader.get_package_list(cache_path)
            logger.info(f"Extracted dependencies for {len(package_list)} packages")
        
        return cache_path, package_list

    except RepositoryDownloadError as e:
        logger.error(f"Failed to download repository: {e}")
        raise


def parse_packages(
    package_list: List[PackageInfo],
) -> List[Tuple[PackageMetadata, List[Dependency]]]:
    """
    Parse package metadata and extract dependencies.

    Note: This function works with repository metadata, not actual RPM files.
    For a full implementation, you would download and parse actual RPM files.
    This implementation creates metadata from repository information.

    Args:
        package_list: List of PackageInfo objects from repository

    Returns:
        List of tuples (PackageMetadata, List[Dependency])

    Raises:
        PackageProcessingError: If no packages could be processed successfully
    """
    total_packages = len(package_list)
    logger.info(f"Processing {total_packages} packages")

    packages_with_deps = []
    errors = []

    # Progress tracking
    progress_interval = max(1, total_packages // 10)  # Report every 10%

    for idx, pkg_info in enumerate(package_list, 1):
        try:
            # Create PackageMetadata from PackageInfo
            metadata = PackageMetadata(
                name=pkg_info.name,
                version=pkg_info.version,
                release=pkg_info.release,
                arch=pkg_info.arch,
                is_source=pkg_info.is_source,
            )

            # Extract dependencies from PackageInfo
            dependencies: List[Dependency] = []
            
            # Add requires as dependencies
            for req in pkg_info.requires:
                dep_type = "buildrequires" if pkg_info.is_source else "requires"
                dependencies.append(Dependency(name=req, type=dep_type))
            
            # Add provides
            for prov in pkg_info.provides:
                dependencies.append(Dependency(name=prov, type="provides"))

            packages_with_deps.append((metadata, dependencies))

            # Progress indicator
            if idx % progress_interval == 0 or idx == total_packages:
                progress_pct = (idx / total_packages) * 100
                logger.info(f"Progress: {idx}/{total_packages} packages ({progress_pct:.1f}%)")

        except Exception as e:
            error_msg = f"Failed to process package {pkg_info.name}: {e}"
            errors.append(error_msg)
            logger.warning(error_msg)
            logger.debug("Package processing error details:", exc_info=True)
            continue

    # Report final statistics
    success_count = len(packages_with_deps)
    error_count = len(errors)

    if error_count > 0:
        logger.warning(f"Package processing completed with {error_count} errors")
        logger.debug(f"First 5 errors: {errors[:5]}")

    if success_count == 0:
        raise PackageProcessingError(f"Failed to process any packages. Total errors: {error_count}")

    logger.info(
        f"Successfully processed {success_count}/{total_packages} packages "
        f"({(success_count/total_packages)*100:.1f}% success rate)"
    )

    return packages_with_deps


def build_dependency_graphs(
    packages_with_deps: List[Tuple[PackageMetadata, List[Dependency]]]
) -> Tuple[DependencyGraph, DependencyGraph]:
    """
    Build both runtime and build dependency graphs.

    Args:
        packages_with_deps: List of tuples (PackageMetadata, List[Dependency])

    Returns:
        Tuple of (runtime_graph, build_graph)

    Raises:
        PackageProcessingError: If graph construction fails
    """
    logger.info("Building dependency graphs")

    try:
        # Extract dependencies
        extractor = DependencyExtractor()

        logger.info("Extracting runtime dependencies...")
        runtime_deps = extractor.extract_runtime_deps(packages_with_deps)
        logger.info(f"Extracted runtime dependencies for {len(runtime_deps)} packages")

        logger.info("Extracting build dependencies...")
        build_deps = extractor.extract_build_deps(packages_with_deps)
        logger.info(f"Extracted build dependencies for {len(build_deps)} packages")

        # Build runtime graph
        logger.info("Constructing runtime dependency graph...")
        runtime_graph = DependencyGraph()
        runtime_graph.build_graph(runtime_deps)

        logger.info(
            f"Runtime graph: {runtime_graph.node_count()} nodes, {runtime_graph.edge_count()} edges"
        )

        # Detect cycles in runtime graph
        logger.info("Detecting cycles in runtime graph...")
        runtime_cycles = runtime_graph.detect_cycles()
        if runtime_cycles:
            logger.warning(f"Detected {len(runtime_cycles)} circular dependencies in runtime graph")
            for i, cycle in enumerate(runtime_cycles[:5]):  # Show first 5 cycles
                logger.warning(f"  Cycle {i+1}: {' -> '.join(cycle)}")
            if len(runtime_cycles) > 5:
                logger.warning(f"  ... and {len(runtime_cycles) - 5} more cycles")
        else:
            logger.info("No circular dependencies detected in runtime graph")

        # Build build dependency graph
        logger.info("Constructing build dependency graph...")
        build_graph = DependencyGraph()
        build_graph.build_graph(build_deps)

        logger.info(
            f"Build graph: {build_graph.node_count()} nodes, {build_graph.edge_count()} edges"
        )

        # Detect cycles in build graph
        logger.info("Detecting cycles in build graph...")
        build_cycles = build_graph.detect_cycles()
        if build_cycles:
            logger.warning(f"Detected {len(build_cycles)} circular dependencies in build graph")
            for i, cycle in enumerate(build_cycles[:5]):  # Show first 5 cycles
                logger.warning(f"  Cycle {i+1}: {' -> '.join(cycle)}")
            if len(build_cycles) > 5:
                logger.warning(f"  ... and {len(build_cycles) - 5} more cycles")
        else:
            logger.info("No circular dependencies detected in build graph")

        return runtime_graph, build_graph

    except Exception as e:
        logger.error(f"Failed to build dependency graphs: {e}", exc_info=True)
        raise PackageProcessingError(f"Graph construction failed: {e}") from e


def save_graphs(
    runtime_graph: DependencyGraph, build_graph: DependencyGraph, output_dir: str = "data"
) -> None:
    """
    Save dependency graphs to JSON files with error handling.

    Args:
        runtime_graph: Runtime dependency graph
        build_graph: Build dependency graph
        output_dir: Directory to save graph files

    Raises:
        PackageProcessingError: If saving fails
    """
    logger.info(f"Saving graphs to {output_dir}")

    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save runtime graph using atomic write
        logger.info("Saving runtime graph...")
        runtime_file = output_path / "runtime_graph.json"
        try:
            with safe_write(runtime_file, mode="w", encoding="utf-8", atomic=True) as f:
                f.write(runtime_graph.export_to_json(graph_type="runtime"))
            logger.info(f"✓ Saved runtime graph to {runtime_file}")
        except (OSError, IOError) as e:
            raise PackageProcessingError(f"Failed to save runtime graph: {e}") from e

        # Save build graph using atomic write
        logger.info("Saving build graph...")
        build_file = output_path / "build_graph.json"
        try:
            with safe_write(build_file, mode="w", encoding="utf-8", atomic=True) as f:
                f.write(build_graph.export_to_json(graph_type="build"))
            logger.info(f"✓ Saved build graph to {build_file}")
        except (OSError, IOError) as e:
            raise PackageProcessingError(f"Failed to save build graph: {e}") from e

        # Save summary statistics
        logger.info("Generating summary statistics...")
        summary = {
            "runtime_graph": {
                "nodes": runtime_graph.node_count(),
                "edges": runtime_graph.edge_count(),
                "cycles": len(runtime_graph.detect_cycles()),
            },
            "build_graph": {
                "nodes": build_graph.node_count(),
                "edges": build_graph.edge_count(),
                "cycles": len(build_graph.detect_cycles()),
            },
        }

        summary_file = output_path / "graph_summary.json"
        try:
            with safe_write(summary_file, mode="w", encoding="utf-8", atomic=True) as f:
                json.dump(summary, f, indent=2)
            logger.info(f"✓ Saved graph summary to {summary_file}")
        except (OSError, IOError) as e:
            logger.warning(f"Failed to save summary file: {e}")
            # Don't fail the entire operation if summary can't be saved

        logger.info("All graphs saved successfully")

    except PackageProcessingError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error while saving graphs: {e}", exc_info=True)
        raise PackageProcessingError(f"Failed to save graphs: {e}") from e


def clear_cache(cache_dir: str = "data/cache") -> None:
    """
    Clear cached repository data with error handling.

    Args:
        cache_dir: Directory containing cached data
    """
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        logger.info("Cache directory does not exist, nothing to clear")
        return

    logger.info(f"Clearing cache directory: {cache_dir}")

    # Remove all cached files
    removed_count = 0
    error_count = 0

    try:
        for file_path in cache_path.glob("*"):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    removed_count += 1
                except (OSError, IOError) as e:
                    error_count += 1
                    logger.warning(f"Failed to remove {file_path}: {e}")

        if error_count > 0:
            logger.warning(f"Cleared {removed_count} files with {error_count} errors")
        else:
            logger.info(f"✓ Cleared {removed_count} cached files from {cache_dir}")

    except Exception as e:
        logger.error(f"Error while clearing cache: {e}", exc_info=True)


def main() -> int:
    """
    Main entry point for the RPM Dependency Graph system.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="RPM Dependency Graph - Analyze and visualize RPM package dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze OpenScaler repository
  python -m src.main --repo-url https://example.com/openscaler/repo

  # Clear cache and re-download
  python -m src.main --repo-url https://example.com/openscaler/repo --clear-cache

  # Enable verbose logging
  python -m src.main --repo-url https://example.com/openscaler/repo --verbose
        """,
    )

    parser.add_argument(
        "--repo-url", type=str, required=True, help="URL of the RPM repository to analyze"
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default="data/cache",
        help="Directory for caching repository metadata (default: data/cache)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Directory for output graph files (default: data)",
    )

    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear cached repository data before downloading"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG level)"
    )

    parser.add_argument(
        "--extract-deps",
        action="store_true",
        help="Download RPM files and extract dependencies (slow but accurate)",
    )

    parser.add_argument(
        "--max-packages",
        type=int,
        default=None,
        help="Maximum number of packages to process (for testing)",
    )

    args = parser.parse_args()

    # Set up logging
    try:
        setup_logging(verbose=args.verbose)
    except Exception as e:
        print(f"ERROR: Failed to set up logging: {e}", file=sys.stderr)
        return 1

    # Validate repository URL
    try:
        args.repo_url = validate_url(args.repo_url, allowed_schemes=["http", "https"])
    except ValidationError as e:
        logger.error(f"Invalid repository URL: {e}")
        return 1

    logger.info("=" * 70)
    logger.info("RPM Dependency Graph System")
    logger.info("=" * 70)
    logger.info(f"Repository URL: {args.repo_url}")
    logger.info(f"Cache directory: {args.cache_dir}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Verbose mode: {args.verbose}")
    logger.info("=" * 70)

    start_time = time.time()

    try:
        # Clear cache if requested
        if args.clear_cache:
            logger.info("\n[1/5] Clearing cache...")
            clear_cache(args.cache_dir)
        else:
            logger.info("\n[1/5] Using existing cache (if available)")

        # Step 1: Download repository metadata
        logger.info("\n[2/5] Downloading repository metadata...")
        try:
            cache_path, package_list = download_repository(
                args.repo_url, args.cache_dir, args.extract_deps, args.max_packages
            )
        except RepositoryDownloadError as e:
            logger.error(f"Failed to download repository: {e}")
            logger.info("Tip: Check your internet connection and repository URL")
            return 1

        if not package_list:
            logger.error("No packages found in repository")
            return 1

        # Step 2: Parse packages
        logger.info(f"\n[3/5] Parsing package information ({len(package_list)} packages)...")
        try:
            packages_with_deps = parse_packages(package_list)
        except PackageProcessingError as e:
            logger.error(f"Failed to parse packages: {e}")
            return 1

        if not packages_with_deps:
            logger.error("No packages were successfully parsed")
            return 1

        # Step 3: Build dependency graphs
        logger.info("\n[4/5] Building dependency graphs...")
        try:
            runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)
        except PackageProcessingError as e:
            logger.error(f"Failed to build graphs: {e}")
            return 1

        # Step 4: Save graphs to JSON files
        logger.info("\n[5/5] Saving graphs to files...")
        try:
            save_graphs(runtime_graph, build_graph, args.output_dir)
        except PackageProcessingError as e:
            logger.error(f"Failed to save graphs: {e}")
            return 1

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(int(elapsed_time), 60)

        # Success summary
        logger.info("\n" + "=" * 70)
        logger.info("✓ Processing complete!")
        logger.info("=" * 70)
        logger.info(
            f"Runtime graph: {runtime_graph.node_count()} nodes, {runtime_graph.edge_count()} edges"
        )
        logger.info(
            f"Build graph: {build_graph.node_count()} nodes, {build_graph.edge_count()} edges"
        )
        logger.info(f"Output directory: {args.output_dir}")
        logger.info(f"Processing time: {minutes}m {seconds}s")
        logger.info("=" * 70)

        return 0

    except KeyboardInterrupt:
        logger.warning("\n\nOperation cancelled by user")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"\n\nUnexpected error: {e}", exc_info=True)
        logger.error("Please check the log file for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
