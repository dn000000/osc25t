"""
Command-line interface for GitProc.
Provides commands for managing services and interacting with the daemon.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from gitproc.config import Config
from gitproc.daemon import Daemon


class DaemonClient:
    """
    Client for communicating with the GitProc daemon via Unix socket.
    """
    
    def __init__(self, socket_path: str):
        """
        Initialize the daemon client.
        
        Args:
            socket_path: Path to the Unix socket
        """
        self.socket_path = socket_path
    
    def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a command to the daemon and receive response.
        
        Args:
            command: Command dictionary to send
            
        Returns:
            Response dictionary from daemon
            
        Raises:
            ConnectionError: If unable to connect to daemon
            RuntimeError: If communication fails
        """
        try:
            # Create Unix socket
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            
            try:
                # Connect to daemon
                client_socket.connect(self.socket_path)
                
                # Send JSON-encoded command
                command_json = json.dumps(command)
                client_socket.sendall(command_json.encode('utf-8'))
                
                # Receive response
                response_data = b""
                while True:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    
                    # Try to parse JSON to see if we have complete message
                    try:
                        response = json.loads(response_data.decode('utf-8'))
                        return response
                    except json.JSONDecodeError:
                        # Not complete yet, continue receiving
                        continue
                
                # If we get here, connection closed without complete JSON
                if response_data:
                    raise RuntimeError("Incomplete response from daemon")
                else:
                    raise RuntimeError("No response from daemon")
                    
            finally:
                client_socket.close()
                
        except FileNotFoundError:
            raise ConnectionError(
                f"Daemon socket not found at {self.socket_path}. "
                "Is the daemon running? Try 'gitproc daemon' to start it."
            )
        except ConnectionRefusedError:
            raise ConnectionError(
                f"Connection refused to {self.socket_path}. "
                "Is the daemon running? Try 'gitproc daemon' to start it."
            )
        except socket.error as e:
            raise ConnectionError(f"Socket error: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from daemon: {e}")


class CLI:
    """
    Command-line interface for GitProc service manager.
    """
    
    def __init__(self):
        """Initialize the CLI with argument parser."""
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create and configure the argument parser.
        
        Returns:
            Configured ArgumentParser instance
        """
        parser = argparse.ArgumentParser(
            prog='gitproc',
            description='Git-backed Process Manager - systemd-like service manager with Git integration',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        # Create subparsers for commands
        subparsers = parser.add_subparsers(
            dest='command',
            help='Available commands',
            required=True
        )
        
        # init command
        init_parser = subparsers.add_parser(
            'init',
            help='Initialize a new Git repository for service management'
        )
        init_parser.add_argument(
            '--repo',
            default='/etc/gitproc/services',
            help='Path to Git repository (default: /etc/gitproc/services)'
        )
        init_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # daemon command
        daemon_parser = subparsers.add_parser(
            'daemon',
            help='Start the daemon process'
        )
        daemon_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        daemon_parser.add_argument(
            '--branch',
            default='main',
            help='Git branch to watch (default: main)'
        )
        
        # start command
        start_parser = subparsers.add_parser(
            'start',
            help='Start a service'
        )
        start_parser.add_argument(
            'service',
            help='Name of the service to start'
        )
        start_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # stop command
        stop_parser = subparsers.add_parser(
            'stop',
            help='Stop a service'
        )
        stop_parser.add_argument(
            'service',
            help='Name of the service to stop'
        )
        stop_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # restart command
        restart_parser = subparsers.add_parser(
            'restart',
            help='Restart a service'
        )
        restart_parser.add_argument(
            'service',
            help='Name of the service to restart'
        )
        restart_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # status command
        status_parser = subparsers.add_parser(
            'status',
            help='Show status of a service'
        )
        status_parser.add_argument(
            'service',
            help='Name of the service'
        )
        status_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # logs command
        logs_parser = subparsers.add_parser(
            'logs',
            help='View service logs'
        )
        logs_parser.add_argument(
            'service',
            help='Name of the service'
        )
        logs_parser.add_argument(
            '--follow', '-f',
            action='store_true',
            help='Follow log output in real-time'
        )
        logs_parser.add_argument(
            '--lines', '-n',
            type=int,
            help='Number of lines to display'
        )
        logs_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # list command
        list_parser = subparsers.add_parser(
            'list',
            help='List all services'
        )
        list_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # rollback command
        rollback_parser = subparsers.add_parser(
            'rollback',
            help='Rollback to a previous Git commit'
        )
        rollback_parser.add_argument(
            'commit',
            help='Git commit hash to rollback to'
        )
        rollback_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        # sync command
        sync_parser = subparsers.add_parser(
            'sync',
            help='Manually trigger Git synchronization'
        )
        sync_parser.add_argument(
            '--config',
            default='~/.gitproc/config.json',
            help='Path to configuration file (default: ~/.gitproc/config.json)'
        )
        
        return parser
    
    def execute(self, args: Optional[list] = None) -> int:
        """
        Execute the CLI with the given arguments.
        
        Args:
            args: Command-line arguments (defaults to sys.argv[1:])
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Parse arguments
            parsed_args = self.parser.parse_args(args)
            
            # Route to appropriate command handler
            command = parsed_args.command
            
            if command == 'init':
                return self._cmd_init(parsed_args)
            elif command == 'daemon':
                return self._cmd_daemon(parsed_args)
            elif command == 'start':
                return self._cmd_start(parsed_args)
            elif command == 'stop':
                return self._cmd_stop(parsed_args)
            elif command == 'restart':
                return self._cmd_restart(parsed_args)
            elif command == 'status':
                return self._cmd_status(parsed_args)
            elif command == 'logs':
                return self._cmd_logs(parsed_args)
            elif command == 'list':
                return self._cmd_list(parsed_args)
            elif command == 'rollback':
                return self._cmd_rollback(parsed_args)
            elif command == 'sync':
                return self._cmd_sync(parsed_args)
            else:
                print(f"Unknown command: {command}", file=sys.stderr)
                return 1
            
        except SystemExit as e:
            # argparse calls sys.exit() on error or --help
            return e.code if e.code is not None else 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_init(self, args) -> int:
        """
        Handle init command.
        
        Creates directory structure, initializes Git repository, and creates default config.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Expand paths
            repo_path = os.path.expanduser(args.repo)
            config_path = os.path.expanduser(args.config)
            
            print(f"Initializing GitProc at {repo_path}")
            
            # Create repository directory
            os.makedirs(repo_path, exist_ok=True)
            print(f"✓ Created repository directory: {repo_path}")
            
            # Initialize Git repository
            if not os.path.exists(os.path.join(repo_path, '.git')):
                result = subprocess.run(
                    ['git', 'init'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"Error initializing Git repository: {result.stderr}", file=sys.stderr)
                    return 1
                print(f"✓ Initialized Git repository")
            else:
                print(f"✓ Git repository already exists")
            
            # Create default config
            config = Config(
                repo_path=repo_path,
                branch='main',
                socket_path='/var/run/gitproc.sock',
                state_file='/var/lib/gitproc/state.json',
                log_dir='/var/log/gitproc',
                cgroup_root='/sys/fs/cgroup/gitproc'
            )
            
            # Create config directory
            config_dir = os.path.dirname(config_path)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
            
            # Save config
            config.save(config_path)
            print(f"✓ Created configuration file: {config_path}")
            
            # Create necessary directories
            config.ensure_directories()
            print(f"✓ Created log directory: {config.log_dir}")
            print(f"✓ Created state directory: {os.path.dirname(config.state_file)}")
            
            print("\nInitialization complete!")
            print(f"\nNext steps:")
            print(f"1. Add service unit files to {repo_path}")
            print(f"2. Commit them to Git: cd {repo_path} && git add . && git commit -m 'Initial services'")
            print(f"3. Start the daemon: gitproc daemon --config {config_path}")
            
            return 0
            
        except Exception as e:
            print(f"Error during initialization: {e}", file=sys.stderr)
            return 1
    
    def _cmd_daemon(self, args) -> int:
        """
        Handle daemon command.
        
        Starts the daemon process.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Expand config path
            config_path = os.path.expanduser(args.config)
            
            # Load configuration
            config = Config.load(config_path)
            
            # Override branch if specified
            if args.branch:
                config.branch = args.branch
            
            print(f"Starting GitProc daemon")
            print(f"Repository: {config.repo_path}")
            print(f"Branch: {config.branch}")
            print(f"Socket: {config.socket_path}")
            
            # Create and run daemon
            daemon = Daemon(config)
            daemon.run()
            
            return 0
            
        except FileNotFoundError as e:
            print(f"Configuration file not found: {e}", file=sys.stderr)
            print(f"Run 'gitproc init' to create a configuration file.", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error starting daemon: {e}", file=sys.stderr)
            return 1
    
    def _cmd_start(self, args) -> int:
        """
        Handle start command.
        
        Sends start command to daemon via socket.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send start command
            response = client.send_command({
                'action': 'start',
                'name': args.service
            })
            
            if response.get('success'):
                print(response.get('message', f"Service {args.service} started"))
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_stop(self, args) -> int:
        """
        Handle stop command.
        
        Sends stop command to daemon via socket.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send stop command
            response = client.send_command({
                'action': 'stop',
                'name': args.service
            })
            
            if response.get('success'):
                print(response.get('message', f"Service {args.service} stopped"))
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_restart(self, args) -> int:
        """
        Handle restart command.
        
        Sends restart command to daemon via socket.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send restart command
            response = client.send_command({
                'action': 'restart',
                'name': args.service
            })
            
            if response.get('success'):
                print(response.get('message', f"Service {args.service} restarted"))
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_status(self, args) -> int:
        """
        Handle status command.
        
        Sends status command to daemon and displays formatted output.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send status command
            response = client.send_command({
                'action': 'status',
                'name': args.service
            })
            
            if response.get('success'):
                state = response.get('state', {})
                
                # Format and display status
                print(f"● {state.get('name', args.service)}")
                print(f"   Status: {state.get('status', 'unknown')}")
                
                if state.get('pid'):
                    print(f"   PID: {state.get('pid')}")
                
                if state.get('start_time'):
                    import time
                    start_time = state.get('start_time')
                    uptime = time.time() - start_time
                    hours = int(uptime // 3600)
                    minutes = int((uptime % 3600) // 60)
                    seconds = int(uptime % 60)
                    print(f"   Uptime: {hours}h {minutes}m {seconds}s")
                
                print(f"   Restart count: {state.get('restart_count', 0)}")
                
                if state.get('last_exit_code') is not None:
                    print(f"   Last exit code: {state.get('last_exit_code')}")
                
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_logs(self, args) -> int:
        """
        Handle logs command.
        
        Sends logs command to daemon and displays output.
        Supports --follow flag for real-time streaming and --lines to limit output.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            if args.follow:
                # Follow mode: continuously poll for new logs
                import time
                
                print(f"Following logs for {args.service} (Ctrl+C to stop)...")
                last_position = 0
                
                try:
                    while True:
                        # Send logs command
                        response = client.send_command({
                            'action': 'logs',
                            'name': args.service,
                            'lines': args.lines
                        })
                        
                        if response.get('success'):
                            logs = response.get('logs', '')
                            
                            # Only print new content
                            if len(logs) > last_position:
                                print(logs[last_position:], end='')
                                last_position = len(logs)
                        else:
                            print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                            return 1
                        
                        # Sleep before next poll
                        time.sleep(1)
                        
                except KeyboardInterrupt:
                    print("\nStopped following logs")
                    return 0
            else:
                # One-time logs retrieval
                response = client.send_command({
                    'action': 'logs',
                    'name': args.service,
                    'lines': args.lines
                })
                
                if response.get('success'):
                    logs = response.get('logs', '')
                    print(logs, end='')
                    return 0
                else:
                    print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                    return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_list(self, args) -> int:
        """
        Handle list command.
        
        Sends list command to daemon and displays all services with their status.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send list command
            response = client.send_command({
                'action': 'list'
            })
            
            if response.get('success'):
                services = response.get('services', [])
                
                if not services:
                    print("No services registered")
                    return 0
                
                # Display services in a table format
                print(f"{'SERVICE':<30} {'STATUS':<12} {'PID':<10} {'RESTARTS':<10}")
                print("-" * 62)
                
                for service in services:
                    name = service.get('name', 'unknown')
                    status = service.get('status', 'unknown')
                    pid = service.get('pid', '-')
                    restart_count = service.get('restart_count', 0)
                    
                    # Format PID
                    pid_str = str(pid) if pid else '-'
                    
                    print(f"{name:<30} {status:<12} {pid_str:<10} {restart_count:<10}")
                
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_rollback(self, args) -> int:
        """
        Handle rollback command.
        
        Sends rollback command to daemon with commit hash and displays affected services.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send rollback command
            response = client.send_command({
                'action': 'rollback',
                'commit': args.commit
            })
            
            if response.get('success'):
                print(response.get('message', f"Rolled back to commit {args.commit}"))
                
                # Display affected services
                affected = response.get('affected_services', [])
                if affected:
                    print(f"\nAffected services:")
                    for service in affected:
                        print(f"  - {service}")
                
                # Display restarted services
                restarted = response.get('restarted_services', [])
                if restarted:
                    print(f"\nRestarted services:")
                    for service in restarted:
                        print(f"  - {service}")
                
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _cmd_sync(self, args) -> int:
        """
        Handle sync command.
        
        Sends sync command to daemon to manually trigger Git synchronization.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Load config to get socket path
            config_path = os.path.expanduser(args.config)
            config = Config.load_or_default(config_path)
            
            # Create daemon client
            client = DaemonClient(config.socket_path)
            
            # Send sync command
            response = client.send_command({
                'action': 'sync'
            })
            
            if response.get('success'):
                print(response.get('message', 'Git sync completed'))
                return 0
            else:
                print(f"Error: {response.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
                
        except ConnectionError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


def main():
    """Main entry point for the CLI."""
    cli = CLI()
    sys.exit(cli.execute())


if __name__ == '__main__':
    main()
