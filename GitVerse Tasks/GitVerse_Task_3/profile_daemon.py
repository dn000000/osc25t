#!/usr/bin/env python3
"""
Performance profiling script for GitProc daemon.

Measures CPU and memory usage of the daemon process.
"""

import os
import sys
import time
import psutil
import argparse
from pathlib import Path


def profile_daemon(pid: int, duration: int = 60, interval: float = 1.0):
    """
    Profile daemon process for specified duration.
    
    Args:
        pid: Process ID of daemon
        duration: Duration to profile in seconds
        interval: Sampling interval in seconds
    """
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"Error: Process {pid} not found")
        return
    
    print(f"Profiling daemon process {pid} for {duration} seconds...")
    print(f"Sampling interval: {interval}s")
    print("-" * 60)
    
    samples = []
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            try:
                # Get CPU and memory usage
                cpu_percent = process.cpu_percent(interval=0.1)
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                # Get thread count
                num_threads = process.num_threads()
                
                # Get I/O stats if available
                try:
                    io_counters = process.io_counters()
                    read_bytes = io_counters.read_bytes
                    write_bytes = io_counters.write_bytes
                except (AttributeError, psutil.AccessDenied):
                    read_bytes = 0
                    write_bytes = 0
                
                sample = {
                    'timestamp': time.time() - start_time,
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory_mb,
                    'num_threads': num_threads,
                    'read_bytes': read_bytes,
                    'write_bytes': write_bytes
                }
                samples.append(sample)
                
                # Print current stats
                print(f"[{sample['timestamp']:6.1f}s] "
                      f"CPU: {cpu_percent:5.1f}% | "
                      f"Memory: {memory_mb:7.2f} MB | "
                      f"Threads: {num_threads}")
                
            except psutil.NoSuchProcess:
                print("Process terminated")
                break
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\nProfiling interrupted")
    
    # Print summary statistics
    print("-" * 60)
    print("Summary Statistics:")
    print("-" * 60)
    
    if samples:
        cpu_values = [s['cpu_percent'] for s in samples]
        memory_values = [s['memory_mb'] for s in samples]
        
        print(f"CPU Usage:")
        print(f"  Average: {sum(cpu_values) / len(cpu_values):.2f}%")
        print(f"  Min:     {min(cpu_values):.2f}%")
        print(f"  Max:     {max(cpu_values):.2f}%")
        print()
        print(f"Memory Usage:")
        print(f"  Average: {sum(memory_values) / len(memory_values):.2f} MB")
        print(f"  Min:     {min(memory_values):.2f} MB")
        print(f"  Max:     {max(memory_values):.2f} MB")
        print()
        print(f"Threads: {samples[-1]['num_threads']}")
        
        if samples[-1]['read_bytes'] > 0 or samples[-1]['write_bytes'] > 0:
            total_read_mb = samples[-1]['read_bytes'] / (1024 * 1024)
            total_write_mb = samples[-1]['write_bytes'] / (1024 * 1024)
            print()
            print(f"I/O Statistics:")
            print(f"  Total Read:  {total_read_mb:.2f} MB")
            print(f"  Total Write: {total_write_mb:.2f} MB")


def find_daemon_pid():
    """
    Find the PID of the running GitProc daemon.
    
    Returns:
        PID of daemon or None if not found
    """
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'gitproc' in ' '.join(cmdline) and 'daemon' in ' '.join(cmdline):
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Profile GitProc daemon performance'
    )
    parser.add_argument(
        '--pid',
        type=int,
        help='PID of daemon process (auto-detect if not specified)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Duration to profile in seconds (default: 60)'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='Sampling interval in seconds (default: 1.0)'
    )
    
    args = parser.parse_args()
    
    # Find daemon PID if not specified
    pid = args.pid
    if pid is None:
        print("Auto-detecting daemon PID...")
        pid = find_daemon_pid()
        if pid is None:
            print("Error: Could not find running GitProc daemon")
            print("Please start the daemon or specify PID with --pid")
            sys.exit(1)
        print(f"Found daemon at PID {pid}")
    
    # Profile the daemon
    profile_daemon(pid, args.duration, args.interval)


if __name__ == '__main__':
    main()
