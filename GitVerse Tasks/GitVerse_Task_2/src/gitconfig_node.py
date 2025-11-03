"""
HTTP API server node for GitConfig
"""
import sys
import json
import signal
import logging
import argparse
from flask import Flask, request, jsonify
from gitconfig_core import GitConfigStore


# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class GitConfigNode:
    def __init__(self, repo_path: str, http_port: int, remote_url: str = None, sync_interval: int = 30):
        self.store = GitConfigStore(repo_path, sync_interval)
        self.http_port = http_port
        self.app = Flask(__name__)
        self._setup_routes()
        
        # Setup remote if provided
        if remote_url:
            self.store.add_remote('origin', remote_url)
            
        # Start background tasks
        self.store.start_ttl_cleanup()
        if remote_url:
            self.store.start_sync('origin')
            
        # Setup graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        signal.signal(signal.SIGINT, self._shutdown_handler)
        
    def _setup_routes(self):
        """Setup HTTP API routes"""
        
        @self.app.route('/keys/<path:key>', methods=['GET'])
        def get_key(key):
            key = '/' + key
            commit = request.args.get('commit')
            value = self.store.get(key, commit=commit)
            
            if value is None:
                logger.warning(f"Key not found: {key}")
                return jsonify({'error': 'Key not found'}), 404
                
            logger.info(f"GET {key}")
            return jsonify({'key': key, 'value': value})
            
        @self.app.route('/keys/<path:key>', methods=['POST'])
        def set_key(key):
            key = '/' + key
            value = request.get_data(as_text=True)
            ttl = request.args.get('ttl', type=int)
            
            if self.store.set(key, value, ttl=ttl):
                logger.info(f"SET {key} (ttl={ttl})")
                return jsonify({'success': True, 'key': key})
            else:
                logger.error(f"Failed to set {key}")
                return jsonify({'error': 'Failed to set key'}), 500
                
        @self.app.route('/keys/<path:key>', methods=['DELETE'])
        def delete_key(key):
            key = '/' + key
            
            if self.store.delete(key):
                logger.info(f"DELETE {key}")
                return jsonify({'success': True})
            else:
                logger.warning(f"Key not found for deletion: {key}")
                return jsonify({'error': 'Key not found'}), 404

        @self.app.route('/keys/<path:key>/history', methods=['GET'])
        def get_history(key):
            key = '/' + key
            history = self.store.history(key)
            logger.info(f"HISTORY {key}")
            return jsonify({'key': key, 'history': history})
            
        @self.app.route('/list', methods=['GET'])
        def list_keys():
            prefix = request.args.get('prefix', '/')
            recursive = request.args.get('recursive', 'false').lower() == 'true'
            keys = self.store.list_keys(prefix, recursive)
            logger.info(f"LIST {prefix} (recursive={recursive})")
            return jsonify({'prefix': prefix, 'keys': keys})
            
        @self.app.route('/cas/<path:key>', methods=['POST'])
        def compare_and_swap(key):
            key = '/' + key
            data = request.get_json()
            expected = data.get('expected')
            new_value = data.get('new_value')
            
            if self.store.cas(key, expected, new_value):
                logger.info(f"CAS {key} succeeded")
                return jsonify({'success': True})
            else:
                logger.warning(f"CAS {key} failed")
                return jsonify({'success': False, 'error': 'Value mismatch'}), 409
                
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({'status': 'healthy'})
            
    def _shutdown_handler(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info("Shutting down gracefully...")
        self.store.stop()
        logger.info("Shutdown complete")
        sys.exit(0)
        
    def run(self):
        """Start HTTP server"""
        logger.info(f"Starting GitConfig node on port {self.http_port}")
        self.app.run(host='0.0.0.0', port=self.http_port, threaded=True)


def main():
    parser = argparse.ArgumentParser(description='GitConfig Node')
    parser.add_argument('command', choices=['start'], help='Command to execute')
    parser.add_argument('--repo', required=True, help='Repository path')
    parser.add_argument('--http-port', type=int, default=8080, help='HTTP port')
    parser.add_argument('--remote', help='Remote repository URL')
    parser.add_argument('--sync-interval', type=int, default=30, help='Sync interval in seconds')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        node = GitConfigNode(args.repo, args.http_port, args.remote, args.sync_interval)
        node.run()


if __name__ == '__main__':
    main()
