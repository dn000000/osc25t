"""Compliance report generation"""

import json
from typing import List, Optional
from datetime import datetime
from sysaudit.models import ComplianceIssue


class ComplianceReporter:
    """Generates compliance reports in various formats"""
    
    def __init__(self, issues: List[ComplianceIssue]):
        """
        Initialize reporter with compliance issues
        
        Args:
            issues: List of compliance issues to report
        """
        self.issues = issues
        self.timestamp = datetime.now()
    
    def generate_text_report(self) -> str:
        """
        Generate a text format report
        
        Returns:
            Report as plain text string
        """
        if not self.issues:
            return "No compliance issues found.\n"
        
        lines = []
        lines.append("=" * 80)
        lines.append("COMPLIANCE REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {self.timestamp.isoformat()}")
        lines.append(f"Total Issues: {len(self.issues)}")
        lines.append("")
        
        # Group by severity
        high = [i for i in self.issues if i.severity == 'HIGH']
        medium = [i for i in self.issues if i.severity == 'MEDIUM']
        low = [i for i in self.issues if i.severity == 'LOW']
        
        lines.append(f"HIGH:   {len(high)}")
        lines.append(f"MEDIUM: {len(medium)}")
        lines.append(f"LOW:    {len(low)}")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        
        # Report issues by severity
        for severity_name, severity_issues in [('HIGH', high), ('MEDIUM', medium), ('LOW', low)]:
            if not severity_issues:
                continue
            
            lines.append(f"{severity_name} SEVERITY ISSUES ({len(severity_issues)})")
            lines.append("-" * 80)
            lines.append("")
            
            for i, issue in enumerate(severity_issues, 1):
                lines.append(f"Issue #{i}")
                lines.append(f"  Rule:           {issue.rule}")
                lines.append(f"  Path:           {issue.path}")
                lines.append(f"  Description:    {issue.description}")
                lines.append(f"  Recommendation: {issue.recommendation}")
                lines.append(f"  Detected:       {issue.timestamp.isoformat()}")
                lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> str:
        """
        Generate a JSON format report
        
        Returns:
            Report as JSON string
        """
        report = {
            "generated": self.timestamp.isoformat(),
            "total_issues": len(self.issues),
            "summary": {
                "high": len([i for i in self.issues if i.severity == 'HIGH']),
                "medium": len([i for i in self.issues if i.severity == 'MEDIUM']),
                "low": len([i for i in self.issues if i.severity == 'LOW']),
            },
            "issues": [
                {
                    "severity": issue.severity,
                    "rule": issue.rule,
                    "path": issue.path,
                    "description": issue.description,
                    "recommendation": issue.recommendation,
                    "timestamp": issue.timestamp.isoformat(),
                }
                for issue in self.issues
            ]
        }
        
        return json.dumps(report, indent=2)
    
    def generate_html_report(self) -> str:
        """
        Generate an HTML format report
        
        Returns:
            Report as HTML string
        """
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html>")
        html.append("<head>")
        html.append("  <meta charset='UTF-8'>")
        html.append("  <title>Compliance Report</title>")
        html.append("  <style>")
        html.append("    body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }")
        html.append("    .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }")
        html.append("    h1 { color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }")
        html.append("    h2 { color: #555; margin-top: 30px; }")
        html.append("    .summary { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }")
        html.append("    .summary-item { display: inline-block; margin-right: 30px; }")
        html.append("    .issue { border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }")
        html.append("    .issue-high { border-left: 5px solid #dc3545; background-color: #fff5f5; }")
        html.append("    .issue-medium { border-left: 5px solid #ffc107; background-color: #fffef5; }")
        html.append("    .issue-low { border-left: 5px solid #28a745; background-color: #f5fff5; }")
        html.append("    .severity { font-weight: bold; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; }")
        html.append("    .severity-high { background-color: #dc3545; color: white; }")
        html.append("    .severity-medium { background-color: #ffc107; color: black; }")
        html.append("    .severity-low { background-color: #28a745; color: white; }")
        html.append("    .field { margin: 8px 0; }")
        html.append("    .field-label { font-weight: bold; color: #666; }")
        html.append("    .field-value { color: #333; }")
        html.append("    .path { font-family: monospace; background-color: #f8f9fa; padding: 2px 5px; border-radius: 3px; }")
        html.append("    .recommendation { background-color: #e7f3ff; padding: 10px; border-radius: 3px; margin-top: 10px; }")
        html.append("    .timestamp { color: #999; font-size: 0.9em; }")
        html.append("  </style>")
        html.append("</head>")
        html.append("<body>")
        html.append("  <div class='container'>")
        html.append("    <h1>Compliance Report</h1>")
        html.append(f"    <p class='timestamp'>Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>")
        
        # Summary
        high = [i for i in self.issues if i.severity == 'HIGH']
        medium = [i for i in self.issues if i.severity == 'MEDIUM']
        low = [i for i in self.issues if i.severity == 'LOW']
        
        html.append("    <div class='summary'>")
        html.append(f"      <div class='summary-item'><strong>Total Issues:</strong> {len(self.issues)}</div>")
        html.append(f"      <div class='summary-item'><span class='severity severity-high'>HIGH</span> {len(high)}</div>")
        html.append(f"      <div class='summary-item'><span class='severity severity-medium'>MEDIUM</span> {len(medium)}</div>")
        html.append(f"      <div class='summary-item'><span class='severity severity-low'>LOW</span> {len(low)}</div>")
        html.append("    </div>")
        
        if not self.issues:
            html.append("    <p>No compliance issues found.</p>")
        else:
            # Report issues by severity
            for severity_name, severity_issues, css_class in [
                ('HIGH', high, 'issue-high'),
                ('MEDIUM', medium, 'issue-medium'),
                ('LOW', low, 'issue-low')
            ]:
                if not severity_issues:
                    continue
                
                html.append(f"    <h2>{severity_name} Severity Issues ({len(severity_issues)})</h2>")
                
                for issue in severity_issues:
                    html.append(f"    <div class='issue {css_class}'>")
                    html.append(f"      <div class='field'>")
                    html.append(f"        <span class='severity severity-{severity_name.lower()}'>{issue.severity}</span>")
                    html.append(f"      </div>")
                    html.append(f"      <div class='field'>")
                    html.append(f"        <span class='field-label'>Rule:</span> ")
                    html.append(f"        <span class='field-value'>{issue.rule}</span>")
                    html.append(f"      </div>")
                    html.append(f"      <div class='field'>")
                    html.append(f"        <span class='field-label'>Path:</span> ")
                    html.append(f"        <span class='path'>{issue.path}</span>")
                    html.append(f"      </div>")
                    html.append(f"      <div class='field'>")
                    html.append(f"        <span class='field-label'>Description:</span> ")
                    html.append(f"        <span class='field-value'>{issue.description}</span>")
                    html.append(f"      </div>")
                    html.append(f"      <div class='recommendation'>")
                    html.append(f"        <strong>Recommendation:</strong> {issue.recommendation}")
                    html.append(f"      </div>")
                    html.append(f"      <div class='timestamp'>Detected: {issue.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</div>")
                    html.append(f"    </div>")
        
        html.append("  </div>")
        html.append("</body>")
        html.append("</html>")
        
        return "\n".join(html)
    
    def generate_report(self, format: str = 'text') -> str:
        """
        Generate report in specified format
        
        Args:
            format: Report format ('text', 'json', or 'html')
            
        Returns:
            Report as string
            
        Raises:
            ValueError: If format is not supported
        """
        format = format.lower()
        
        if format == 'text':
            return self.generate_text_report()
        elif format == 'json':
            return self.generate_json_report()
        elif format == 'html':
            return self.generate_html_report()
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'text', 'json', or 'html'")
    
    def save_report(self, output_path: str, format: str = 'text'):
        """
        Generate and save report to file
        
        Args:
            output_path: Path to save the report
            format: Report format ('text', 'json', or 'html')
        """
        report = self.generate_report(format)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
    
    def print_report(self, format: str = 'text'):
        """
        Generate and print report to stdout
        
        Args:
            format: Report format ('text', 'json', or 'html')
        """
        report = self.generate_report(format)
        print(report)
