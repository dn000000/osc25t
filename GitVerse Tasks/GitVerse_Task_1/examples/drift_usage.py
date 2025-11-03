"""
Example usage of drift detection functionality.

This example demonstrates how to:
1. Initialize a Git repository for audit tracking
2. Create a baseline
3. Make changes to files
4. Detect drift from the baseline
5. Use severity scoring to prioritize changes
"""

import tempfile
import shutil
from pathlib import Path

from sysaudit.models import Config
from sysaudit.git import GitManager, DriftDetector, SeverityScorer


def main():
    # Create temporary directories for demonstration
    repo_dir = tempfile.mkdtemp(prefix='audit_repo_')
    watch_dir = tempfile.mkdtemp(prefix='watch_dir_')
    
    print(f"Repository directory: {repo_dir}")
    print(f"Watch directory: {watch_dir}")
    print()
    
    try:
        # 1. Initialize configuration
        config = Config(
            repo_path=repo_dir,
            watch_paths=[watch_dir],
            baseline_branch='baseline'
        )
        
        # 2. Initialize Git manager and repository
        print("Initializing Git repository...")
        git_manager = GitManager(config)
        git_manager.init_repo()
        print("✓ Repository initialized")
        print()
        
        # 3. Create some initial files and establish baseline
        print("Creating baseline files...")
        
        # Create critical system files
        etc_dir = Path(repo_dir) / 'etc'
        etc_dir.mkdir(exist_ok=True)
        
        (etc_dir / 'hostname').write_text('myserver')
        (etc_dir / 'hosts').write_text('127.0.0.1 localhost\n')
        
        # Create user files
        home_dir = Path(repo_dir) / 'home' / 'user'
        home_dir.mkdir(parents=True, exist_ok=True)
        (home_dir / 'config.txt').write_text('user config')
        
        # Commit baseline
        git_manager.repo.index.add(['etc/hostname', 'etc/hosts', 'home/user/config.txt'])
        baseline_commit = git_manager.repo.index.commit('Baseline commit')
        
        # Create baseline branch pointing to this commit
        baseline_branch = git_manager.repo.create_head('baseline', baseline_commit)
        print("✓ Baseline established")
        print()
        
        # 4. Make some changes
        print("Making changes to files...")
        
        # Create a working branch for changes
        working_branch = git_manager.repo.create_head('working', baseline_commit)
        working_branch.checkout()
        
        # Modify a critical file
        (etc_dir / 'hostname').write_text('myserver-renamed')
        git_manager.repo.index.add(['etc/hostname'])
        git_manager.repo.index.commit('Change hostname')
        print("  - Modified: /etc/hostname")
        
        # Add a new critical file
        (etc_dir / 'sudoers').write_text('root ALL=(ALL:ALL) ALL\n')
        git_manager.repo.index.add(['etc/sudoers'])
        git_manager.repo.index.commit('Add sudoers')
        print("  - Added: /etc/sudoers")
        
        # Add a user file
        (home_dir / 'notes.txt').write_text('my notes')
        git_manager.repo.index.add(['home/user/notes.txt'])
        git_manager.repo.index.commit('Add user notes')
        print("  - Added: /home/user/notes.txt")
        
        # Delete a file
        (etc_dir / 'hosts').unlink()
        git_manager.repo.index.remove(['etc/hosts'])
        git_manager.repo.index.commit('Remove hosts file')
        print("  - Deleted: /etc/hosts")
        print()
        
        # 5. Detect drift from baseline
        print("Detecting drift from baseline...")
        drift_detector = DriftDetector(git_manager)
        report = drift_detector.check_drift('baseline')
        
        print(f"✓ Drift report generated at {report.timestamp}")
        print(f"  Total changes: {len(report.changes)}")
        print()
        
        # 6. Display changes grouped by severity
        print("Changes by severity:")
        print("-" * 60)
        
        # Group changes by severity
        high_changes = [c for c in report.changes if c.severity == 'HIGH']
        medium_changes = [c for c in report.changes if c.severity == 'MEDIUM']
        low_changes = [c for c in report.changes if c.severity == 'LOW']
        
        if high_changes:
            print("\n🔴 HIGH SEVERITY:")
            for change in high_changes:
                print(f"  [{change.change_type.upper()}] {change.path}")
        
        if medium_changes:
            print("\n🟡 MEDIUM SEVERITY:")
            for change in medium_changes:
                print(f"  [{change.change_type.upper()}] {change.path}")
        
        if low_changes:
            print("\n🟢 LOW SEVERITY:")
            for change in low_changes:
                print(f"  [{change.change_type.upper()}] {change.path}")
        
        print()
        
        # 7. Demonstrate severity scorer directly
        print("Severity scoring examples:")
        print("-" * 60)
        
        scorer = SeverityScorer()
        
        test_paths = [
            '/etc/shadow',
            '/etc/ssh/sshd_config',
            '/etc/hostname',
            '/usr/bin/python',
            '/home/user/document.txt',
            '/var/log/app.log',
        ]
        
        for path in test_paths:
            severity = scorer.score(path)
            explanation = scorer.get_pattern_explanation(path)
            print(f"{severity:6} - {path}")
            print(f"         {explanation}")
            print()
        
        # 8. Demonstrate custom severity patterns
        print("Custom severity patterns:")
        print("-" * 60)
        
        scorer.add_custom_pattern('/myapp/*', 'HIGH')
        scorer.add_custom_pattern('/data/critical/*', 'HIGH')
        
        custom_paths = [
            '/myapp/config.conf',
            '/data/critical/database.db',
            '/data/normal/file.txt',
        ]
        
        for path in custom_paths:
            severity = scorer.score(path)
            print(f"{severity:6} - {path}")
        
        print()
        
        # 9. Get file history
        print("File history for /etc/hostname:")
        print("-" * 60)
        
        history = drift_detector.get_file_history('etc/hostname', max_count=5)
        for i, commit_info in enumerate(history, 1):
            print(f"{i}. {commit_info['summary']}")
            print(f"   SHA: {commit_info['sha'][:8]}")
            print(f"   Time: {commit_info['timestamp']}")
            print()
        
        # 10. Compare specific file with baseline
        print("Comparing /etc/hostname with baseline:")
        print("-" * 60)
        
        comparison = drift_detector.compare_with_baseline('etc/hostname', 'baseline')
        print(f"Change type: {comparison['change_type']}")
        print(f"Baseline content: {comparison['baseline_content']}")
        print(f"Current content: {comparison['current_content']}")
        print()
        
        # 11. Filter high severity changes
        print("High severity changes only:")
        print("-" * 60)
        
        high_severity_report = report.get_high_severity_changes()
        for change in high_severity_report:
            print(f"  [{change.change_type.upper()}] {change.path}")
        
        print()
        print("✓ Drift detection demonstration complete!")
        
    finally:
        # Cleanup
        print("\nCleaning up temporary directories...")
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(watch_dir, ignore_errors=True)
        print("✓ Cleanup complete")


if __name__ == '__main__':
    main()
