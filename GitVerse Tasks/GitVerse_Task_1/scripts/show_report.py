#!/usr/bin/env python3
"""Show test report"""

import json
import sys
from pathlib import Path

def main():
    results_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "test-results")
    report_file = results_dir / "final-report.json"
    
    if not report_file.exists():
        print("Report not found")
        return
    
    with open(report_file) as f:
        report = json.load(f)
    
    print('\n' + '='*60)
    print('FINAL REPORT')
    print('='*60)
    print('Project: {}'.format(report["project"]))
    print('Version: {}'.format(report["version"]))
    if report.get("timestamp"):
        print('Time: {}'.format(report["timestamp"]))
    print('\nSummary:')
    print('  Total tests: {}'.format(report["summary"]["total_tests"]))
    print('  Passed: {}'.format(report["summary"]["passed"]))
    print('  Failed: {}'.format(report["summary"]["failed"]))
    print('  Success Rate: {}'.format(report["summary"]["success_rate"]))
    
    if report['tests']:
        print('\nResults by type:')
        for test_type, data in report['tests'].items():
            if isinstance(data, dict):
                print('\n  {}:'.format(test_type.upper()))
                print('    Passed: {}'.format(data.get("passed", "N/A")))
                print('    Failed: {}'.format(data.get("failed", "N/A")))
                if 'duration_seconds' in data:
                    print('    Duration: {:.2f}s'.format(data["duration_seconds"]))
    print('='*60)

if __name__ == "__main__":
    main()
