#!/usr/bin/env python3
"""
Example usage of FilterManager with Config integration.

This demonstrates how the FilterManager is used in the audit system
to filter file system events based on blacklist/whitelist patterns.
"""

from sysaudit.monitor.filter import FilterManager
from sysaudit.models import Config

# Example 1: Using FilterManager with default patterns only
print("Example 1: Default patterns only")
print("-" * 50)
filter_mgr = FilterManager()

test_paths = [
    '/etc/config.conf',
    '/tmp/test.tmp',
    '/var/log/system.log',
    '/etc/ssh/sshd_config',
    '/home/user/.git/config',
    '/home/user/script.py',
]

for path in test_paths:
    ignored = filter_mgr.should_ignore(path)
    status = "IGNORED" if ignored else "MONITORED"
    print(f"{status:10} {path}")

print()

# Example 2: Using FilterManager with Config object
print("Example 2: Integration with Config")
print("-" * 50)

# Create a config with blacklist file
config = Config(
    repo_path='/var/lib/sysaudit',
    watch_paths=['/etc', '/usr/local/bin'],
    blacklist_file='examples/blacklist.txt',  # Uses the example blacklist
    whitelist_file=None
)

# Initialize FilterManager from config
filter_mgr = FilterManager(
    blacklist_file=config.blacklist_file,
    whitelist_file=config.whitelist_file,
    use_defaults=True
)

print(f"Loaded {len(filter_mgr.get_blacklist_patterns())} blacklist patterns")
print(f"Loaded {len(filter_mgr.get_whitelist_patterns())} whitelist patterns")
print()

# Example 3: Using whitelist to restrict monitoring
print("Example 3: Whitelist restricts to specific files")
print("-" * 50)

filter_mgr_whitelist = FilterManager(use_defaults=False)
filter_mgr_whitelist.add_whitelist_pattern('*.conf')
filter_mgr_whitelist.add_whitelist_pattern('*.yaml')

test_paths_2 = [
    '/etc/app.conf',
    '/etc/config.yaml',
    '/etc/script.py',
    '/etc/data.json',
]

for path in test_paths_2:
    ignored = filter_mgr_whitelist.should_ignore(path)
    status = "IGNORED" if ignored else "MONITORED"
    print(f"{status:10} {path}")

print()

# Example 4: Dynamic pattern management
print("Example 4: Adding patterns at runtime")
print("-" * 50)

filter_mgr_dynamic = FilterManager(use_defaults=False)

# Add some custom patterns
filter_mgr_dynamic.add_blacklist_pattern('*.secret')
filter_mgr_dynamic.add_blacklist_pattern('*.key')
filter_mgr_dynamic.add_blacklist_pattern('passwords/*')

test_paths_3 = [
    '/etc/app.secret',
    '/home/user/private.key',
    'passwords/admin.txt',
    '/etc/config.conf',
]

for path in test_paths_3:
    ignored = filter_mgr_dynamic.should_ignore(path)
    status = "IGNORED" if ignored else "MONITORED"
    print(f"{status:10} {path}")

print()
print("Current blacklist patterns:")
for pattern in filter_mgr_dynamic.get_blacklist_patterns():
    print(f"  - {pattern}")
