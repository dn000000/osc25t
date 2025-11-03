#!/usr/bin/env python3
"""
Example usage of the sysaudit CLI interface

This script demonstrates how to use the various CLI commands programmatically
or shows the equivalent shell commands.
"""

import subprocess
import tempfile
import os
from pathlib import Path


def run_command(cmd):
    """Run a shell command and print output"""
    print(f"\n$ {cmd}")
    print("-" * 70)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print(f"Exit code: {result.returncode}")
    return result


def main():
    """Demonstrate CLI usage"""
    
    print("=" * 70)
    print("SysAudit CLI Usage Examples")
    print("=" * 70)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = os.path.join(tmpdir, "audit_repo")
        watch_path = os.path.join(tmpdir, "watch")
        config_path = os.path.join(tmpdir, "config.yaml")
        
        os.makedirs(watch_path, exist_ok=True)
        
        print("\n1. Show help")
        run_command("python -m sysaudit.cli --help")
        
        print("\n2. Show examples")
        run_command("python -m sysaudit.cli examples")
        
        print("\n3. Initialize repository")
        run_command(f"python -m sysaudit.cli init --repo {repo_path} --baseline main")
        
        print("\n4. Create test files to monitor")
        test_file = os.path.join(watch_path, "test.conf")
        Path(test_file).write_text("initial content\n")
        print(f"Created test file: {test_file}")
        
        print("\n5. Create manual snapshot")
        run_command(
            f"python -m sysaudit.cli snapshot "
            f"-m 'Initial snapshot' --repo {repo_path} --paths {watch_path}"
        )
        
        print("\n6. Check drift (should show no changes)")
        run_command(f"python -m sysaudit.cli drift-check --baseline main --repo {repo_path}")
        
        print("\n7. Modify test file")
        Path(test_file).write_text("modified content\n")
        print(f"Modified test file: {test_file}")
        
        print("\n8. Create another snapshot")
        run_command(
            f"python -m sysaudit.cli snapshot "
            f"-m 'After modification' --repo {repo_path} --paths {watch_path}"
        )
        
        print("\n9. Check drift (should show changes)")
        run_command(f"python -m sysaudit.cli drift-check --baseline main --repo {repo_path}")
        
        print("\n10. Run compliance report")
        run_command(f"python -m sysaudit.cli compliance-report --paths {watch_path}")
        
        print("\n11. Show rollback help")
        run_command("python -m sysaudit.cli rollback --help")
        
        print("\n" + "=" * 70)
        print("Demo completed!")
        print("=" * 70)


if __name__ == "__main__":
    main()
