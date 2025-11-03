"""
CLI interface for GitConfig
"""
import sys
import argparse
import requests
from gitconfig_core import GitConfigStore


def main():
    parser = argparse.ArgumentParser(description='GitConfig CLI')
    parser.add_argument('command', choices=['set', 'get', 'delete', 'list', 'history', 'watch', 'cas'],
                       help='Command to execute')
    parser.add_argument('key', nargs='?', help='Key to operate on')
    parser.add_argument('value', nargs='?', help='Value to set')
    parser.add_argument('--repo', default='./data/default', help='Local repository path')
    parser.add_argument('--http', help='HTTP API endpoint (e.g., http://localhost:8080)')
    parser.add_argument('--commit', help='Commit hash for versioned get')
    parser.add_argument('--ttl', type=int, help='TTL in seconds')
    parser.add_argument('--recursive', action='store_true', help='Recursive list')
    parser.add_argument('--expected', help='Expected value for CAS')
    parser.add_argument('--timeout', type=int, help='Watch timeout in seconds')
    
    args = parser.parse_args()
    
    # Use HTTP API if provided
    if args.http:
        use_http_api(args)
    else:
        use_local_store(args)


def use_http_api(args):
    """Use HTTP API for operations"""
    base_url = args.http.rstrip('/')
    
    try:
        if args.command == 'set':
            if not args.key or args.value is None:
                print("Error: set requires key and value")
                sys.exit(1)
            
            url = f"{base_url}/keys{args.key}"
            params = {}
            if args.ttl:
                params['ttl'] = args.ttl
                
            response = requests.post(url, data=args.value, params=params)
            if response.status_code == 200:
                print(f"Set {args.key} = {args.value}")
            else:
                print(f"Error: {response.json().get('error', 'Unknown error')}")
                
        elif args.command == 'get':
            if not args.key:
                print("Error: get requires key")
                sys.exit(1)
                
            url = f"{base_url}/keys{args.key}"
            params = {}
            if args.commit:
                params['commit'] = args.commit
                
            response = requests.get(url, params=params)
            if response.status_code == 200:
                print(response.json()['value'])
            else:
                print(f"Error: {response.json().get('error', 'Unknown error')}")
                
        elif args.command == 'delete':
            if not args.key:
                print("Error: delete requires key")
                sys.exit(1)
                
            url = f"{base_url}/keys{args.key}"
            response = requests.delete(url)
            if response.status_code == 200:
                print(f"Deleted {args.key}")
            else:
                print(f"Error: {response.json().get('error', 'Unknown error')}")
                
        elif args.command == 'list':
            prefix = args.key or '/'
            url = f"{base_url}/list"
            params = {'prefix': prefix, 'recursive': str(args.recursive).lower()}
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                keys = response.json()['keys']
                for key in keys:
                    print(key)
            else:
                print(f"Error: {response.json().get('error', 'Unknown error')}")
                
        elif args.command == 'history':
            if not args.key:
                print("Error: history requires key")
                sys.exit(1)
                
            url = f"{base_url}/keys{args.key}/history"
            response = requests.get(url)
            if response.status_code == 200:
                history = response.json()['history']
                for entry in history:
                    print(f"{entry['commit']} - {entry['date']} - {entry['message']}")
            else:
                print(f"Error: {response.json().get('error', 'Unknown error')}")
                
        elif args.command == 'cas':
            if not args.key or args.value is None or args.expected is None:
                print("Error: cas requires key, value, and --expected")
                sys.exit(1)
                
            url = f"{base_url}/cas{args.key}"
            data = {'expected': args.expected, 'new_value': args.value}
            response = requests.post(url, json=data)
            if response.status_code == 200:
                print(f"CAS succeeded: {args.key} = {args.value}")
            else:
                print(f"CAS failed: {response.json().get('error', 'Value mismatch')}")
                
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        sys.exit(1)



def use_local_store(args):
    """Use local store for operations"""
    store = GitConfigStore(args.repo)
    
    try:
        if args.command == 'set':
            if not args.key or args.value is None:
                print("Error: set requires key and value")
                sys.exit(1)
                
            if store.set(args.key, args.value, ttl=args.ttl):
                print(f"Set {args.key} = {args.value}")
            else:
                print("Error: Failed to set key")
                
        elif args.command == 'get':
            if not args.key:
                print("Error: get requires key")
                sys.exit(1)
                
            value = store.get(args.key, commit=args.commit)
            if value is not None:
                print(value)
            else:
                print("Error: Key not found")
                sys.exit(1)
                
        elif args.command == 'delete':
            if not args.key:
                print("Error: delete requires key")
                sys.exit(1)
                
            if store.delete(args.key):
                print(f"Deleted {args.key}")
            else:
                print("Error: Key not found")
                sys.exit(1)
                
        elif args.command == 'list':
            prefix = args.key or '/'
            keys = store.list_keys(prefix, recursive=args.recursive)
            for key in keys:
                print(key)
                
        elif args.command == 'history':
            if not args.key:
                print("Error: history requires key")
                sys.exit(1)
                
            history = store.history(args.key)
            for entry in history:
                print(f"{entry['commit']} - {entry['date']} - {entry['message']}")
                
        elif args.command == 'watch':
            if not args.key:
                print("Error: watch requires key")
                sys.exit(1)
                
            print(f"Watching {args.key}...")
            if store.watch(args.key, timeout=args.timeout):
                print(f"Key {args.key} changed!")
            else:
                print("Watch timeout")
                
        elif args.command == 'cas':
            if not args.key or args.value is None or args.expected is None:
                print("Error: cas requires key, value, and --expected")
                sys.exit(1)
                
            if store.cas(args.key, args.expected, args.value):
                print(f"CAS succeeded: {args.key} = {args.value}")
            else:
                print("CAS failed: Value mismatch")
                sys.exit(1)
                
    finally:
        store.stop()


if __name__ == '__main__':
    main()
