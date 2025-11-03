"""
Sample repository data for testing.

Provides minimal test repository with known dependencies including:
- Simple linear dependencies
- Circular dependencies
- Missing dependencies
"""

from src.repository import PackageInfo
from src.parser import PackageMetadata, Dependency


# Sample repository metadata XML
SAMPLE_REPOMD_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo">
  <data type="primary">
    <location href="repodata/primary.xml.gz"/>
    <checksum type="sha256">abc123def456</checksum>
  </data>
</repomd>
"""


# Sample primary.xml with various package types
SAMPLE_PRIMARY_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" packages="8">
  <package type="rpm">
    <name>web-server</name>
    <arch>x86_64</arch>
    <version ver="2.4.0" rel="1"/>
    <checksum type="sha256">aaa111</checksum>
    <location href="Packages/web-server-2.4.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>database</name>
    <arch>x86_64</arch>
    <version ver="10.5.0" rel="1"/>
    <checksum type="sha256">bbb222</checksum>
    <location href="Packages/database-10.5.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>auth-lib</name>
    <arch>x86_64</arch>
    <version ver="1.2.3" rel="1"/>
    <checksum type="sha256">ccc333</checksum>
    <location href="Packages/auth-lib-1.2.3-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>logger</name>
    <arch>x86_64</arch>
    <version ver="3.0.0" rel="1"/>
    <checksum type="sha256">ddd444</checksum>
    <location href="Packages/logger-3.0.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>circular-a</name>
    <arch>x86_64</arch>
    <version ver="1.0.0" rel="1"/>
    <checksum type="sha256">eee555</checksum>
    <location href="Packages/circular-a-1.0.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>circular-b</name>
    <arch>x86_64</arch>
    <version ver="1.0.0" rel="1"/>
    <checksum type="sha256">fff666</checksum>
    <location href="Packages/circular-b-1.0.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>web-server</name>
    <arch>src</arch>
    <version ver="2.4.0" rel="1"/>
    <checksum type="sha256">ggg777</checksum>
    <location href="Packages/web-server-2.4.0-1.src.rpm"/>
  </package>
  <package type="rpm">
    <name>database</name>
    <arch>src</arch>
    <version ver="10.5.0" rel="1"/>
    <checksum type="sha256">hhh888</checksum>
    <location href="Packages/database-10.5.0-1.src.rpm"/>
  </package>
</metadata>
"""


def get_sample_package_list():
    """
    Get a sample package list with various dependency scenarios.

    Returns:
        List of PackageInfo objects
    """
    return [
        # Binary packages
        PackageInfo(
            name="web-server",
            version="2.4.0",
            release="1",
            arch="x86_64",
            location="Packages/web-server-2.4.0-1.x86_64.rpm",
            checksum="aaa111",
            is_source=False,
        ),
        PackageInfo(
            name="database",
            version="10.5.0",
            release="1",
            arch="x86_64",
            location="Packages/database-10.5.0-1.x86_64.rpm",
            checksum="bbb222",
            is_source=False,
        ),
        PackageInfo(
            name="auth-lib",
            version="1.2.3",
            release="1",
            arch="x86_64",
            location="Packages/auth-lib-1.2.3-1.x86_64.rpm",
            checksum="ccc333",
            is_source=False,
        ),
        PackageInfo(
            name="logger",
            version="3.0.0",
            release="1",
            arch="x86_64",
            location="Packages/logger-3.0.0-1.x86_64.rpm",
            checksum="ddd444",
            is_source=False,
        ),
        PackageInfo(
            name="circular-a",
            version="1.0.0",
            release="1",
            arch="x86_64",
            location="Packages/circular-a-1.0.0-1.x86_64.rpm",
            checksum="eee555",
            is_source=False,
        ),
        PackageInfo(
            name="circular-b",
            version="1.0.0",
            release="1",
            arch="x86_64",
            location="Packages/circular-b-1.0.0-1.x86_64.rpm",
            checksum="fff666",
            is_source=False,
        ),
        # Source packages
        PackageInfo(
            name="web-server",
            version="2.4.0",
            release="1",
            arch="src",
            location="Packages/web-server-2.4.0-1.src.rpm",
            checksum="ggg777",
            is_source=True,
        ),
        PackageInfo(
            name="database",
            version="10.5.0",
            release="1",
            arch="src",
            location="Packages/database-10.5.0-1.src.rpm",
            checksum="hhh888",
            is_source=True,
        ),
    ]


def get_linear_dependencies():
    """
    Get packages with simple linear dependencies: A -> B -> C.

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        (
            PackageMetadata("pkg-a", "1.0.0", "1", "x86_64", False),
            [Dependency("pkg-b", type="requires")],
        ),
        (
            PackageMetadata("pkg-b", "1.0.0", "1", "x86_64", False),
            [Dependency("pkg-c", type="requires")],
        ),
        (PackageMetadata("pkg-c", "1.0.0", "1", "x86_64", False), []),
    ]


def get_circular_dependencies():
    """
    Get packages with circular dependencies: A -> B -> C -> A.

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        (
            PackageMetadata("circular-a", "1.0.0", "1", "x86_64", False),
            [Dependency("circular-b", type="requires")],
        ),
        (
            PackageMetadata("circular-b", "1.0.0", "1", "x86_64", False),
            [Dependency("circular-c", type="requires")],
        ),
        (
            PackageMetadata("circular-c", "1.0.0", "1", "x86_64", False),
            [Dependency("circular-a", type="requires")],
        ),
    ]


def get_missing_dependencies():
    """
    Get packages with dependencies on non-existent packages.

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        (
            PackageMetadata("app-with-missing-deps", "1.0.0", "1", "x86_64", False),
            [
                Dependency("existing-lib", type="requires"),
                Dependency("missing-package", type="requires"),
                Dependency("another-missing-pkg", type="requires"),
            ],
        ),
        (PackageMetadata("existing-lib", "1.0.0", "1", "x86_64", False), []),
    ]


def get_complex_dependencies():
    """
    Get packages with complex dependency relationships.

    Includes:
    - Multiple dependencies per package
    - Diamond dependency pattern (A -> B, A -> C, B -> D, C -> D)
    - Both runtime and build dependencies

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        # Binary packages with runtime dependencies
        (
            PackageMetadata("web-server", "2.4.0", "1", "x86_64", False),
            [
                Dependency("database", type="requires"),
                Dependency("auth-lib", type="requires"),
                Dependency("logger", type="requires"),
            ],
        ),
        (
            PackageMetadata("database", "10.5.0", "1", "x86_64", False),
            [
                Dependency("logger", type="requires"),
            ],
        ),
        (
            PackageMetadata("auth-lib", "1.2.3", "1", "x86_64", False),
            [
                Dependency("logger", type="requires"),
            ],
        ),
        (PackageMetadata("logger", "3.0.0", "1", "x86_64", False), []),
        # Source packages with build dependencies
        (
            PackageMetadata("web-server", "2.4.0", "1", "src", True),
            [
                Dependency("gcc", type="buildrequires"),
                Dependency("make", type="buildrequires"),
                Dependency("openssl-devel", type="buildrequires"),
            ],
        ),
        (
            PackageMetadata("database", "10.5.0", "1", "src", True),
            [
                Dependency("gcc", type="buildrequires"),
                Dependency("cmake", type="buildrequires"),
            ],
        ),
    ]


def get_self_loop_dependencies():
    """
    Get packages with self-loop dependencies (package depends on itself).

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        (
            PackageMetadata("self-loop-pkg", "1.0.0", "1", "x86_64", False),
            [Dependency("self-loop-pkg", type="requires")],
        ),
    ]


def get_multiple_circular_dependencies():
    """
    Get packages with multiple independent circular dependency chains.

    Chain 1: A -> B -> A
    Chain 2: C -> D -> E -> C

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        # First circular chain
        (
            PackageMetadata("cycle1-a", "1.0.0", "1", "x86_64", False),
            [Dependency("cycle1-b", type="requires")],
        ),
        (
            PackageMetadata("cycle1-b", "1.0.0", "1", "x86_64", False),
            [Dependency("cycle1-a", type="requires")],
        ),
        # Second circular chain
        (
            PackageMetadata("cycle2-c", "1.0.0", "1", "x86_64", False),
            [Dependency("cycle2-d", type="requires")],
        ),
        (
            PackageMetadata("cycle2-d", "1.0.0", "1", "x86_64", False),
            [Dependency("cycle2-e", type="requires")],
        ),
        (
            PackageMetadata("cycle2-e", "1.0.0", "1", "x86_64", False),
            [Dependency("cycle2-c", type="requires")],
        ),
    ]


def get_mixed_runtime_and_build_dependencies():
    """
    Get packages with both runtime and build dependencies.

    Returns:
        List of tuples (PackageMetadata, List[Dependency])
    """
    return [
        # Binary package with runtime deps
        (
            PackageMetadata("application", "1.0.0", "1", "x86_64", False),
            [
                Dependency("runtime-lib", type="requires"),
                Dependency("python3", type="requires"),
            ],
        ),
        (PackageMetadata("runtime-lib", "1.0.0", "1", "x86_64", False), []),
        (PackageMetadata("python3", "3.9.0", "1", "x86_64", False), []),
        # Source package with build deps
        (
            PackageMetadata("application", "1.0.0", "1", "src", True),
            [
                Dependency("gcc", type="buildrequires"),
                Dependency("python3-devel", type="buildrequires"),
                Dependency("make", type="buildrequires"),
            ],
        ),
    ]
