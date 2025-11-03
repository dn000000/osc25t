# RPM Dependency Graph System

A Python-based application that analyzes RPM packages from the OpenScaler repository and generates interactive dependency graphs for both build-time and runtime dependencies.

## Features

- Downloads and parses RPM package metadata from OpenScaler repository
- Extracts build dependencies from SRPM packages
- Extracts runtime dependencies from binary RPM packages
- Constructs interactive dependency graphs
- Web-based visualization with zoom, pan, and search capabilities
- Detects circular dependencies
- Caches repository data for faster subsequent runs

## Requirements

- Python 3.8 or higher
- Internet connection for downloading repository metadata

### Platform Notes

- **Linux/macOS**: Full RPM parsing support with `rpm-py-installer`
- **Windows**: Limited support - repository metadata parsing works, but full RPM file parsing requires WSL or Linux environment

## Installation

### Quick Install

**On Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

**On Windows:**
```cmd
install.bat
```

### Manual Installation

1. Create a virtual environment:
```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate.bat
```

2. Install dependencies:
```bash
pip install --upgrade pip

# On Linux (with full RPM parsing support)
pip install -r requirements-linux.txt

# On Windows/macOS (basic functionality)
pip install -r requirements.txt
```

## Usage

### Running the Application

Use the run script:

**On Linux/macOS:**
```bash
chmod +x run.sh
./run.sh <repository-url>
```

**On Windows:**
```cmd
run.bat <repository-url>
```

**Example:**
```bash
# Linux/macOS
./run.sh https://example.com/openscaler/repo

# Windows
run.bat https://example.com/openscaler/repo
```

Or manually:

```bash
# Linux/macOS
source venv/bin/activate
python -m src.main --repo-url <repository-url>
python -m src.server

# Windows
venv\Scripts\activate.bat
python -m src.main --repo-url <repository-url>
python -m src.server
```

### Accessing the Web Interface

Once the server is running, open your browser and navigate to:
```
http://localhost:5000
```

### Command-Line Options

```bash
python -m src.main --help
```

**Available Options:**

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--repo-url URL` | RPM repository URL to analyze (required) | - | `--repo-url https://example.com/repo` |
| `--cache-dir PATH` | Directory for caching metadata | `data/cache` | `--cache-dir /tmp/cache` |
| `--output-dir PATH` | Directory for output graph files | `data` | `--output-dir ./output` |
| `--clear-cache` | Clear cached data before downloading | False | `--clear-cache` |
| `--verbose, -v` | Enable verbose logging (DEBUG level) | False | `--verbose` |

**Usage Examples:**

```bash
# Basic usage
python -m src.main --repo-url https://example.com/openscaler/repo

# Clear cache and re-download
python -m src.main --repo-url https://example.com/openscaler/repo --clear-cache

# Enable verbose logging for debugging
python -m src.main --repo-url https://example.com/openscaler/repo --verbose

# Custom cache and output directories
python -m src.main --repo-url https://example.com/openscaler/repo \
  --cache-dir /tmp/rpm-cache \
  --output-dir ./graphs
```

## Project Structure

```
rpm-dependency-graph/
├── src/                    # Source code
│   ├── main.py            # Entry point and orchestration
│   ├── repository.py      # Repository downloader
│   ├── parser.py          # RPM package parser
│   ├── extractor.py       # Dependency extractor
│   ├── graph.py           # Graph builder
│   ├── server.py          # Web server
│   └── utils.py           # Utility functions
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── templates/            # HTML templates
│   └── index.html       # Main web interface
├── static/              # Static assets
│   ├── css/            # Stylesheets
│   └── js/             # JavaScript files
├── data/               # Data storage
│   └── cache/         # Cached repository data
├── requirements.txt   # Python dependencies
├── install.sh        # Installation script
├── run.sh           # Run script
└── README.md        # This file
```

## Development

### Running Tests

Run all tests:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ -v --cov=src --cov-report=html
```

Run specific test categories:
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
```

### Code Quality

Format code:
```bash
black src/ tests/
```

Lint code:
```bash
flake8 src/ tests/
```

Type checking:
```bash
mypy src/
```

## Architecture

The system consists of three main layers:

1. **Data Acquisition Layer**: Downloads and caches repository metadata
2. **Parsing Layer**: Extracts package information and dependencies from RPM files
3. **Graph Construction Layer**: Builds graph data structures from parsed dependencies
4. **Presentation Layer**: Serves web interface and provides graph visualization

## API Endpoints

The web server provides the following REST API endpoints:

### `GET /`
Serves the main HTML page for interactive graph visualization.

**Response**: HTML page

### `GET /api/graphs`
Lists all available dependency graphs with metadata.

**Response**:
```json
{
  "graphs": [
    {
      "type": "runtime",
      "name": "Runtime Dependencies",
      "nodes": 1234,
      "edges": 5678,
      "available": true
    },
    {
      "type": "build",
      "name": "Build Dependencies",
      "nodes": 456,
      "edges": 789,
      "available": true
    }
  ],
  "data_directory": "data"
}
```

### `GET /api/graph/build`
Returns the build dependency graph data in JSON format.

**Response**:
```json
{
  "graph_type": "build",
  "nodes": [
    {
      "id": "package-name",
      "label": "package-name-1.0.0",
      "metadata": {
        "version": "1.0.0",
        "arch": "x86_64"
      }
    }
  ],
  "edges": [
    {
      "source": "package-a",
      "target": "package-b",
      "type": "requires"
    }
  ]
}
```

**Error Response** (404):
```json
{
  "error": "Build dependency graph not found",
  "message": "Please run the main.py script to generate dependency graphs"
}
```

### `GET /api/graph/runtime`
Returns the runtime dependency graph data in JSON format.

**Response**: Same format as `/api/graph/build` but with `"graph_type": "runtime"`

### `GET /static/<path:filename>`
Serves static files (CSS, JavaScript, images).

**Example**: `GET /static/css/style.css`

## Troubleshooting

### Installation Issues

#### Python version too old
**Symptoms**: Error message about Python version during installation

**Solution**:
```bash
# Check your Python version
python3 --version

# Install Python 3.8 or higher from python.org or your package manager
# Ubuntu/Debian
sudo apt-get install python3.8

# macOS (using Homebrew)
brew install python@3.8

# Windows: Download from python.org
```

#### pip install fails
**Symptoms**: Errors during `pip install` command

**Solutions**:
```bash
# Upgrade pip
pip install --upgrade pip

# If SSL errors occur
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# If permission errors occur (Linux/macOS)
pip install --user -r requirements.txt
```

#### Virtual environment activation fails
**Symptoms**: Cannot activate virtual environment

**Solutions**:
```bash
# Linux/macOS: Ensure execute permissions
chmod +x venv/bin/activate

# Windows: Enable script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Runtime Issues

#### Repository download fails
**Symptoms**: Error message about network or repository access

**Solutions**:
1. Check internet connection
2. Verify repository URL is correct and accessible
3. Check if repository requires authentication
4. Try with `--verbose` flag to see detailed error messages
5. Check firewall/proxy settings

```bash
# Test repository URL manually
curl -I https://example.com/openscaler/repo/repodata/repomd.xml

# Run with verbose logging
python -m src.main --repo-url <URL> --verbose
```

#### RPM parsing errors
**Symptoms**: Warnings about failed package parsing

**Solutions**:
1. Check log file: `rpm_dependency_graph.log`
2. Some parsing errors are normal for corrupted packages
3. The system continues processing other packages
4. If too many errors occur, verify repository integrity

```bash
# View recent errors
tail -n 50 rpm_dependency_graph.log | grep ERROR

# Check specific package
grep "package-name" rpm_dependency_graph.log
```

#### Web interface not loading
**Symptoms**: Browser shows "Connection refused" or similar error

**Solutions**:
1. Ensure Flask server is running:
   ```bash
   python -m src.server
   ```
2. Check if port 5000 is already in use:
   ```bash
   # Linux/macOS
   lsof -i :5000
   
   # Windows
   netstat -ano | findstr :5000
   ```
3. Try accessing via `http://127.0.0.1:5000` instead of `localhost`
4. Check firewall settings

#### Graph files not found (404 errors)
**Symptoms**: API returns "graph not found" errors

**Solutions**:
1. Ensure you've run the main script first:
   ```bash
   python -m src.main --repo-url <URL>
   ```
2. Check that graph files exist:
   ```bash
   ls -la data/*.json
   ```
3. Verify output directory matches server configuration

#### Empty or incomplete graphs
**Symptoms**: Graph visualization shows no nodes or very few nodes

**Solutions**:
1. Check if repository metadata was downloaded successfully
2. Verify package list is not empty
3. Check for parsing errors in logs
4. Ensure repository contains the expected package types (SRPM/binary RPM)

### Performance Issues

#### Processing takes too long
**Symptoms**: Script runs for more than 10 minutes

**Solutions**:
1. Use cached data (don't use `--clear-cache`)
2. Check network speed for initial download
3. Large repositories (>10,000 packages) may take longer
4. Monitor progress with `--verbose` flag

```bash
# Use cached data
python -m src.main --repo-url <URL>

# Monitor progress
python -m src.main --repo-url <URL> --verbose
```

#### High memory usage
**Symptoms**: System becomes slow or runs out of memory

**Solutions**:
1. Close other applications
2. Process smaller repositories first
3. Increase system swap space (Linux)
4. Consider processing in batches (requires code modification)

#### Web interface is slow
**Symptoms**: Graph visualization is laggy or unresponsive

**Solutions**:
1. Large graphs (>1000 nodes) may be slow to render
2. Use browser zoom controls to focus on specific areas
3. Use search functionality to find specific packages
4. Consider filtering the graph (requires code modification)
5. Try a different browser (Chrome/Firefox recommended)

### Common Error Messages

#### `ValidationError: Invalid repository URL`
**Cause**: Repository URL format is incorrect

**Solution**: Ensure URL starts with `http://` or `https://`

#### `RepositoryDownloadError: Failed to download after 3 attempts`
**Cause**: Network issues or invalid repository

**Solution**: Check network connection and repository URL

#### `PackageProcessingError: No packages were successfully parsed`
**Cause**: Repository metadata is empty or corrupted

**Solution**: Verify repository contains valid RPM packages

#### `FileNotFoundError: [Errno 2] No such file or directory: 'data/runtime_graph.json'`
**Cause**: Graph files haven't been generated yet

**Solution**: Run `python -m src.main --repo-url <URL>` first

### Getting Help

If you encounter issues not covered here:

1. Check the log file: `rpm_dependency_graph.log`
2. Run with `--verbose` flag for detailed output
3. Search existing issues on GitHub
4. Create a new issue with:
   - Error message
   - Log file excerpt
   - Python version (`python --version`)
   - Operating system
   - Steps to reproduce

## Security Considerations

This application implements multiple security measures to protect against common vulnerabilities:

### Input Validation

- **URL Validation**: All repository URLs are validated to prevent injection attacks and ensure only HTTP/HTTPS protocols are used
- **Package Name Sanitization**: Package names are validated against a strict pattern to prevent path traversal and injection attacks
- **File Path Validation**: All file paths are validated to prevent directory traversal attacks
- **Metadata Validation**: Package metadata (version, release, architecture) is validated and sanitized
- **Size Limits**: File size limits are enforced to prevent denial-of-service attacks (100MB for metadata, 500MB for RPM files)

### Safe File Operations

- **Context Managers**: All file operations use context managers to ensure proper resource cleanup
- **Atomic Writes**: Critical files (graph JSON outputs) use atomic write operations to prevent corruption
- **Temporary File Cleanup**: Temporary files are automatically cleaned up after processing
- **Path Traversal Prevention**: File paths are validated to ensure they remain within allowed directories

### Dependency Security

All Python dependencies are pinned to specific versions to ensure reproducible builds and prevent supply chain attacks:

```
Flask==3.0.0
requests==2.31.0
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0
black==23.12.1
flake8==7.0.0
mypy==1.8.0
types-requests==2.31.0.10
```

**Important**: Regularly update dependencies to receive security patches:
```bash
pip install --upgrade -r requirements.txt
```

### Network Security

- **HTTPS Preferred**: Repository downloads prefer HTTPS when available
- **Timeout Protection**: Network requests have timeouts to prevent hanging
- **Retry Logic**: Failed downloads use exponential backoff to prevent DoS
- **User-Agent Header**: Requests include a proper User-Agent header

### Web Server Security

- **Input Validation**: All API parameters are validated before processing
- **Path Traversal Protection**: Static file serving validates paths to prevent directory traversal
- **Error Handling**: Errors are logged without exposing sensitive information
- **Rate Limiting**: Consider implementing rate limiting in production deployments

### Best Practices for Deployment

1. **Run with Least Privilege**: Run the application with minimal required permissions
2. **Use HTTPS**: Deploy behind a reverse proxy with HTTPS in production
3. **Firewall Configuration**: Restrict network access to only required ports
4. **Regular Updates**: Keep Python and all dependencies up to date
5. **Log Monitoring**: Monitor logs for suspicious activity
6. **Input Sanitization**: Never trust external input - all input is validated
