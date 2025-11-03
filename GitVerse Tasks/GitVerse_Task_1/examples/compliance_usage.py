"""Example usage of compliance checking system"""

import os
import tempfile
import stat
from pathlib import Path
from sysaudit.models import Config
from sysaudit.compliance import ComplianceChecker, ComplianceReporter


def main():
    """Demonstrate compliance checking functionality"""
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Testing compliance checking in: {tmpdir}\n")
        
        # Create test files with various permission issues
        test_files = []
        
        # 1. Create a world-writable file in /etc (simulated)
        etc_dir = os.path.join(tmpdir, 'etc')
        os.makedirs(etc_dir, exist_ok=True)
        world_writable = os.path.join(etc_dir, 'test_config')
        Path(world_writable).touch()
        os.chmod(world_writable, 0o666)  # World-writable
        test_files.append(world_writable)
        print(f"Created world-writable file: {world_writable}")
        
        # 2. Create a SUID binary in unexpected location
        bin_dir = os.path.join(tmpdir, 'bin')
        os.makedirs(bin_dir, exist_ok=True)
        suid_file = os.path.join(bin_dir, 'suspicious_binary')
        Path(suid_file).touch()
        os.chmod(suid_file, 0o4755)  # SUID bit set
        test_files.append(suid_file)
        print(f"Created SUID binary: {suid_file}")
        
        # 3. Create SSH key with weak permissions
        ssh_dir = os.path.join(tmpdir, '.ssh')
        os.makedirs(ssh_dir, exist_ok=True)
        weak_key = os.path.join(ssh_dir, 'id_rsa')
        Path(weak_key).write_text("fake private key")
        os.chmod(weak_key, 0o644)  # Too permissive for private key
        test_files.append(weak_key)
        print(f"Created SSH key with weak permissions: {weak_key}")
        
        print("\n" + "=" * 80)
        print("RUNNING COMPLIANCE CHECKS")
        print("=" * 80 + "\n")
        
        # Create configuration
        config = Config(
            repo_path=os.path.join(tmpdir, 'repo'),
            watch_paths=[tmpdir]
        )
        
        # Initialize compliance checker
        checker = ComplianceChecker(config)
        
        # List available rules
        print("Available compliance rules:")
        for rule_name in checker.list_rules():
            rule = checker.get_rule_by_name(rule_name)
            print(f"  - {rule_name}: {rule.description}")
        print()
        
        # Check specific files
        print("Checking test files...")
        issues = checker.check_files(test_files)
        
        print(f"Found {len(issues)} compliance issues\n")
        
        # Generate reports in different formats
        reporter = ComplianceReporter(issues)
        
        # Text report
        print("=" * 80)
        print("TEXT REPORT")
        print("=" * 80)
        text_report = reporter.generate_text_report()
        print(text_report)
        
        # Save JSON report
        json_file = os.path.join(tmpdir, 'compliance_report.json')
        reporter.save_report(json_file, format='json')
        print(f"\nJSON report saved to: {json_file}")
        
        # Save HTML report
        html_file = os.path.join(tmpdir, 'compliance_report.html')
        reporter.save_report(html_file, format='html')
        print(f"HTML report saved to: {html_file}")
        
        # Demonstrate directory scanning
        print("\n" + "=" * 80)
        print("SCANNING ENTIRE DIRECTORY")
        print("=" * 80 + "\n")
        
        all_issues = checker.check_directory(tmpdir, recursive=True)
        print(f"Found {len(all_issues)} total issues in directory scan")
        
        # Show summary by severity
        high = [i for i in all_issues if i.severity == 'HIGH']
        medium = [i for i in all_issues if i.severity == 'MEDIUM']
        low = [i for i in all_issues if i.severity == 'LOW']
        
        print(f"  HIGH:   {len(high)}")
        print(f"  MEDIUM: {len(medium)}")
        print(f"  LOW:    {len(low)}")


if __name__ == '__main__':
    main()
