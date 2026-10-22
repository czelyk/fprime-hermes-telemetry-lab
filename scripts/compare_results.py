"""Strict semantic comparison of packet order and decoded values/timestamps."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def freeze(x):
    if isinstance(x, dict):
        return tuple(sorted((k, freeze(v)) for k, v in x.items()))
    if isinstance(x, list):
        return tuple(map(freeze, x))
    return x


def load(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def recovered(records, expected):
    starts = [x for x in records if x['kind'] == 'file_start']
    ends = [x for x in records if x['kind'] == 'file_end']
    chunks = sorted((x for x in records if x['kind'] == 'file_data'), key=lambda x: x['offset'])
    if len(starts) != 1 or len(ends) != 1:
        return {'complete': False, 'reason': 'not exactly one file start and end'}
    content = bytearray()
    for chunk in chunks:
        if chunk['offset'] != len(content):
            return {'complete': False, 'reason': 'gap, overlap or duplicate in file chunks'}
        content.extend(bytes.fromhex(chunk['data_hex']))
    actual_hash = hashlib.sha256(content).hexdigest()
    expected_hash = hashlib.sha256(expected.read_bytes()).hexdigest()
    return dict(complete=(len(content) == starts[0]['size'] and actual_hash == expected_hash),
                bytes=len(content), sha256=actual_hash, expected_sha256=expected_hash)


def compare(args):
    a, b = load(args.hermes), load(args.gds)
    packet_a = [x for x in a if x['kind'] == 'packet']
    packet_b = [x for x in b if x['kind'] == 'packet']
    channels_a = collections.Counter(freeze(x) for x in a if x['kind'] == 'channel')
    channels_b = collections.Counter(freeze(x) for x in b if x['kind'] == 'channel')
    all_a, all_b = collections.Counter(map(freeze, a)), collections.Counter(map(freeze, b))
    result = dict(packet_order_and_bytes_equal=(packet_a == packet_b),
        channel_values_and_timestamps_equal=(channels_a == channels_b),
        all_records_equal=(all_a == all_b), packets=len(packet_a), channel_measurements=sum(channels_a.values()),
        distinct_channels=len({x['name'] for x in a if x['kind'] == 'channel'}),
        hermes_only_records=sum((all_a-all_b).values()), gds_only_records=sum((all_b-all_a).values()))
    if args.reference:
        reference = load(args.reference)
        reference_records = collections.Counter(map(freeze, reference))
        reference_packets = iter(x for x in reference if x['kind'] == 'packet')
        ordered_subset = all(any(candidate == expected for expected in reference_packets) for candidate in packet_a)
        result['surviving_packets_are_ordered_originals'] = ordered_subset
        result['no_invented_decoded_records'] = not bool(all_a-reference_records)
        result['lost_packets_vs_reference'] = sum(x['kind'] == 'packet' for x in reference) - len(packet_a)
    if args.expected_file:
        result['hermes_file'] = recovered(a, args.expected_file)
        result['gds_file'] = recovered(b, args.expected_file)
    result['pass'] = result['all_records_equal'] and result['packet_order_and_bytes_equal']
    if args.expected_file:
        result['pass'] &= result['hermes_file']['complete'] and result['gds_file']['complete']
    if args.reference:
        result['pass'] &= result['surviving_packets_are_ordered_originals'] and result['no_invented_decoded_records']
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if not result['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--hermes', type=Path, required=True)
    p.add_argument('--gds', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--expected-file', type=Path)
    p.add_argument('--reference', type=Path)
    compare(p.parse_args())
