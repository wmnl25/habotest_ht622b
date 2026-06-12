import csv
import json
from collections import defaultdict
from pathlib import Path

def analyze_captures(csv_file):
    """
    Analyze captured HT622B frames and derive digit decoding tables.
    """

    # Read all captured data
    rows = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} captured frames")

    # Build lookup tables: (position, context_hash) -> {byte_value: set of digits}
    # Context includes: byte14, mode, range, and other state flags that affect decoding

    def get_context(row):
        """Generate a context signature that affects digit decoding"""
        # Based on analysis, frame[14] is the primary context switch
        # But mode and range might also matter
        return (
            row['byte14'],
            row['mode'],
            row['byte4'],  # range byte
        )

    # Tables for each digit position
    tens_table = defaultdict(lambda: defaultdict(set))
    units_table = defaultdict(lambda: defaultdict(set))
    tenths_table = defaultdict(lambda: defaultdict(set))

    for row in rows:
        target = row['target_db']
        try:
            target_f = float(target)
        except:
            continue

        tens_dig = int(target_f // 10)
        units_dig = int(target_f % 10)
        tenths_dig = int((target_f * 10) % 10)

        ctx = get_context(row)

        tens_byte = int(row['byte7_tens'], 16)
        units_byte = int(row['byte8_units'], 16)
        tenths_byte = int(row['byte9_tenths'], 16)

        tens_table[ctx][tens_byte].add(tens_dig)
        units_table[ctx][units_byte].add(units_dig)
        tenths_table[ctx][tenths_byte].add(tenths_dig)

    # Analyze consistency: each byte should map to exactly ONE digit per context
    print("\n=== CONSISTENCY CHECK ===")

    def check_consistency(table, name):
        conflicts = []
        unambiguous = {}
        for ctx, byte_map in table.items():
            for byte, digits in byte_map.items():
                if len(digits) > 1:
                    conflicts.append((ctx, byte, digits))
                else:
                    if ctx not in unambiguous:
                        unambiguous[ctx] = {}
                    unambiguous[ctx][byte] = list(digits)[0]

        print(f"\n{name}:")
        print(f"  Total contexts: {len(table)}")
        print(f"  Unambiguous mappings: {sum(len(m) for m in unambiguous.values())}")
        print(f"  Conflicts: {len(conflicts)}")

        if conflicts:
            print(f"  Conflicting mappings (need more data to resolve):")
            for ctx, byte, digits in conflicts[:5]:
                print(f"    Context {ctx}: byte 0x{byte:02X} -> digits {digits}")

        return unambiguous, conflicts

    tens_map, tens_conflicts = check_consistency(tens_table, "TENS")
    units_map, units_conflicts = check_consistency(units_table, "UNITS")
    tenths_map, tenths_conflicts = check_consistency(tenths_table, "TENTHS")

    # Generate decoder code
    print("\n=== GENERATED DECODER ===")

    decoder_code = generate_decoder(tens_map, units_map, tenths_map)
    print(decoder_code)

    # Save to file
    with open('ht622b_decoder_generated.py', 'w') as f:
        f.write(decoder_code)

    # Save mapping as JSON for inspection
    mapping = {
        'tens': {str(k): {f"0x{b:02X}": d for b, d in v.items()} for k, v in tens_map.items()},
        'units': {str(k): {f"0x{b:02X}": d for b, d in v.items()} for k, v in units_map.items()},
        'tenths': {str(k): {f"0x{b:02X}": d for b, d in v.items()} for k, v in tenths_map.items()},
    }

    with open('ht622b_mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)

    print("\nSaved decoder to ht622b_decoder_generated.py")
    print("Saved mapping to ht622b_mapping.json")

    # Report coverage gaps
    print("\n=== COVERAGE GAPS ===")
    report_gaps(tens_map, units_map, tenths_map)

    return tens_map, units_map, tenths_map


def generate_decoder(tens_map, units_map, tenths_map):
    """Generate a Python decoder function from the mappings"""

    code = """# AUTO-GENERATED HT622B DECODER
# Generated from captured data analysis
# Do not edit manually - regenerate from new captures instead

TENS_MAP = """
    code += repr(tens_map) + "

"

    code += "UNITS_MAP = "
    code += repr(units_map) + "

"

    code += "TENTHS_MAP = "
    code += repr(tenths_map) + "

"

    code += 