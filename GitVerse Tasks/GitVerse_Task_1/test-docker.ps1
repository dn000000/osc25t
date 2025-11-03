# Automated build and test pipeline for sysaudit project in Docker (PowerShell)
# Usage: .\test-docker.ps1 [options]

param(
    [switch]$Help,
    [switch]$SkipBuild,
    [switch]$SkipUnit,
    [switch]$SkipIntegration,
    [switch]$SkipE2E,
    [switch]$SkipCoverage,
    [switch]$Quick,
    [switch]$Verbose,
    [switch]$Clean,
    [switch]$NoCache,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

# Configuration
$ImageName = "sysaudit:test"
$ContainerName = "sysaudit-test-runner"
$ResultsDir = "test-results"
$CoverageDir = "htmlcov"

# Output functions
function Write-Header($message) {
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host "  $message" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
}

function Write-Step($message) {
    Write-Host "> $message" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Error2($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

function Write-Warning2($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Blue
}

# Help function
function Show-Help {
    @"
Usage: .\test-docker.ps1 [OPTIONS]

Automated build and test pipeline for sysaudit project in Docker

OPTIONS:
    -Help               Show this help
    -SkipBuild          Skip image build
    -SkipUnit           Skip unit tests
    -SkipIntegration    Skip integration tests
    -SkipE2E            Skip E2E tests
    -SkipCoverage       Skip coverage generation
    -Quick              Quick mode (unit tests only)
    -Verbose            Verbose output
    -Clean              Clean results before run
    -NoCache            Build image without cache
    -Rebuild            Full rebuild from scratch (clean + no-cache + prune)

EXAMPLES:
    .\test-docker.ps1                    # Full test run
    .\test-docker.ps1 -Quick             # Quick run (unit only)
    .\test-docker.ps1 -SkipE2E           # All tests except E2E
    .\test-docker.ps1 -Rebuild           # Complete rebuild from scratch

"@
}

# Show help
if ($Help) {
    Show-Help
    exit 0
}

# Rebuild mode - full clean rebuild
if ($Rebuild) {
    $Clean = $true
    $NoCache = $true
    Write-Info "Rebuild mode: Full clean rebuild from scratch"
}

# Quick mode
if ($Quick) {
    $SkipIntegration = $true
    $SkipE2E = $true
}

# Check Docker
function Test-Docker {
    Write-Step "Checking Docker..."
    if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error2 "Docker is not installed"
        exit 1
    }
    $version = docker --version
    Write-Success "Docker installed: $version"
}

# Cleanup
function Clear-Results {
    if ($Clean) {
        Write-Step "Cleaning previous results..."
        if (Test-Path $ResultsDir) { Remove-Item -Recurse -Force $ResultsDir }
        if (Test-Path $CoverageDir) { Remove-Item -Recurse -Force $CoverageDir }
        docker rm -f $ContainerName 2>$null | Out-Null 2>&1
        Write-Success "Cleanup completed"
    }
    
    if ($Rebuild) {
        Write-Step "Pruning Docker build cache..."
        docker builder prune -f > $null 2>&1
        Write-Step "Removing old images..."
        docker rmi -f $ImageName 2>$null | Out-Null 2>&1
        Write-Success "Docker cleanup completed"
    }
}

# Create directories
function New-Directories {
    Write-Step "Creating result directories..."
    New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $CoverageDir | Out-Null
    Write-Success "Directories created"
}

# Build image
function Build-Image {
    if ($SkipBuild) {
        Write-Warning2 "Skipping image build"
        return
    }
    
    Write-Header "DOCKER IMAGE BUILD"
    Write-Step "Building image $ImageName..."
    
    $startTime = Get-Date
    
    $buildArgs = @("-t", $ImageName)
    if ($NoCache) { $buildArgs += "--no-cache" }
    $buildArgs += "."
    
    if ($Verbose) {
        docker build @buildArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error2 "Image build failed"
            exit 1
        }
    } else {
        # Suppress output but check exit code
        $ErrorActionPreference = "Continue"
        docker build @buildArgs > $null 2>&1
        $buildResult = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        
        if ($buildResult -ne 0) {
            Write-Error2 "Image build failed"
            exit 1
        }
    }
    
    $duration = ((Get-Date) - $startTime).TotalSeconds
    Write-Success "Image built in $([math]::Round($duration, 1))s"
}

# Run unit tests
function Invoke-UnitTests {
    if ($SkipUnit) {
        Write-Warning2 "Skipping unit tests"
        return $true
    }
    
    Write-Header "UNIT TESTS"
    Write-Step "Running all pytest tests (272 tests including E2E integration tests)..."
    
    $runArgs = @("run", "--rm")
    $runArgs += "-v"
    $runArgs += "${PWD}/${ResultsDir}:/app/test-results"
    $runArgs += "-v"
    $runArgs += "${PWD}/${CoverageDir}:/app/htmlcov"
    $runArgs += $ImageName
    $runArgs += "python"
    $runArgs += "-m"
    $runArgs += "pytest"
    $runArgs += "tests/"
    $runArgs += "-v"
    $runArgs += "--ignore=tests/e2e/test_real_user_scenarios.py"
    
    if (-not $SkipCoverage) {
        $runArgs += "--cov=sysaudit"
        $runArgs += "--cov-report=html"
        $runArgs += "--cov-report=term-missing"
    }
    
    $output = docker @runArgs 2>&1
    $exitCode = $LASTEXITCODE
    $outputString = $output | Out-String
    Write-Host $outputString
    
    # Parse pytest output to create JSON report
    $passed = 0
    $failed = 0
    
    # Look for the summary line like "272 passed in 24.59s"
    if ($outputString -match "=+\s+(\d+)\s+passed.*in\s+[\d.]+s\s+=+") {
        $passed = [int]$matches[1]
    }
    
    if ($outputString -match "(\d+)\s+failed") {
        $failed = [int]$matches[1]
    }
    
    # Create JSON report manually to avoid locale issues
    $total = $passed + $failed
    if ($total -gt 0) {
        $successRate = [math]::Round(($passed / $total) * 100, 1)
        $successRateStr = "$successRate%"
    } else {
        $successRateStr = "N/A"
    }
    
    $timestamp = (Get-Date).ToString("o")
    $pytestReport = @"
{
  "timestamp": "$timestamp",
  "test_type": "pytest",
  "passed": $passed,
  "failed": $failed,
  "total": $total,
  "success_rate": "$successRateStr"
}
"@
    
    [System.IO.File]::WriteAllText("$ResultsDir/pytest-report.json", $pytestReport)
    
    if ($exitCode -eq 0) {
        Write-Success "Unit tests passed ($passed tests)"
        return $true
    } else {
        Write-Error2 "Unit tests failed"
        return $false
    }
}

# Run integration tests (deprecated - kept for compatibility)
function Invoke-IntegrationTests {
    if ($SkipIntegration) {
        Write-Warning2 "Skipping integration tests"
        return $true
    }
    
    # Integration tests are now part of unit tests
    Write-Warning2 "Integration tests are included in unit tests (skipping separate run)"
    return $true
}

# Run E2E tests
function Invoke-E2ETests {
    if ($SkipE2E) {
        Write-Warning2 "Skipping E2E tests"
        return $true
    }
    
    Write-Header "E2E TESTS"
    Write-Step "Running E2E user scenario tests (20 scenarios)..."
    
    $runArgs = @("run", "--rm", "--user", "root", "-v", "${PWD}/${ResultsDir}:/app/test-results", "-e", "PYTHONUNBUFFERED=1", $ImageName, "python", "tests/e2e/test_real_user_scenarios.py")
    docker @runArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "E2E scenario tests passed"
        return $true
    } else {
        Write-Error2 "E2E scenario tests failed"
        return $false
    }
}

# Generate final report
function New-Report {
    Write-Header "REPORT GENERATION"
    Write-Step "Creating final report..."
    
    python scripts/generate_report.py $ResultsDir
    
    Write-Success "Report created"
}

# Show results
function Show-Results {
    Write-Header "TEST RESULTS"
    
    if (Test-Path "$ResultsDir/final-report.json") {
        python scripts/show_report.py $ResultsDir
    }
    
    Write-Host ""
    Write-Info "Test results: $ResultsDir/"
    
    if (-not $SkipCoverage -and (Test-Path "$CoverageDir/index.html")) {
        Write-Info "Coverage report: $CoverageDir/index.html"
    }
    
    Write-Info "Final report: $ResultsDir/final-report.json"
}

# Main function
function Main {
    $startTime = Get-Date
    $failed = $false
    
    Write-Header "SYSAUDIT DOCKER TEST PIPELINE"
    
    Test-Docker
    Clear-Results
    New-Directories
    Build-Image
    
    # Run tests
    if (-not (Invoke-UnitTests)) { $failed = $true }
    
    if (-not $failed) {
        if (-not (Invoke-IntegrationTests)) { $failed = $true }
    }
    
    if (-not $failed) {
        if (-not (Invoke-E2ETests)) { $failed = $true }
    }
    
    # Generate report
    New-Report
    
    # Show results
    $totalDuration = ((Get-Date) - $startTime).TotalSeconds
    
    Show-Results
    
    Write-Host ""
    Write-Info "Total execution time: $([math]::Round($totalDuration, 1))s"
    
    if ($failed) {
        Write-Host ""
        Write-Error2 "Some tests failed"
        exit 1
    } else {
        Write-Host ""
        Write-Success "All tests passed successfully!"
        exit 0
    }
}

# Run
Main
