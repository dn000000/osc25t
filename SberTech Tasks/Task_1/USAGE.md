# RPM Dependency Graph - Usage Guide

This guide provides step-by-step instructions for testing the RPM Dependency Graph system using the OpenScaler repository.

## Quick Start

```bash
# For Runtime Dependencies (binary packages) - FAST
./run.sh https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/

# For Build Dependencies (source packages) - SLOW (downloads RPMs)
./run_with_deps.sh https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/ --max-packages 10
```

**Important:** Always use the full path to the package directory, not just the base URL!

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Understanding Repository URLs](#understanding-repository-urls)
- [Testing Build Dependencies](#testing-build-dependencies)
- [Testing Runtime Dependencies](#testing-runtime-dependencies)
- [Advanced Usage](#advanced-usage)
- [Web Interface](#web-interface)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.8 or higher
- Internet connection (to download RPM metadata)
- Windows, Linux, or macOS

## Installation

### Windows

```cmd
# Clone or navigate to the project directory
cd path\to\task_1

# Run the installation script
install.bat
```

### Linux/macOS

```bash
# Clone or navigate to the project directory
cd path/to/task_1

# Make the script executable and run it
chmod +x install.sh
./install.sh
```

The installation script will:
1. Create a Python virtual environment
2. Install all required dependencies
3. Optionally install RPM Python library (if available)
4. Verify the installation

**Note:** The RPM Python library is optional. If it fails to install, the application will use manual RPM parsing, which is slower but fully functional.

## Testing Build Dependencies

Build dependencies show what packages are needed to compile/build source packages.

### Quick Test (10 packages)

**Important:** For source packages, use the `/source/Packages/` path.

```cmd
# Windows - Source packages (Build Dependencies)
run_with_deps.bat https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/ --max-packages 10

# Linux/macOS - Source packages (Build Dependencies)
./run_with_deps.sh https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/ --max-packages 10
```

**Expected Results:**
- Downloads 10 source RPM files (~50 seconds)
- Extracts dependencies from RPM headers
- Builds graph with ~87 nodes and ~92 edges
- Opens web interface at http://localhost:5000

### Medium Test (100 packages)

```cmd
run_with_deps.bat https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/ --max-packages 100
```

**Expected Results:**
- Downloads 100 source RPM files (~8-10 minutes)
- Builds larger dependency graph
- More comprehensive view of build dependencies

### Full Repository (4866 packages)

⚠️ **Warning:** This will download ~4866 RPM files and may take 1-2 hours depending on network speed.

```cmd
run_with_deps.bat https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/
```

## Understanding Repository URLs

RPM repositories have different directories for different types of packages:

- **Binary Packages** (for runtime dependencies):
  - Path: `/OS/x86_64/` or `/OS/aarch64/`
  - Contains compiled packages ready to install
  - Example: `https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/`

- **Source Packages** (for build dependencies):
  - Path: `/source/Packages/`
  - Contains source code and build instructions
  - Example: `https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/`

**Important:** Always use the full path to the specific package directory, not just the base repository URL.

## Testing Runtime Dependencies

Runtime dependencies show what packages are needed for installed software to run.

### Standard Test (Fast - No RPM Downloads)

**URL Format:** Use `/OS/x86_64/` for binary packages.

```cmd
# Windows - Binary packages (Runtime Dependencies)
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/

# Linux/macOS - Binary packages (Runtime Dependencies)
./run.sh https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/
```

**Expected Results:**
- Downloads only repository metadata (~3 seconds)
- Processes 2540 binary packages
- Builds graph with 2547 nodes and 5716 edges
- Detects 132 circular dependencies
- Opens web interface at http://localhost:5000

**Note:** This uses pre-built metadata from the repository, so it's very fast.

**Automatic Fallback:** If standard metadata is not available (404 error), the system automatically falls back to HTML directory listing parsing.

### Alternative Architectures

For ARM64 systems:

```cmd
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/aarch64/
```

## How It Works

The system uses a smart fallback mechanism:

1. **Standard Metadata (Preferred)**
   - Tries to download `repodata/repomd.xml` and `primary.xml`
   - Fast and efficient
   - Works with standard RPM repositories

2. **HTML Directory Listing (Automatic Fallback)**
   - Activates when standard metadata is not found (404 error)
   - Parses HTML page to find `.rpm` files
   - Creates synthetic metadata
   - Works with simple file listings

3. **Full RPM Parsing (Optional)**
   - Use `run_with_deps.bat/sh` scripts
   - Downloads actual RPM files
   - Extracts dependencies from RPM headers
   - Most accurate but slowest

## Advanced Usage

### Verbose Mode

Get detailed logging information:

```cmd
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/ --verbose
```

### Clear Cache

Force re-download of repository metadata:

```cmd
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/ --clear-cache
```

### Custom Output Directory

Save graphs to a specific location:

```cmd
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/ --output-dir custom_output
```

### Combine Options

```cmd
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/ --verbose --clear-cache --output-dir results
```

## Web Interface

After running any command, the web interface automatically opens at http://localhost:5000

### Features

1. **Graph Type Selection**
   - Switch between Runtime and Build Dependencies
   - Dropdown in top-left corner

2. **Search Functionality**
   - Enter package name in search box
   - Highlights matching packages
   - Centers view on found package

3. **Package Details**
   - Click any node to see details
   - Shows dependencies and dependents
   - Panel appears on the right side

4. **Navigation Controls**
   - **Reset View**: Return to default zoom/position
   - **Fit to Screen**: Adjust zoom to show all nodes
   - Mouse wheel: Zoom in/out
   - Click and drag: Pan the graph

5. **Statistics**
   - Total Packages count
   - Dependencies count
   - Circular Dependencies count

### Graph Visualization

- **Blue nodes**: Regular packages
- **Green nodes**: Highlighted connections when clicking a node
- **Red nodes**: Search results
- **Orange nodes**: Selected package
- **Gray arrows**: Dependencies
- **Green arrows**: Highlighted dependencies

### Performance Notes

- Graphs with >500 nodes show only first 500 for performance
- Use search to find specific packages in large graphs
- Large graphs use circle layout for faster rendering

## Troubleshooting

### Issue: "Virtual environment not found"

**Solution:** Run the installation script first:
```cmd
install.bat  # Windows
./install.sh # Linux/macOS
```

### Issue: "Failed to download repository" or "No RPM files found"

**Possible causes:**
1. Incorrect repository URL (most common)
2. No internet connection
3. Repository is temporarily unavailable

**Solution:** 

1. **Check URL format** - Make sure you're using the full path:
   ```
   ✗ Wrong: https://repo.openscaler.ru/openScaler-24.03-LTS/
   ✓ Right: https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/
   
   ✗ Wrong: https://repo.openscaler.ru/openScaler-24.03-LTS/source/
   ✓ Right: https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/
   ```

2. **Verify URL in browser** - Open the URL and check if you see:
   - For binary repos: `repodata/` directory or list of `.rpm` files
   - For source repos: list of `.src.rpm` files

3. **Check internet connection**

### Issue: "Graph is empty" or "Loading forever"

**Cause:** Graph may be too large for browser to render.

**Solution:** The system automatically limits to 500 nodes. If still having issues:
1. Clear browser cache (Ctrl+F5)
2. Try a different browser
3. Check browser console (F12) for errors

### Issue: "zstandard library not installed"

**Solution:** Install the missing dependency:
```cmd
# Activate virtual environment first
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Install zstandard
pip install zstandard
```

### Issue: "rpm-py-installer failed to install" (Linux)

**This is not an error!** The RPM Python library is optional.

**What happens:**
- The application will use manual RPM header parsing
- Slightly slower but fully functional
- No action needed

**If you want to install it anyway:**
1. Install system RPM development packages:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install rpm librpm-dev python3-dev
   
   # Fedora/RHEL/CentOS
   sudo dnf install rpm-devel python3-devel
   ```

2. Re-run installation:
   ```bash
   source venv/bin/activate
   pip install rpm-py-installer
   ```

### Issue: Slow performance with large graphs

**Solutions:**
1. Use `--max-packages` to limit the number of packages
2. Search for specific packages instead of viewing entire graph
3. Use Runtime Dependencies (faster) instead of Build Dependencies

### Issue: "Port 5000 already in use"

**Solution:** Stop other applications using port 5000, or modify `src/server.py` to use a different port.

## Example Workflows

### Workflow 1: Quick Dependency Check

```cmd
# 1. Check runtime dependencies (fast)
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/

# 2. Open browser to http://localhost:5000

# 3. Search for a specific package (e.g., "python3")

# 4. Click on the package to see its dependencies
```

### Workflow 2: Build Dependency Analysis

```cmd
# 1. Extract dependencies from 50 source packages
run_with_deps.bat https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/ --max-packages 50

# 2. Wait for download and processing (~4-5 minutes)

# 3. Switch to "Build Dependencies" in web interface

# 4. Analyze what packages are needed to build software
```

### Workflow 3: Compare Dependencies

```cmd
# 1. Generate runtime dependencies
run.bat https://repo.openscaler.ru/openScaler-24.03-LTS/OS/x86_64/

# 2. In another terminal, generate build dependencies
run_with_deps.bat https://repo.openscaler.ru/openScaler-24.03-LTS/source/Packages/ --max-packages 20

# 3. Switch between graph types in web interface to compare
```

## Output Files

After running the system, the following files are created in the `data/` directory:

- `runtime_graph.json` - Runtime dependency graph
- `build_graph.json` - Build dependency graph
- `graph_summary.json` - Statistics summary
- `cache/` - Cached repository metadata and RPM files

## Performance Benchmarks

Based on OpenScaler repository:

| Operation | Packages | Time | Notes |
|-----------|----------|------|-------|
| Runtime metadata download | 2540 | ~3s | Fast, uses repo metadata |
| Build metadata (10 packages) | 10 | ~50s | Downloads RPM files |
| Build metadata (100 packages) | 100 | ~8-10min | Downloads RPM files |
| Build metadata (full) | 4866 | ~1-2hrs | Downloads all RPM files |
| Graph rendering (<500 nodes) | <500 | <1s | Smooth in browser |
| Graph rendering (500-1000 nodes) | 500-1000 | 1-3s | May be slow |
| Graph rendering (>1000 nodes) | >1000 | Limited to 500 | Auto-limited for performance |

## Additional Resources

- **README.md** - Project overview and features
- **SECURITY.md** - Security considerations
- **requirements.txt** - Python dependencies
- **tests/** - Unit and integration tests

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review log files in the project directory
3. Check browser console (F12) for JavaScript errors
4. Verify repository URLs are accessible in a web browser
