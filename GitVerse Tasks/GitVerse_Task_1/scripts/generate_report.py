#!/usr/bin/env python3
"""Generate test report from JSON files"""

import json
import sys
from pathlib import Path

def main():
    results_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "test-results")
    
    report = {
        "timestamp": "",
        "project": "sysaudit",
        "version": "0.1.0",
        "tests": {}
    }
    
    # Collect results
    for json_file in results_dir.glob("*.json"):
        if json_file.name == "final-report.json":
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)
                test_type = json_file.stem.replace("-report", "")
                report["tests"][test_type] = data
                if "timestamp" in data:
                    report["timestamp"] = data["timestamp"]
        except Exception as e:
            print('Error reading {}: {}'.format(json_file, e))
    
    # Calculate statistics
    total_passed = sum(t.get("passed", 0) for t in report["tests"].values() if isinstance(t, dict))
    total_failed = sum(t.get("failed", 0) for t in report["tests"].values() if isinstance(t, dict))
    total_tests = total_passed + total_failed
    
    if total_tests > 0:
        success_rate = '{:.1f}%'.format((total_passed / total_tests * 100))
    else:
        success_rate = 'N/A'
    
    report["summary"] = {
        "total_tests": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "success_rate": success_rate
    }
    
    # Save report
    with open(results_dir / "final-report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print('Report saved: {}/final-report.json'.format(results_dir))

if __name__ == "__main__":
    main()
