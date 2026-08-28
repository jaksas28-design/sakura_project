#!/usr/bin/env python3
"""
Sakura Audit Chain - Cryptographic audit logging system

SHA-256 hash chain ensures tamper-evidence: if any entry is modified,
all subsequent hashes break, proving tampering occurred.

Every classification result is logged with:
- Previous hash (links to prior entry)
- Current hash (computed from prev_hash + current_data)
- Timestamp, classification, score, features, weights, threshold

Usage:
    python3 audit.py --log audit_chain.jsonl --verify
    python3 audit.py --log audit_chain.jsonl --append result.json
"""

import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class AuditChain:
    """Cryptographic audit chain using SHA-256 hash linking."""
    
    GENESIS_HASH = '0' * 64  # Initial hash for chain start
    
    def __init__(self, log_path: str, debug: bool = False):
        """
        Initialize audit chain.
        
        Args:
            log_path: Path to JSONL audit log file
            debug: Enable verbose logging
        """
        self.log_path = Path(log_path)
        self.debug = debug
        
        # Create parent directories if needed
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize log file if doesn't exist
        if not self.log_path.exists():
            self.log_path.touch()
            if self.debug:
                print(f"[DEBUG] Created new audit log: {self.log_path}")
    
    @staticmethod
    def compute_hash(prev_hash: str, entry_data: Dict) -> str:
        """
        Compute SHA-256 hash: H(prev_hash + json(entry_data))
        
        Args:
            prev_hash: Hash of previous entry (or GENESIS_HASH)
            entry_data: Current entry data (without curr_hash field)
            
        Returns:
            SHA-256 hex digest
        """
        # Serialize entry with sorted keys for deterministic output
        entry_json = json.dumps(entry_data, sort_keys=True, separators=(',', ':'))
        
        # Combine previous hash + current data
        message = prev_hash + entry_json
        
        # Compute SHA-256
        hash_obj = hashlib.sha256(message.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def get_last_hash(self) -> str:
        """
        Get hash of last entry in chain.
        
        Returns:
            Last hash, or GENESIS_HASH if chain is empty
        """
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return self.GENESIS_HASH
        
        try:
            with open(self.log_path, 'r') as f:
                last_line = None
                for line in f:
                    last_line = line.strip()
                
                if last_line:
                    entry = json.loads(last_line)
                    return entry.get('curr_hash', self.GENESIS_HASH)
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Error reading last hash: {e}")
        
        return self.GENESIS_HASH
    
    def append_entry(
        self,
        operation: str,
        data: Dict,
        sequence: Optional[int] = None
    ) -> Dict:
        """
        Append entry to audit chain with hash linking.
        
        Args:
            operation: Operation type (e.g., 'classify', 'verify')
            data: Operation data (classification result, etc.)
            sequence: Sequence number (auto-increment if None)
            
        Returns:
            Complete audit entry with hash
        """
        # Get previous hash
        prev_hash = self.get_last_hash()
        
        # Auto-increment sequence
        if sequence is None:
            sequence = self._get_next_sequence()
        
        # Build entry (without curr_hash yet)
        entry_data = {
            'sequence': sequence,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'prev_hash': prev_hash,
            'operation': operation,
            **data  # Merge operation-specific data
        }
        
        # Compute hash
        curr_hash = self.compute_hash(prev_hash, entry_data)
        entry_data['curr_hash'] = curr_hash
        
        # Write to log
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry_data) + '\n')
            
            if self.debug:
                print(f"[DEBUG] Appended entry {sequence}: {curr_hash[:8]}...")
        except Exception as e:
            raise RuntimeError(f"Failed to write audit entry: {e}")
        
        return entry_data
    
    def _get_next_sequence(self) -> int:
        """Get next sequence number (last + 1, or 1 if empty)."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return 1
        
        try:
            with open(self.log_path, 'r') as f:
                last_line = None
                for line in f:
                    last_line = line.strip()
                
                if last_line:
                    entry = json.loads(last_line)
                    return entry.get('sequence', 0) + 1
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Error getting sequence: {e}")
        
        return 1
    
    def verify_chain(self) -> Tuple[bool, List[str]]:
        """
        Verify entire hash chain for tampering.
        
        Algorithm:
        1. For each entry, recompute its hash from prev_hash + data
        2. Compare with stored curr_hash
        3. If mismatch, entry was tampered with
        4. Chain breaks at first tampering (all subsequent entries suspect)
        
        Returns:
            (is_valid, error_messages)
            - is_valid: True if no tampering detected
            - error_messages: List of tampering locations (empty if valid)
        """
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return True, []
        
        errors = []
        prev_hash = self.GENESIS_HASH
        
        try:
            with open(self.log_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as e:
                        errors.append(f"Line {line_num}: Invalid JSON - {e}")
                        break
                    
                    # Verify previous hash link
                    stored_prev_hash = entry.get('prev_hash')
                    if stored_prev_hash != prev_hash:
                        errors.append(
                            f"Line {line_num}: prev_hash mismatch. "
                            f"Expected: {prev_hash}, Got: {stored_prev_hash}"
                        )
                        break
                    
                    # Extract and remove curr_hash for recomputation
                    stored_curr_hash = entry.get('curr_hash')
                    entry_data = {k: v for k, v in entry.items() if k != 'curr_hash'}
                    
                    # Recompute hash
                    computed_curr_hash = self.compute_hash(prev_hash, entry_data)
                    
                    if stored_curr_hash != computed_curr_hash:
                        errors.append(
                            f"Line {line_num}: curr_hash mismatch (TAMPERING DETECTED). "
                            f"Expected: {computed_curr_hash}, Got: {stored_curr_hash}"
                        )
                        break
                    
                    # Move to next entry
                    prev_hash = stored_curr_hash
                
        except Exception as e:
            errors.append(f"Chain verification error: {e}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def get_entries(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Retrieve all entries from chain.
        
        Args:
            limit: Maximum number of entries to return (None = all)
            
        Returns:
            List of audit entries
        """
        entries = []
        
        if not self.log_path.exists():
            return entries
        
        try:
            with open(self.log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
                    
                    if limit and len(entries) >= limit:
                        break
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Error reading entries: {e}")
        
        return entries
    
    def export_report(self, output_path: Optional[str] = None) -> Dict:
        """
        Generate verification report.
        
        Args:
            output_path: Optional file to write report JSON
            
        Returns:
            Report dict with summary and results
        """
        is_valid, errors = self.verify_chain()
        entries = self.get_entries()
        
        report = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'log_file': str(self.log_path),
            'total_entries': len(entries),
            'chain_valid': is_valid,
            'errors': errors,
            'summary': {
                'verified_entries': len(entries) - len(errors),
                'total_entries': len(entries),
                'integrity_status': '✓ VERIFIED' if is_valid else '✗ TAMPERING DETECTED'
            }
        }
        
        # Write to file if path provided
        if output_path:
            try:
                with open(output_path, 'w') as f:
                    json.dump(report, f, indent=2)
                if self.debug:
                    print(f"[DEBUG] Report written to: {output_path}")
            except Exception as e:
                print(f"Error writing report: {e}", file=sys.stderr)
        
        return report


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Sakura Audit Chain - Cryptographic audit logging system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 audit.py --log audit_chain.jsonl --verify
  python3 audit.py --log audit_chain.jsonl --report report.json
  python3 audit.py --log audit_chain.jsonl --list
  python3 audit.py --log audit_chain.jsonl --append result.json
        """
    )
    
    parser.add_argument('--log', type=str, required=True, 
                        help='Path to audit chain JSONL file')
    parser.add_argument('--verify', action='store_true',
                        help='Verify chain integrity')
    parser.add_argument('--report', type=str,
                        help='Generate verification report (output file)')
    parser.add_argument('--list', action='store_true',
                        help='List all entries')
    parser.add_argument('--limit', type=int,
                        help='Limit number of entries to display')
    parser.add_argument('--append', type=str,
                        help='Append JSON entry to chain')
    parser.add_argument('--debug', action='store_true',
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Initialize chain
    chain = AuditChain(args.log, debug=args.debug)
    
    # Verify
    if args.verify:
        is_valid, errors = chain.verify_chain()
        
        if is_valid:
            print(f"✓ Chain is valid ({len(chain.get_entries())} entries verified)")
        else:
            print(f"✗ Chain tampering detected:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
    
    # Generate report
    if args.report:
        report = chain.export_report(output_path=args.report)
        print(json.dumps(report, indent=2))
    
    # List entries
    if args.list:
        entries = chain.get_entries(limit=args.limit)
        for entry in entries:
            print(json.dumps(entry, indent=2))
            print('-' * 60)
    
    # Append entry
    if args.append:
        try:
            with open(args.append, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading append file: {e}", file=sys.stderr)
            sys.exit(1)
        
        operation = data.pop('operation', 'custom')
        entry = chain.append_entry(operation, data)
        print(f"Appended entry {entry['sequence']}: {entry['curr_hash']}")
    
    # If no action specified, show help
    if not (args.verify or args.report or args.list or args.append):
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
