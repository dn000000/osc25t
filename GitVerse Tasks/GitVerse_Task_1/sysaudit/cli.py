"""CLI interface for Git-based System Audit & Compliance Monitor"""
import click
import sys
import os
from pathlib import Path
import yaml
import time
import signal
import shutil
import traceback
from datetime import datetime
from sysaudit.git.manager import GitManager
from sysaudit.git.drift import DriftDetector
from sysaudit.git.rollback import RollbackManager
from sysaudit.compliance.checker import ComplianceChecker
from sysaudit.compliance.reporter import ComplianceReporter
from sysaudit.config import Config
from sysaudit.monitor.file_monitor import FileMonitor
from sysaudit.monitor.filter import FilterManager


# Error handling utilities
def handle_error(error, verbose=False):
    """Handle and display errors in a user-friendly way"""
    error_msg = str(error)
    
    # Provide helpful context for common errors
    if "Permission denied" in error_msg or isinstance(error, PermissionError):
        click.echo("✗ Permission denied. Try running with sudo or as root.", err=True)
    elif "No such file or directory" in error_msg or isinstance(error, FileNotFoundError):
        click.echo(f"✗ File or directory not found: {error_msg}", err=True)
    elif "Repository" in error_msg and "not found" in error_msg:
        click.echo("✗ Git repository not initialized. Run 'sysaudit init' first.", err=True)
    else:
        click.echo(f"✗ Error: {error_msg}", err=True)
    
    if verbose:
        click.echo("\nDetailed traceback:", err=True)
        traceback.print_exc()


def validate_repo_exists(repo_path, suggest_init=True):
    """Validate that repository exists and is initialized"""
    if not os.path.exists(repo_path):
        click.echo(f"Error: Repository path does not exist: {repo_path}", err=True)
        if suggest_init:
            click.echo("Run 'sysaudit init' first to initialize the repository", err=True)
        return False
    
    # Check if it's a git repository
    git_dir = os.path.join(repo_path, '.git')
    if not os.path.exists(git_dir):
        click.echo(f"Error: {repo_path} is not a Git repository", err=True)
        if suggest_init:
            click.echo("Run 'sysaudit init' first to initialize the repository", err=True)
        return False
    
    return True


def load_config_or_exit(config_file, repo, watch_paths=None, require_repo=True):
    """Load configuration from file or CLI args, exit on error"""
    config = None
    
    if config_file:
        if not os.path.exists(config_file):
            click.echo(f"Error: Configuration file not found: {config_file}", err=True)
            sys.exit(1)
        
        try:
            config = Config.from_yaml(config_file)
            click.echo(f"Loaded configuration from {config_file}")
        except Exception as e:
            click.echo(f"Error: Failed to load configuration: {e}", err=True)
            sys.exit(1)
    else:
        if require_repo and not repo:
            click.echo("Error: Either --config or --repo must be specified", err=True)
            sys.exit(1)
        
        config = Config(
            repo_path=repo or '/tmp/sysaudit',
            watch_paths=list(watch_paths) if watch_paths else [],
            baseline_branch='main'
        )
    
    return config


@click.group()
@click.version_option(version='0.1.0')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output', envvar='SYSAUDIT_VERBOSE')
@click.pass_context
def cli(ctx, verbose):
    """Git-based System Audit & Compliance Monitor
    
    A tool for continuous monitoring of file system changes with automatic
    Git versioning and compliance checking.
    
    Environment Variables:
        SYSAUDIT_VERBOSE: Enable verbose output (1, true, yes)
    
    Examples:
        sysaudit init --repo /var/lib/sysaudit
        sysaudit monitor --config /etc/sysaudit/config.yaml
        sysaudit drift-check --baseline main --repo /var/lib/sysaudit
    """
    # Store verbose flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    if verbose:
        click.echo("Verbose mode enabled", err=True)


@cli.command()
@click.option('--repo', required=True, help='Path to audit repository')
@click.option('--baseline', default='main', help='Baseline branch name (default: main)')
@click.option('--config-dir', default='/etc/sysaudit', help='Configuration directory (default: /etc/sysaudit)')
@click.pass_context
def init(ctx, repo, baseline, config_dir):
    """Initialize the audit system
    
    Creates a Git repository for tracking file changes and sets up
    the initial configuration structure.
    
    Example:
        sysaudit init --repo /var/lib/sysaudit --baseline main
    """
    verbose = ctx.obj.get('verbose', False)
    
    try:
        click.echo(f"Initializing audit system...")
        click.echo(f"Repository path: {repo}")
        click.echo(f"Baseline branch: {baseline}")
        
        # Create repository directory
        repo_path = Path(repo)
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Create a minimal Config object for initialization
        # Use repo path as dummy watch path since Config requires at least one
        config = Config(
            repo_path=str(repo_path),
            watch_paths=[str(repo_path)],  # Dummy watch path for init
            baseline_branch=baseline
        )
        
        # Initialize Git repository
        git_manager = GitManager(config)
        git_manager.init_repo(baseline_branch=baseline)
        
        click.echo(f"✓ Git repository initialized at {repo}")
        click.echo(f"✓ Baseline branch '{baseline}' created")
        
        # Create configuration directory
        config_path = Path(config_dir)
        config_path.mkdir(parents=True, exist_ok=True)
        
        # Create example configuration file if it doesn't exist
        config_file = config_path / 'config.yaml'
        if not config_file.exists():
            example_config = {
                'repository': {
                    'path': str(repo),
                    'baseline': baseline,
                    'gpg_sign': False
                },
                'monitoring': {
                    'paths': ['/etc'],
                    'blacklist_file': str(config_path / 'blacklist.txt'),
                    'whitelist_file': None,
                    'batch_interval': 5,
                    'batch_size': 10
                },
                'compliance': {
                    'auto_check': False,
                    'rules': ['world-writable', 'suid-sgid', 'weak-permissions']
                },
                'alerts': {
                    'enabled': True,
                    'webhook_url': None,
                    'journal_priority': 'CRIT'
                }
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(example_config, f, default_flow_style=False)
            
            click.echo(f"✓ Configuration file created at {config_file}")
        
        # Create example blacklist file
        blacklist_file = config_path / 'blacklist.txt'
        if not blacklist_file.exists():
            default_patterns = [
                '*.tmp',
                '*.swp',
                '*~',
                '*.log',
                '*.pyc',
                '__pycache__',
                '.git/*',
                '*.cache',
                '*.pid'
            ]
            blacklist_file.write_text('\n'.join(default_patterns) + '\n')
            click.echo(f"✓ Blacklist file created at {blacklist_file}")
        
        click.echo("\n✓ Initialization complete!")
        click.echo(f"\nNext steps:")
        click.echo(f"  1. Edit configuration: {config_file}")
        click.echo(f"  2. Start monitoring: sysaudit monitor --config {config_file}")
        
    except Exception as e:
        handle_error(e, verbose=verbose)
        sys.exit(1)


@cli.command()
@click.option('--watch', multiple=True, help='Paths to monitor (can be specified multiple times)')
@click.option('--daemon', is_flag=True, help='Run as daemon in background')
@click.option('--config', 'config_file', help='Path to configuration file')
@click.option('--repo', help='Path to audit repository (overrides config)')
def monitor(watch, daemon, config_file, repo):
    """Start monitoring file system changes
    
    Monitors specified paths for file changes and automatically commits
    them to the Git repository.
    
    Examples:
        sysaudit monitor --config /etc/sysaudit/config.yaml
        sysaudit monitor --watch /etc --watch /usr/local/bin --repo /var/lib/sysaudit
    """
    try:
        # Load configuration
        config = None
        if config_file:
            config = Config.from_yaml(config_file)
            click.echo(f"Loaded configuration from {config_file}")
        else:
            # Create minimal config from CLI arguments
            if not repo:
                click.echo("Error: Either --config or --repo must be specified", err=True)
                sys.exit(1)
            
            watch_paths = list(watch) if watch else [os.getcwd()]
            config = Config(
                repo_path=repo,
                watch_paths=watch_paths,
                baseline_branch='main'
            )
        
        # Override watch paths if specified via CLI
        if watch:
            config.watch_paths = list(watch)
        
        # Override repo if specified via CLI
        if repo:
            config.repo_path = repo
        
        # Validate configuration
        if not config.watch_paths:
            click.echo("Error: No paths to monitor. Specify paths via --watch or config file", err=True)
            sys.exit(1)
        
        if not os.path.exists(config.repo_path):
            click.echo(f"Error: Repository path does not exist: {config.repo_path}", err=True)
            click.echo("Run 'sysaudit init' first to initialize the repository", err=True)
            sys.exit(1)
        
        click.echo(f"Starting file system monitoring...")
        click.echo(f"Repository: {config.repo_path}")
        click.echo(f"Monitoring paths:")
        for path in config.watch_paths:
            click.echo(f"  - {path}")
        
        # Initialize components
        file_monitor = FileMonitor(config)
        git_manager = GitManager(config)
        
        # Create callback for handling file events
        def handle_events(events):
            """Handle file events by committing to Git"""
            if events:
                try:
                    git_manager.commit_changes(events)
                    click.echo(f"Committed {len(events)} file changes")
                except Exception as e:
                    click.echo(f"Error committing changes: {e}", err=True)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            click.echo("\n\nShutting down gracefully...")
            file_monitor.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring
        if daemon:
            click.echo("Running in daemon mode (press Ctrl+C to stop)...")
        else:
            click.echo("Monitoring started (press Ctrl+C to stop)...")
        
        file_monitor.start(handle_events)
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\n\nShutting down...")
            file_monitor.stop()
        
    except Exception as e:
        click.echo(f"✗ Monitoring failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--message', '-m', required=True, help='Snapshot commit message')
@click.option('--config', 'config_file', help='Path to configuration file')
@click.option('--repo', help='Path to audit repository (overrides config)')
@click.option('--paths', multiple=True, help='Specific paths to snapshot (defaults to all monitored paths)')
def snapshot(message, config_file, repo, paths):
    """Create a manual snapshot of current state
    
    Takes a snapshot of the current state of monitored files and creates
    a Git commit with the specified message.
    
    Examples:
        sysaudit snapshot -m "Before system upgrade" --config /etc/sysaudit/config.yaml
        sysaudit snapshot -m "Manual backup" --repo /var/lib/sysaudit --paths /etc
    """
    try:
        # Load configuration
        config = None
        if config_file:
            config = Config.from_yaml(config_file)
            click.echo(f"Loaded configuration from {config_file}")
        else:
            if not repo:
                click.echo("Error: Either --config or --repo must be specified", err=True)
                sys.exit(1)
            
            snapshot_paths = list(paths) if paths else [os.getcwd()]
            config = Config(
                repo_path=repo,
                watch_paths=snapshot_paths,
                baseline_branch='main'
            )
        
        # Override paths if specified
        if paths:
            config.watch_paths = list(paths)
        
        # Override repo if specified
        if repo:
            config.repo_path = repo
        
        if not os.path.exists(config.repo_path):
            click.echo(f"Error: Repository path does not exist: {config.repo_path}", err=True)
            click.echo("Run 'sysaudit init' first to initialize the repository", err=True)
            sys.exit(1)
        
        click.echo(f"Creating snapshot...")
        click.echo(f"Repository: {config.repo_path}")
        click.echo(f"Paths to snapshot:")
        for path in config.watch_paths:
            click.echo(f"  - {path}")
        
        # Initialize Git manager
        git_manager = GitManager(config)
        
        # Copy files to repository
        files_copied = 0
        for watch_path in config.watch_paths:
            if not os.path.exists(watch_path):
                click.echo(f"Warning: Path does not exist: {watch_path}", err=True)
                continue
            
            if os.path.isfile(watch_path):
                # Single file
                rel_path = os.path.abspath(watch_path).lstrip('/')
                dest_path = os.path.join(config.repo_path, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(watch_path, dest_path)
                files_copied += 1
            else:
                # Directory - copy recursively
                for root, dirs, files in os.walk(watch_path):
                    # Skip .git directories
                    dirs[:] = [d for d in dirs if d != '.git']
                    
                    for file in files:
                        src_file = os.path.join(root, file)
                        rel_path = os.path.abspath(src_file).lstrip('/')
                        dest_file = os.path.join(config.repo_path, rel_path)
                        
                        try:
                            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                            shutil.copy2(src_file, dest_file)
                            files_copied += 1
                        except (PermissionError, OSError) as e:
                            click.echo(f"Warning: Could not copy {src_file}: {e}", err=True)
        
        if files_copied == 0:
            click.echo("Warning: No files were copied", err=True)
        
        # Create commit using Git directly
        from datetime import datetime
        repo = git_manager.get_repo()
        if repo:
            # Add all files
            repo.git.add(A=True)
            
            # Create commit
            commit_message = f"Manual snapshot: {message}\n\nTimestamp: {datetime.now().isoformat()}\nFiles: {files_copied}"
            commit = repo.index.commit(commit_message)
            
            click.echo(f"\n✓ Snapshot created successfully!")
            click.echo(f"  Commit: {commit.hexsha[:8]}")
            click.echo(f"  Files: {files_copied}")
            click.echo(f"  Message: {message}")
        else:
            click.echo("✗ Failed to access repository", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"✗ Snapshot failed: {e}", err=True)
        sys.exit(1)


@cli.command('drift-check')
@click.option('--baseline', default='main', help='Baseline branch/commit to compare against (default: main)')
@click.option('--severity', type=click.Choice(['HIGH', 'MEDIUM', 'LOW'], case_sensitive=False), 
              help='Filter by severity level')
@click.option('--config', 'config_file', help='Path to configuration file')
@click.option('--repo', help='Path to audit repository (overrides config)')
def drift_check(baseline, severity, config_file, repo):
    """Check drift from baseline
    
    Compares the current state with a baseline commit/branch to identify
    changes and their severity levels.
    
    Examples:
        sysaudit drift-check --baseline main --config /etc/sysaudit/config.yaml
        sysaudit drift-check --baseline main --severity HIGH --repo /var/lib/sysaudit
    """
    try:
        # Load configuration
        config = None
        if config_file:
            config = Config.from_yaml(config_file)
        else:
            if not repo:
                click.echo("Error: Either --config or --repo must be specified", err=True)
                sys.exit(1)
            # For drift check, watch_paths are not required
            config = Config(repo_path=repo, watch_paths=[repo], baseline_branch=baseline)
        
        # Override repo if specified
        if repo:
            config.repo_path = repo
        
        if not os.path.exists(config.repo_path):
            click.echo(f"Error: Repository path does not exist: {config.repo_path}", err=True)
            sys.exit(1)
        
        click.echo(f"Checking drift from baseline: {baseline}")
        click.echo(f"Repository: {config.repo_path}\n")
        
        # Initialize components
        git_manager = GitManager(config)
        drift_detector = DriftDetector(git_manager)
        
        # Check drift
        report = drift_detector.check_drift(baseline)
        
        # Filter by severity if specified
        changes = report.changes
        if severity:
            changes = [c for c in changes if c.severity.upper() == severity.upper()]
        
        if not changes:
            if severity:
                click.echo(f"✓ No changes with severity {severity} detected")
            else:
                click.echo("✓ No drift detected - system matches baseline")
            return
        
        # Display results
        click.echo(f"Drift Report - {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo("=" * 70)
        
        # Group by severity
        by_severity = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
        for change in changes:
            by_severity[change.severity].append(change)
        
        # Display by severity
        for sev in ['HIGH', 'MEDIUM', 'LOW']:
            if by_severity[sev]:
                # Color coding
                if sev == 'HIGH':
                    color = 'red'
                elif sev == 'MEDIUM':
                    color = 'yellow'
                else:
                    color = 'green'
                
                click.echo(f"\n{sev} Severity ({len(by_severity[sev])} changes):", fg=color, bold=True)
                click.echo("-" * 70)
                
                for change in by_severity[sev]:
                    # Change type symbol
                    if change.change_type == 'added':
                        symbol = '+'
                        type_color = 'green'
                    elif change.change_type == 'deleted':
                        symbol = '-'
                        type_color = 'red'
                    else:
                        symbol = 'M'
                        type_color = 'yellow'
                    
                    click.echo(f"  [{click.style(symbol, fg=type_color)}] {change.path} ({change.change_type})")
        
        # Summary
        click.echo("\n" + "=" * 70)
        click.echo(f"Total changes: {len(changes)}")
        click.echo(f"  HIGH: {len(by_severity['HIGH'])}")
        click.echo(f"  MEDIUM: {len(by_severity['MEDIUM'])}")
        click.echo(f"  LOW: {len(by_severity['LOW'])}")
        
    except Exception as e:
        click.echo(f"✗ Drift check failed: {e}", err=True)
        sys.exit(1)


@cli.command('compliance-report')
@click.option('--format', type=click.Choice(['text', 'html', 'json'], case_sensitive=False),
              default='text', help='Report format (default: text)')
@click.option('--output', '-o', help='Output file (default: stdout)')
@click.option('--config', 'config_file', help='Path to configuration file')
@click.option('--paths', multiple=True, help='Specific paths to check (defaults to config paths)')
def compliance_report(format, output, config_file, paths):
    """Generate compliance report
    
    Scans the system for compliance issues such as world-writable files,
    unexpected SUID/SGID binaries, and weak permissions.
    
    Examples:
        sysaudit compliance-report --config /etc/sysaudit/config.yaml
        sysaudit compliance-report --format json --output report.json --paths /etc
    """
    try:
        # Load configuration
        config = None
        if config_file:
            config = Config.from_yaml(config_file)
            click.echo(f"Loaded configuration from {config_file}")
        else:
            if not paths:
                click.echo("Error: Either --config or --paths must be specified", err=True)
                sys.exit(1)
            config = Config(
                repo_path='/tmp/sysaudit',  # Not used for compliance
                watch_paths=list(paths),
                baseline_branch='main'
            )
        
        # Override paths if specified
        if paths:
            config.watch_paths = list(paths)
        
        if not config.watch_paths:
            click.echo("Error: No paths to check. Specify paths via --paths or config file", err=True)
            sys.exit(1)
        
        click.echo(f"Running compliance checks...")
        click.echo(f"Paths to check:")
        for path in config.watch_paths:
            click.echo(f"  - {path}")
        click.echo()
        
        # Initialize compliance checker
        checker = ComplianceChecker(config)
        
        # Scan all paths
        all_issues = []
        for path in config.watch_paths:
            if not os.path.exists(path):
                click.echo(f"Warning: Path does not exist: {path}", err=True)
                continue
            
            click.echo(f"Scanning {path}...")
            # Get all files in path
            files_to_check = []
            if os.path.isfile(path):
                files_to_check.append(path)
            else:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        files_to_check.append(os.path.join(root, file))
            
            issues = checker.check_files(files_to_check)
            all_issues.extend(issues)
        
        # Create reporter with issues
        reporter = ComplianceReporter(all_issues)
        
        # Generate report
        if format.lower() == 'text':
            report_content = reporter.generate_text_report()
        elif format.lower() == 'html':
            report_content = reporter.generate_html_report()
        elif format.lower() == 'json':
            report_content = reporter.generate_json_report()
        
        # Output report
        if output:
            with open(output, 'w') as f:
                f.write(report_content)
            click.echo(f"\n✓ Report saved to {output}")
        else:
            click.echo("\n" + "=" * 70)
            click.echo(report_content)
        
        # Summary
        if not output:
            click.echo("\n" + "=" * 70)
        
        if all_issues:
            high_count = sum(1 for i in all_issues if i.severity == 'HIGH')
            medium_count = sum(1 for i in all_issues if i.severity == 'MEDIUM')
            low_count = sum(1 for i in all_issues if i.severity == 'LOW')
            
            click.echo(f"\nCompliance Summary:")
            click.echo(f"  Total issues: {len(all_issues)}")
            click.echo(f"  HIGH: {high_count}")
            click.echo(f"  MEDIUM: {medium_count}")
            click.echo(f"  LOW: {low_count}")
            
            if high_count > 0:
                sys.exit(1)  # Exit with error if high severity issues found
        else:
            click.echo("\n✓ No compliance issues found")
        
    except Exception as e:
        click.echo(f"✗ Compliance report failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--to-commit', required=True, help='Target commit hash or reference')
@click.option('--path', 'file_path', required=True, help='File path to rollback')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--config', 'config_file', help='Path to configuration file')
@click.option('--repo', help='Path to audit repository (overrides config)')
def rollback(to_commit, file_path, dry_run, config_file, repo):
    """Rollback file to previous version
    
    Restores a file to its state at a specific commit. Creates a backup
    of the current version before rolling back.
    
    Examples:
        sysaudit rollback --to-commit abc123 --path /etc/config.conf --repo /var/lib/sysaudit
        sysaudit rollback --to-commit HEAD~5 --path /etc/ssh/sshd_config --dry-run --config /etc/sysaudit/config.yaml
    """
    try:
        # Load configuration
        config = None
        if config_file:
            config = Config.from_yaml(config_file)
        else:
            if not repo:
                click.echo("Error: Either --config or --repo must be specified", err=True)
                sys.exit(1)
            # Use a dummy watch path for rollback (not actually used)
            config = Config(repo_path=repo, watch_paths=['/tmp'], baseline_branch='main')
        
        # Override repo if specified
        if repo:
            config.repo_path = repo
        
        if not os.path.exists(config.repo_path):
            click.echo(f"Error: Repository path does not exist: {config.repo_path}", err=True)
            sys.exit(1)
        
        if dry_run:
            click.echo("DRY RUN MODE - No changes will be made\n")
        
        click.echo(f"Rollback operation:")
        click.echo(f"  Repository: {config.repo_path}")
        click.echo(f"  Target commit: {to_commit}")
        click.echo(f"  File path: {file_path}")
        click.echo()
        
        # Initialize components
        rollback_manager = RollbackManager(config.repo_path)
        
        # Perform rollback
        result = rollback_manager.rollback_file(file_path, to_commit, dry_run=dry_run)
        
        if dry_run:
            click.echo(f"\n✓ Dry run completed")
            click.echo(f"  Would rollback: {file_path}")
            click.echo(f"  To commit: {to_commit}")
            if result and 'backup_path' in result:
                click.echo(f"  Would create backup at: {result['backup_path']}")
        else:
            click.echo(f"\n✓ Rollback completed successfully!")
            click.echo(f"  File restored: {file_path}")
            click.echo(f"  From commit: {to_commit}")
            if result and 'backup_path' in result:
                click.echo(f"  Backup created: {result['backup_path']}")
        
    except ValueError as e:
        click.echo(f"✗ Rollback failed: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Rollback failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def examples():
    """Show usage examples
    
    Displays common usage patterns and workflows for the audit system.
    """
    examples_text = """
Common Usage Examples
=====================

1. Initialize the audit system:
   $ sysaudit init --repo /var/lib/sysaudit --baseline main

2. Start monitoring with configuration file:
   $ sysaudit monitor --config /etc/sysaudit/config.yaml

3. Start monitoring specific paths:
   $ sysaudit monitor --watch /etc --watch /usr/local/bin --repo /var/lib/sysaudit

4. Create a manual snapshot:
   $ sysaudit snapshot -m "Before system upgrade" --config /etc/sysaudit/config.yaml

5. Check drift from baseline:
   $ sysaudit drift-check --baseline main --repo /var/lib/sysaudit

6. Check drift with severity filter:
   $ sysaudit drift-check --baseline main --severity HIGH --repo /var/lib/sysaudit

7. Generate compliance report:
   $ sysaudit compliance-report --config /etc/sysaudit/config.yaml

8. Generate compliance report in JSON format:
   $ sysaudit compliance-report --format json --output report.json --paths /etc

9. Rollback a file (dry run):
   $ sysaudit rollback --to-commit abc123 --path /etc/config.conf --dry-run --repo /var/lib/sysaudit

10. Rollback a file:
    $ sysaudit rollback --to-commit HEAD~5 --path /etc/ssh/sshd_config --repo /var/lib/sysaudit

Typical Workflow
================

1. Initialize:
   $ sudo sysaudit init --repo /var/lib/sysaudit

2. Edit configuration:
   $ sudo nano /etc/sysaudit/config.yaml

3. Start monitoring as a service:
   $ sudo systemctl start sysaudit

4. Check for drift periodically:
   $ sudo sysaudit drift-check --baseline main --config /etc/sysaudit/config.yaml

5. Run compliance checks:
   $ sudo sysaudit compliance-report --config /etc/sysaudit/config.yaml

For more information, use --help with any command:
   $ sysaudit <command> --help
"""
    click.echo(examples_text)


def main():
    """Main entry point for the CLI"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled by user", err=True)
        sys.exit(130)
    except Exception as e:
        # Check if verbose mode is enabled via environment variable
        verbose = os.environ.get('SYSAUDIT_VERBOSE', '').lower() in ('1', 'true', 'yes')
        handle_error(e, verbose=verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()
