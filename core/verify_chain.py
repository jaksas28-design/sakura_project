#!/usr/bin/env python3
"""
Sakura Chain Verifier - Comprehensive audit chain analysis and reporting

Deep inspection of hash chain integrity with detailed diagnostics:
- Entry-by-entry hash verification
- Sequence continuity checks
- Timestamp monotonicity validation
- Schema compliance verification
- Tamper location pinpointing
- Detailed audit reports

Usage:
    python3 verify_chain.py --log audit_chain.jsonl
    python3 verify_chain.py --log audit_chain.jsonl --verbose
    python3 verify_chain.py --log audit_chain.jsonl --export report.json
    python3 verify_chain.py --log audit_chain.jsonl --stats
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from core.audit import AuditChain


class ChainVerifier:
    """Comprehensive chain verification with diagnostics."""
    
    def __init__(self, log_path: str, verbose: bool = False):
        """
        Initialize verifier.
        
        Args:
            log_path: Path to audit chain JSONL file
            verbose: Enable verbose output
        """
        self.log_path = Path(log_path)
        self.verbose = verbose
        self.chain = AuditChain(str(self.log_path), debug=verbose)
        self.entries = []
        self.results = {
            'hash_chain': {'valid': True, 'errors': []},
            'sequence': {'valid': True, 'errors': []},
            'timestamps': {'valid': True, 'errors': []},
            'schema': {'valid': True, 'errors': []},
            'overall': {'valid': True, 'tamper_detected': False}
        }
    
    def load_entries(self) -> bool:
        """Load all entries from chain file."""
        if not self.log_path.exists():
            print(f"✗ Chain file not found: {self.log_path}", file=sys.stderr)
            return False
        
        try:
            with open(self.log_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                        entry['_line_num'] = line_num
                        self.entries.append(entry)
                    except json.JSONDecodeError as e:
                        self.results['schema']['errors'].append(
                            f"Line {line_num}: Invalid JSON - {e}"
                        )
                        self.results['schema']['valid'] = False
            
            if self.verbose:
                print(f"[DEBUG] Loaded {len(self.entries)} entries")
            
            return True
        
        except Exception as e:
            print(f"✗ Error loading chain: {e}", file=sys.stderr)
            return False
    
    def verify_hash_chain(self) -> None:
        """Verify hash linking (curr_hash = hash(prev_hash + data))."""
        if not self.entries:
            return
        
        prev_hash = AuditChain.GENESIS_HASH
        
        for entry in self.entries:
            line_num = entry.get('_line_num', '?')
            stored_prev = entry.get('prev_hash')
            stored_curr = entry.get('curr_hash')
            
            # Check prev_hash link
            if stored_prev != prev_hash:
                error = (
                    f"Line {line_num}: prev_hash mismatch. "
                    f"Expected {prev_hash[:8]}..., got {stored_prev[:8]}..."
                )
                self.results['hash_chain']['errors'].append(error)
                self.results['hash_chain']['valid'] = False
                if self.verbose:
                    print(f"  ✗ {error}")
                break  # Chain breaks here
            
            # Recompute curr_hash
            entry_data = {k: v for k, v in entry.items() 
                         if k not in ('curr_hash', '_line_num')}
            computed_curr = AuditChain.compute_hash(prev_hash, entry_data)
            
            if stored_curr != computed_curr:
                error = (
                    f"Line {line_num}: curr_hash mismatch (TAMPERING). "
                    f"Expected {computed_curr[:8]}..., got {stored_curr[:8]}..."
                )
                self.results['hash_chain']['errors'].append(error)
                self.results['hash_chain']['valid'] = False
                self.results['overall']['tamper_detected'] = True
                if self.verbose:
                    print(f"  ✗ TAMPERING DETECTED: {error}")
                break  # Chain breaks here
            
            if self.verbose:
                print(f"  ✓ Entry {entry.get('sequence', '?')}: hash valid")
            
            prev_hash = stored_curr
    
    def verify_sequence(self) -> None:
        """Verify sequence numbers are continuous and monotonically increasing."""
        if not self.entries:
            return
        
        prev_seq = None
        
        for entry in self.entries:
            line_num = entry.get('_line_num', '?')
            seq = entry.get('sequence')
            
            if seq is None:
                error = f"Line {line_num}: Missing sequence number"
                self.results['sequence']['errors'].append(error)
                self.results['sequence']['valid'] = False
                continue
            
            # Check monotonic increase
            if prev_seq is not None and seq != prev_seq + 1:
                error = f"Line {line_num}: Sequence gap. Expected {prev_seq + 1}, got {seq}"
                self.results['sequence']['errors'].append(error)
                self.results['sequence']['valid'] = False
                if self.verbose:
                    print(f"  ✗ {error}")
            else:
                if self.verbose:
                    print(f"  ✓ Sequence {seq}: valid")
            
            prev_seq = seq
    
    def verify_timestamps(self) -> None:
        """Verify timestamps are monotonically increasing."""
        if not self.entries:
            return
        
        prev_ts = None
        
        for entry in self.entries:
            line_num = entry.get('_line_num', '?')
            ts_str = entry.get('timestamp')
            
            if not ts_str:
                error = f"Line {line_num}: Missing timestamp"
                self.results['timestamps']['errors'].append(error)
                self.results['timestamps']['valid'] = False
                continue
            
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                
                if prev_ts is not None and ts < prev_ts:
                    error = f"Line {line_num}: Timestamp went backward ({ts_str} < {prev_ts})"
                    self.results['timestamps']['errors'].append(error)
                    self.results['timestamps']['valid'] = False
                    if self.verbose:
                        print(f"  ✗ {error}")
                else:
                    if self.verbose:
                        print(f"  ✓ Timestamp {ts_str}: valid")
                
                prev_ts = ts
            
            except ValueError as e:
                error = f"Line {line_num}: Invalid timestamp format - {e}"
                self.results['timestamps']['errors'].append(error)
                self.results['timestamps']['valid'] = False
    
    def verify_schema(self) -> None:
        """Verify all required fields present in each entry."""
        required_fields = {
            'sequence', 'timestamp', 'prev_hash', 'curr_hash',
            'operation'
        }
        
        for entry in self.entries:
            line_num = entry.get('_line_num', '?')
            missing = required_fields - set(entry.keys())
            
            if missing:
                error = f"Line {line_num}: Missing fields: {missing}"
                self.results['schema']['errors'].append(error)
                self.results['schema']['valid'] = False
                if self.verbose:
                    print(f"  ✗ {error}")
            else:
                if self.verbose:
                    print(f"  ✓ Entry {entry.get('sequence', '?')}: schema valid")
    
    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        print("=" * 70)
        print("SAKURA AUDIT CHAIN VERIFICATION")
        print("=" * 70)
        
        # Load entries
        if not self.load_entries():
            return False
        
        print(f"\n📊 Chain File: {self.log_path}")
        print(f"📋 Total Entries: {len(self.entries)}")
        
        # Run checks
        print("\n🔍 Running verification checks...\n")
        
        print("1️⃣  Hash Chain Verification:")
        self.verify_hash_chain()
        status = "✓ PASS" if self.results['hash_chain']['valid'] else "✗ FAIL"
        print(f"   {status}")
        
        print("\n2️⃣  Sequence Verification:")
        self.verify_sequence()
        status = "✓ PASS" if self.results['sequence']['valid'] else "✗ FAIL"
        print(f"   {status}")
        
        print("\n3️⃣  Timestamp Verification:")
        self.verify_timestamps()
        status = "✓ PASS" if self.results['timestamps']['valid'] else "✗ FAIL"
        print(f"   {status}")
        
        print("\n4️⃣  Schema Verification:")
        self.verify_schema()
        status = "✓ PASS" if self.results['schema']['valid'] else "✗ FAIL"
        print(f"   {status}")
        
        # Overall result
        all_valid = all(self.results[k]['valid'] for k in 
                       ['hash_chain', 'sequence', 'timestamps', 'schema'])
        self.results['overall']['valid'] = all_valid
        
        return all_valid
    
    def print_report(self) -> None:
        """Print detailed verification report."""
        print("\n" + "=" * 70)
        print("VERIFICATION REPORT")
        print("=" * 70)
        
        if self.results['overall']['tamper_detected']:
            print("\n🚨 TAMPERING DETECTED IN AUDIT CHAIN 🚨\n")
            print("Possible causes:")
            print("  - Entry data was modified")
            print("  - Entry was deleted")
            print("  - Entries were reordered")
            print("\nImmediately investigate and take action!")
        elif self.results['overall']['valid']:
            print("\n✅ CHAIN INTEGRITY VERIFIED ✅\n")
            print(f"All {len(self.entries)} entries verified successfully.")
            print("No tampering detected.")
            print("Chain is tamper-evident and trustworthy.")
        else:
            print("\n⚠️  CHAIN VALIDATION ISSUES ⚠️\n")
        
        # Print errors by category
        for category in ['hash_chain', 'sequence', 'timestamps', 'schema']:
            errors = self.results[category]['errors']
            if errors:
                print(f"\n{category.upper()} ERRORS ({len(errors)}):")
                for error in errors:
                    print(f"  - {error}")
        
        print("\n" + "=" * 70)
    
    def print_statistics(self) -> None:
        """Print chain statistics."""
        if not self.entries:
            return
        
        print("\n" + "=" * 70)
        print("CHAIN STATISTICS")
        print("=" * 70)
        
        operations = defaultdict(int)
        for entry in self.entries:
            op = entry.get('operation', 'unknown')
            operations[op] += 1
        
        print(f"\n📊 Operations by type:")
        for op, count in sorted(operations.items()):
            print(f"  {op}: {count}")
        
        # First and last entry
        if self.entries:
            first = self.entries[0]
            last = self.entries[-1]
            
            print(f"\n⏰ Timespan:")
            print(f"  First: {first.get('timestamp', 'N/A')}")
            print(f"  Last:  {last.get('timestamp', 'N/A')}")
            print(f"  Total: {len(self.entries)} entries")
        
        print("\n" + "=" * 70)
    
    def export_report(self, output_path: str) -> None:
        """Export results as JSON."""
        report = {
            'verification_timestamp': datetime.utcnow().isoformat() + 'Z',
            'chain_file': str(self.log_path),
            'total_entries': len(self.entries),
            'results': self.results,
            'summary': {
                'overall_valid': self.results['overall']['valid'],
                'tamper_detected': self.results['overall']['tamper_detected'],
                'total_errors': sum(len(self.results[k]['errors']) 
                                    for k in self.results if k != 'overall')
            }
        }
        
        try:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Report exported to: {output_path}")
        except Exception as e:
            print(f"\n✗ Error exporting report: {e}", file=sys.stderr)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Sakura Chain Verifier - Comprehensive audit chain verification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 verify_chain.py --log audit_chain.jsonl
  python3 verify_chain.py --log audit_chain.jsonl --verbose
  python3 verify_chain.py --log audit_chain.jsonl --export report.json
  python3 verify_chain.py --log audit_chain.jsonl --stats
        """
    )
    
    parser.add_argument('--log', type=str, required=True,
                        help='Path to audit chain JSONL file')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable detailed output')
    parser.add_argument('--export', type=str,
                        help='Export results to JSON file')
    parser.add_argument('--stats', action='store_true',
                        help='Print chain statistics')
    
    args = parser.parse_args()
    
    # Run verification
    verifier = ChainVerifier(args.log, verbose=args.verbose)
    is_valid = verifier.run_all_checks()
    
    # Print report
    verifier.print_report()
    
    # Print statistics
    if args.stats:
        verifier.print_statistics()
    
    # Export results
    if args.export:
        verifier.export_report(args.export)
    
    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
