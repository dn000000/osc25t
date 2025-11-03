"""
Dependency extractor module for processing package dependencies.
"""

import logging
from typing import Dict, List, Set

from src.validation import validate_package_name, ValidationError

logger = logging.getLogger(__name__)


class DependencyExtractor:
    """Extracts and processes package dependencies"""

    # System libraries and dependencies to filter out
    SYSTEM_FILTERS = {
        "rpmlib(",
        "config(",
        "/bin/sh",
        "/usr/bin/sh",
        "rtld(",
    }

    def __init__(self) -> None:
        """Initialize the dependency extractor"""
        self.virtual_provides_map: Dict[str, Set[str]] = {}

    def extract_runtime_deps(self, packages_with_deps: List[tuple]) -> Dict[str, List[str]]:
        """
        Extract runtime dependencies from binary RPM packages.

        Args:
            packages_with_deps: List of tuples (PackageMetadata, List[Dependency])

        Returns:
            Dictionary mapping package names to their runtime dependencies
        """
        logger.info("Extracting runtime dependencies")

        try:
            runtime_deps = {}

            # First pass: build provides map
            logger.debug("Building provides map for dependency resolution")
            self._build_provides_map(packages_with_deps)

            # Count binary packages
            binary_packages = [p for p, _ in packages_with_deps if not p.is_source]
            total_binary = len(binary_packages)
            logger.info(f"Processing {total_binary} binary packages")

            # Second pass: extract runtime dependencies
            processed = 0
            for metadata, dependencies in packages_with_deps:
                # Skip source packages for runtime dependencies
                if metadata.is_source:
                    continue

                try:
                    # Validate package name
                    try:
                        pkg_name = validate_package_name(metadata.name)
                    except ValidationError as e:
                        logger.warning(f"Invalid package name {metadata.name}: {e}")
                        continue

                    requires = []

                    for dep in dependencies:
                        if dep.type == "requires":
                            # Resolve and filter dependency
                            resolved_deps = self._resolve_dependency(dep.name)
                            requires.extend(resolved_deps)

                    # Remove duplicates and self-references
                    requires = list(set(requires))
                    if pkg_name in requires:
                        requires.remove(pkg_name)

                    runtime_deps[pkg_name] = requires
                    processed += 1

                except Exception as e:
                    logger.warning(f"Error extracting runtime deps for {metadata.name}: {e}")
                    logger.debug("Runtime dependency extraction error:", exc_info=True)
                    # Continue with empty dependencies
                    runtime_deps[metadata.name] = []

            logger.info(f"Extracted runtime dependencies for {len(runtime_deps)} packages")
            return runtime_deps

        except Exception as e:
            logger.error(f"Failed to extract runtime dependencies: {e}", exc_info=True)
            raise

    def extract_build_deps(self, packages_with_deps: List[tuple]) -> Dict[str, List[str]]:
        """
        Extract build dependencies from source RPM packages.

        Args:
            packages_with_deps: List of tuples (PackageMetadata, List[Dependency])

        Returns:
            Dictionary mapping package names to their build dependencies
        """
        logger.info("Extracting build dependencies")

        try:
            build_deps = {}

            # Ensure provides map is built
            if not self.virtual_provides_map:
                logger.debug("Building provides map for dependency resolution")
                self._build_provides_map(packages_with_deps)

            # Count source packages
            source_packages = [p for p, _ in packages_with_deps if p.is_source]
            total_source = len(source_packages)
            logger.info(f"Processing {total_source} source packages")

            # Extract build dependencies from source packages
            processed = 0
            for metadata, dependencies in packages_with_deps:
                # Only process source packages for build dependencies
                if not metadata.is_source:
                    continue

                try:
                    # Validate package name
                    try:
                        pkg_name = validate_package_name(metadata.name)
                    except ValidationError as e:
                        logger.warning(f"Invalid package name {metadata.name}: {e}")
                        continue

                    requires = []

                    for dep in dependencies:
                        if dep.type in ("buildrequires", "requires"):
                            # Resolve and filter dependency
                            resolved_deps = self._resolve_dependency(dep.name)
                            requires.extend(resolved_deps)

                    # Remove duplicates and self-references
                    requires = list(set(requires))
                    if pkg_name in requires:
                        requires.remove(pkg_name)

                    build_deps[pkg_name] = requires
                    processed += 1

                except Exception as e:
                    logger.warning(f"Error extracting build deps for {metadata.name}: {e}")
                    logger.debug("Build dependency extraction error:", exc_info=True)
                    # Continue with empty dependencies
                    build_deps[metadata.name] = []

            logger.info(f"Extracted build dependencies for {len(build_deps)} packages")
            return build_deps

        except Exception as e:
            logger.error(f"Failed to extract build dependencies: {e}", exc_info=True)
            raise

    def _build_provides_map(self, packages_with_deps: List[tuple]) -> None:
        """
        Build a mapping of virtual provides to actual package names.

        Args:
            packages_with_deps: List of tuples (PackageMetadata, List[Dependency])
        """
        logger.info("Building virtual provides map")

        self.virtual_provides_map = {}

        for metadata, dependencies in packages_with_deps:
            pkg_name = metadata.name

            for dep in dependencies:
                if dep.type == "provides":
                    provide_name = dep.name

                    if provide_name not in self.virtual_provides_map:
                        self.virtual_provides_map[provide_name] = set()

                    self.virtual_provides_map[provide_name].add(pkg_name)

        logger.info(f"Built provides map with {len(self.virtual_provides_map)} entries")

    def _resolve_dependency(self, dep_name: str) -> List[str]:
        """
        Resolve a dependency name to actual package names.

        Args:
            dep_name: Dependency name (may be virtual or file path)

        Returns:
            List of resolved package names
        """
        # Filter out system dependencies
        if self._is_system_dependency(dep_name):
            return []

        # Check if it's a virtual provide
        if dep_name in self.virtual_provides_map:
            return list(self.virtual_provides_map[dep_name])

        # Check if it's a file path dependency
        if dep_name.startswith("/"):
            resolved = self._resolve_file_dependency(dep_name)
            if resolved:
                return resolved
            # If we can't resolve it, skip it
            return []

        # Otherwise, assume it's a direct package name
        return [dep_name]

    def _is_system_dependency(self, dep_name: str) -> bool:
        """
        Check if a dependency is a system-level dependency that should be filtered.

        Args:
            dep_name: Dependency name

        Returns:
            True if this is a system dependency to filter out
        """
        # Check against known system filters
        for filter_pattern in self.SYSTEM_FILTERS:
            if dep_name.startswith(filter_pattern):
                return True

        # Filter out shared library dependencies (.so files)
        if ".so" in dep_name and not dep_name.startswith("/"):
            return True

        return False

    def _resolve_file_dependency(self, file_path: str) -> List[str]:
        """
        Resolve file path dependencies to package names.

        Args:
            file_path: File path (e.g., /usr/bin/python)

        Returns:
            List of package names that provide this file
        """
        # Check if any package provides this file path
        if file_path in self.virtual_provides_map:
            return list(self.virtual_provides_map[file_path])

        # Try common file-to-package mappings
        file_mappings = {
            "/usr/bin/python": ["python3", "python"],
            "/usr/bin/python3": ["python3"],
            "/usr/bin/python2": ["python2"],
            "/usr/bin/perl": ["perl"],
            "/usr/bin/bash": ["bash"],
            "/bin/bash": ["bash"],
            "/bin/sh": ["bash"],
            "/usr/bin/sh": ["bash"],
        }

        if file_path in file_mappings:
            return file_mappings[file_path]

        # If we can't resolve it, return empty list
        return []
