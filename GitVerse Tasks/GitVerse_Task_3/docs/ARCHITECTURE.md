# GitProc Architecture

This document provides a detailed overview of the GitProc system architecture, component interactions, and data flow.

## System Overview

GitProc is a Git-backed process manager that combines version control with service management. The system consists of a CLI interface, a daemon process, and several core components that work together to manage service lifecycles.

## High-Level Architecture

```mermaid
graph TB
    User[User/Administrator]
    CLI[CLI Interface]
    Socket[Unix Socket]
    Daemon[Daemon Process]
    Git[Git Repository]
    Processes[Managed Processes]
    
    User -->|Commands| CLI
    CLI -->|JSON RPC| Socket
    Socket -->|IPC| Daemon
    Daemon -->|Read/Monitor| Git
    Daemon -->|Spawn/Control| Processes
    Git -->|Unit Files| Daemon
    Processes -->|Logs/Status| Daemon
    Daemon -->|Response| Socket
    Socket -->|Results| CLI
    CLI -->|Display| User
    
    style Daemon fill:#4a90e2
    style Git fill:#f39c12
    style Processes fill:#27ae60
```

## Component Architecture

```mermaid
graph TB
    subgraph "CLI Layer"
        CLI[CLI Interface<br/>cli.py]
        Client[Daemon Client<br/>Socket Communication]
    end
    
    subgraph "Daemon Layer"
        Daemon[Daemon Process<br/>daemon.py]
        Server[Unix Socket Server]
        EventLoop[Main Event Loop]
    end
    
    subgraph "Core Components"
        Parser[Unit File Parser<br/>parser.py]
        State[State Manager<br/>state_manager.py]
        ProcMgr[Process Manager<br/>process_manager.py]
        GitInt[Git Integration<br/>git_integration.py]
        DepRes[Dependency Resolver<br/>dependency_resolver.py]
    end
    
    subgraph "Monitoring Components"
        GitMon[Git Monitor<br/>git_monitor.py]
        HealthMon[Health Monitor<br/>health_monitor.py]
        ProcMon[Process Monitor<br/>SIGCHLD Handler]
    end
    
    subgraph "System Integration"
        ResCtr[Resource Controller<br/>resource_controller.py]
        Cgroups[Cgroups v2]
        Namespaces[PID Namespaces]
    end
    
    CLI --> Client
    Client --> Server
    Server --> Daemon
    Daemon --> EventLoop
    
    EventLoop --> Parser
    EventLoop --> State
    EventLoop --> ProcMgr
    EventLoop --> GitInt
    EventLoop --> DepRes
    
    Daemon --> GitMon
    Daemon --> HealthMon
    Daemon --> ProcMon
    
    ProcMgr --> ResCtr
    ResCtr --> Cgroups
    ProcMgr --> Namespaces
    
    GitMon --> GitInt
    HealthMon --> ProcMgr
    ProcMon --> State
    
    style Daemon fill:#4a90e2
    style EventLoop fill:#3498db
    style ProcMgr fill:#27ae60
    style GitInt fill:#f39c12
```

## Data Flow Diagrams

### Service Start Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Daemon
    participant Parser
    participant DepResolver
    participant ProcessMgr
    participant ResourceCtrl
    participant Process
    
    User->>CLI: start my-app
    CLI->>Daemon: {"cmd": "start", "service": "my-app"}
    Daemon->>Parser: parse(my-app.service)
    Parser-->>Daemon: UnitFile object
    Daemon->>DepResolver: get_start_order([my-app])
    DepResolver-->>Daemon: [dependency, my-app]
    
    loop For each service in order
        Daemon->>ResourceCtrl: create_cgroup(service, limits)
        ResourceCtrl-->>Daemon: cgroup_path
        Daemon->>ProcessMgr: start_process(unit, cgroup_path)
        ProcessMgr->>ProcessMgr: fork()
        ProcessMgr->>ProcessMgr: unshare(CLONE_NEWPID)
        ProcessMgr->>ProcessMgr: drop_privileges()
        ProcessMgr->>Process: execvp(command)
        Process-->>ProcessMgr: PID
        ProcessMgr-->>Daemon: ProcessInfo
        Daemon->>Daemon: update_state(running)
    end
    
    Daemon-->>CLI: {"status": "success", "pid": 1234}
    CLI-->>User: Service started (PID: 1234)
```

### Git Sync Flow

```mermaid
sequenceDiagram
    participant GitRepo as Git Repository
    participant GitMonitor as Git Monitor
    participant Daemon
    participant Parser
    participant ProcessMgr
    participant Services
    
    Note over GitRepo: User commits changes
    GitRepo->>GitMonitor: File change detected
    GitMonitor->>GitMonitor: Check commit hash
    GitMonitor->>Daemon: notify_changes()
    Daemon->>GitRepo: get_changed_files()
    GitRepo-->>Daemon: [modified.service, new.service, deleted.service]
    
    loop For each modified file
        Daemon->>Parser: parse(modified.service)
        Parser-->>Daemon: UnitFile
        Daemon->>ProcessMgr: stop_process(old_pid)
        ProcessMgr->>Services: SIGTERM
        Services-->>ProcessMgr: Exit
        Daemon->>ProcessMgr: start_process(new_unit)
        ProcessMgr->>Services: spawn
        Services-->>Daemon: New PID
    end
    
    loop For each new file
        Daemon->>Parser: parse(new.service)
        Parser-->>Daemon: UnitFile
        Daemon->>Daemon: register_service()
    end
    
    loop For each deleted file
        Daemon->>ProcessMgr: stop_process(pid)
        ProcessMgr->>Services: SIGTERM
        Daemon->>Daemon: unregister_service()
    end
    
    Daemon->>Daemon: save_state()
```

### Health Check Flow

```mermaid
sequenceDiagram
    participant Timer
    participant HealthMon as Health Monitor
    participant Service
    participant ProcessMgr as Process Manager
    participant Daemon
    
    loop Every HealthCheckInterval seconds
        Timer->>HealthMon: trigger_check()
        HealthMon->>Service: GET /health
        
        alt Service Healthy
            Service-->>HealthMon: HTTP 200 OK
            HealthMon->>HealthMon: log_success()
        else Service Unhealthy
            Service-->>HealthMon: HTTP 500 / Timeout
            HealthMon->>HealthMon: log_failure()
            HealthMon->>Daemon: request_restart(service)
            Daemon->>ProcessMgr: stop_process(pid)
            ProcessMgr->>Service: SIGTERM
            Service-->>ProcessMgr: Exit
            Daemon->>ProcessMgr: start_process(unit)
            ProcessMgr->>Service: spawn
            Service-->>Daemon: New PID
            Daemon->>Daemon: update_state()
        end
    end
```

### Process Restart Flow

```mermaid
sequenceDiagram
    participant Process
    participant Kernel
    participant Daemon
    participant StateManager
    participant ProcessMgr
    
    Process->>Process: crash/exit
    Process->>Kernel: exit(code)
    Kernel->>Daemon: SIGCHLD
    Daemon->>Daemon: handle_sigchld()
    Daemon->>Kernel: waitpid(WNOHANG)
    Kernel-->>Daemon: (pid, exit_code)
    Daemon->>StateManager: get_service_by_pid(pid)
    StateManager-->>Daemon: service_name, unit
    
    alt Restart=always
        Daemon->>StateManager: increment_restart_count()
        Daemon->>StateManager: update_state(stopped)
        Daemon->>ProcessMgr: start_process(unit)
        ProcessMgr->>Process: spawn
        Process-->>ProcessMgr: new_pid
        ProcessMgr-->>Daemon: ProcessInfo
        Daemon->>StateManager: update_state(running, new_pid)
        Daemon->>Daemon: log_restart()
    else Restart=no
        Daemon->>StateManager: update_state(stopped, exit_code)
        Daemon->>Daemon: log_exit()
    end
```

## Component Details

### CLI Interface (cli.py)

**Responsibilities:**
- Parse command-line arguments
- Connect to daemon via Unix socket
- Send JSON-encoded commands
- Display formatted responses
- Handle connection errors

**Key Classes:**
- `CLI`: Main CLI handler
- `DaemonClient`: Socket communication wrapper

### Daemon Process (daemon.py)

**Responsibilities:**
- Main event loop coordination
- Unix socket server for CLI communication
- Signal handling (SIGTERM, SIGCHLD)
- Service lifecycle orchestration
- State persistence

**Key Classes:**
- `Daemon`: Main daemon controller
- `UnixSocketServer`: IPC server

**Threads:**
- Main thread: Event loop and socket server
- Git monitor thread: Repository change detection
- Health check thread: Periodic health checks

### Unit File Parser (parser.py)

**Responsibilities:**
- Parse .service files (INI format)
- Extract service directives
- Validate configuration
- Convert units (memory, CPU)

**Key Classes:**
- `UnitFile`: Service configuration dataclass
- `UnitFileParser`: Parser and validator

### Process Manager (process_manager.py)

**Responsibilities:**
- Process spawning with isolation
- Signal handling (SIGTERM, SIGKILL)
- Output capture and logging
- Privilege dropping
- Cgroup integration

**Key Classes:**
- `ProcessManager`: Process lifecycle controller
- `ProcessInfo`: Process metadata

**Isolation Features:**
- PID namespace (Linux)
- User/group switching
- Environment isolation
- Resource limits via cgroups

### Git Integration (git_integration.py)

**Responsibilities:**
- Repository initialization
- Unit file discovery
- Change detection
- Rollback operations
- Branch management

**Key Classes:**
- `GitIntegration`: Git operations wrapper

**Dependencies:**
- GitPython library

### State Manager (state_manager.py)

**Responsibilities:**
- Service registry
- State tracking (running/stopped/failed)
- Persistent storage
- State queries

**Key Classes:**
- `ServiceState`: Service state dataclass
- `StateManager`: State controller

**Storage:**
- In-memory: Dict[service_name, ServiceState]
- Persistent: JSON file with atomic writes

### Resource Controller (resource_controller.py)

**Responsibilities:**
- Cgroup creation and management
- Memory limit enforcement
- CPU quota configuration
- Process assignment to cgroups

**Key Classes:**
- `ResourceController`: Cgroup manager

**Cgroup Support:**
- Cgroups v2 (preferred)
- Cgroups v1 (fallback)
- Graceful degradation if unavailable

### Dependency Resolver (dependency_resolver.py)

**Responsibilities:**
- Build dependency graph
- Topological sorting
- Cycle detection
- Start order calculation

**Key Classes:**
- `DependencyResolver`: Dependency graph manager

**Algorithm:**
- Kahn's algorithm for topological sort
- DFS for cycle detection

### Health Monitor (health_monitor.py)

**Responsibilities:**
- Periodic health checks
- HTTP endpoint monitoring
- Failure detection
- Restart triggering

**Key Classes:**
- `HealthMonitor`: Health check coordinator
- `HealthCheck`: Check configuration

**Check Types:**
- HTTP GET requests
- Timeout handling (5 seconds)
- Status code validation (200 = healthy)

### Git Monitor (git_monitor.py)

**Responsibilities:**
- File system monitoring
- Commit detection
- Change notification

**Key Classes:**
- `GitMonitor`: Repository watcher

**Implementation:**
- Watchdog library for file events
- Monitor .git/refs/heads/<branch>
- Fallback to polling if inotify unavailable

## Directory Structure

```
/etc/gitproc/
├── services/              # Git repository
│   ├── .git/             # Git metadata
│   ├── app.service       # Service unit files
│   ├── nginx.service
│   └── database.service
└── config.json           # Configuration

/var/lib/gitproc/
└── state.json            # Persistent state

/var/log/gitproc/
├── daemon.log            # Daemon logs
├── app.log               # Service logs
├── nginx.log
└── database.log

/var/run/
└── gitproc.sock          # Unix socket

/sys/fs/cgroup/gitproc/   # Cgroups
├── app/
│   ├── memory.max
│   ├── cpu.max
│   └── cgroup.procs
└── nginx/
    ├── memory.max
    ├── cpu.max
    └── cgroup.procs
```

## Communication Protocols

### CLI ↔ Daemon (Unix Socket)

**Protocol:** JSON-RPC over Unix domain socket

**Request Format:**
```json
{
  "command": "start|stop|restart|status|logs|list|rollback|sync",
  "service": "service-name",
  "args": {
    "follow": true,
    "lines": 100,
    "commit": "abc123"
  }
}
```

**Response Format:**
```json
{
  "status": "success|error",
  "data": {
    "pid": 1234,
    "state": "running",
    "logs": "..."
  },
  "error": "error message if status=error"
}
```

### Daemon ↔ Services

**Process Control:**
- SIGTERM: Graceful shutdown request
- SIGKILL: Forced termination (after timeout)
- SIGCHLD: Process exit notification

**Output Capture:**
- stdout/stderr redirected to log files
- File descriptors duplicated with dup2()

## Security Model

### Privilege Separation

```
┌─────────────────────────────────────┐
│         Daemon (root)                │
│  - Namespace creation                │
│  - Cgroup management                 │
│  - Privilege dropping                │
└──────────────┬──────────────────────┘
               │
               ├─────────────────────────┐
               │                         │
               ▼                         ▼
    ┌──────────────────┐    ┌──────────────────┐
    │  Service A       │    │  Service B       │
    │  (user: nobody)  │    │  (user: appuser) │
    │  - No root       │    │  - No root       │
    │  - Isolated PID  │    │  - Isolated PID  │
    │  - Resource lim  │    │  - Resource lim  │
    └──────────────────┘    └──────────────────┘
```

### Isolation Layers

1. **PID Namespace**: Process cannot see other system processes
2. **User Separation**: Services run as non-root users
3. **Resource Limits**: Cgroups prevent resource exhaustion
4. **File System**: Services inherit daemon's file system view

## Performance Considerations

### Event-Driven Architecture

- Non-blocking I/O for socket communication
- Signal-driven process monitoring (SIGCHLD)
- File system events for Git monitoring (inotify)
- Thread pool for health checks

### Resource Usage

**Daemon:**
- Memory: ~20-50 MB baseline
- CPU: <1% idle, <5% during operations
- File descriptors: 3 + (2 × number of services)

**Per Service:**
- Memory: Service-dependent + ~1 MB overhead
- CPU: Service-dependent
- File descriptors: 3 (stdin/stdout/stderr) + service usage

### Scalability

- Tested with 100+ concurrent services
- Linear memory growth with service count
- Constant CPU usage (event-driven)
- Git operations scale with repository size

## Error Handling Strategy

### Graceful Degradation

```
Feature Available? → Use Feature
       ↓ No
   Log Warning
       ↓
   Continue Without Feature
       ↓
   Provide Reduced Functionality
```

**Examples:**
- No PID namespace support → Run without isolation
- No cgroups → Run without resource limits
- Git operation fails → Continue with last known state
- Health check fails → Log and retry

### Error Recovery

- Automatic restart on service crash (if configured)
- State persistence across daemon restarts
- Rollback capability for bad configurations
- Detailed error logging for troubleshooting

## Future Architecture Considerations

### Potential Enhancements

1. **Distributed Management**
   - Git push/pull for multi-node synchronization
   - Shared state via distributed database
   - Leader election for coordination

2. **Additional Isolation**
   - Network namespaces
   - Mount namespaces
   - Seccomp profiles

3. **Advanced Monitoring**
   - Metrics collection (Prometheus)
   - Distributed tracing
   - Performance profiling

4. **High Availability**
   - Daemon redundancy
   - Automatic failover
   - Service migration

## References

- [Linux Namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [Cgroups v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [systemd Unit Files](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Git Internals](https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain)
