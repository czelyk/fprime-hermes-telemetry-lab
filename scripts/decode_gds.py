"""Headless use of full pinned GDS imports, loaders and telemetry decoders.

No stub imports or invented dictionaries. The optional eager flag is an explicit
competent comparison for the previously observed terminal continuation behavior.
"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/fprime-gds/src'))
from fprime_gds.common.models.dictionaries import Dictionaries
from fprime_gds.common.decoders.pkt_decoder import PktDecoder
from fprime_gds.common.decoders.ch_decoder import ChDecoder
from fprime_gds.common.decoders.event_decoder import EventDecoder
from fprime_gds.common.decoders.file_decoder import FileDecoder
from fprime_gds.common.communication.ccsds.chain import SpacePacketSpaceDataLinkFramerDeframer
from fprime_gds.common.communication.ccsds.space_data_link import SpaceDataLinkFramerDeframer


def normalize(t, value, types):
    if t['kind'] != 'qualifiedIdentifier':
        return value
    definition = types[t['name']]
    kind = definition['kind']
    if kind == 'alias':
        return normalize(definition['underlyingType'], value, types)
    if kind == 'enum':
        return {x['name']: x['value'] for x in definition['enumeratedConstants']}[value]
    if kind == 'array':
        return [normalize(definition['elementType'], v, types) for v in value]
    if kind == 'struct':
        result = {}
        for key, field in definition['members'].items():
            result[key] = ([normalize(field['type'], v, types) for v in value[key]]
                           if 'size' in field else normalize(field['type'], value[key], types))
        return result
    raise ValueError(definition)


class EagerSpaceDataLink(SpaceDataLinkFramerDeframer):
    def reassemble(self, field, first_header_pointer, vc_count):
        result = super().reassemble(field, first_header_pointer, vc_count)
        if first_header_pointer == self.FHP_NO_PACKET_START and self.pending:
            complete, partial = self.split_complete_packets(self.pending)
            self.pending = partial
            result += complete
        return result


class EagerChain(SpacePacketSpaceDataLinkFramerDeframer):
    @classmethod
    def get_composites(cls):
        return super().get_composites()[:-1] + [EagerSpaceDataLink]


def decode(args):
    source = json.loads(args.dictionary.read_text(encoding='utf-8'))
    types = {t['qualifiedName']: t for t in source['typeDefinitions']}
    channels = {c['name']: c for c in source['telemetryChannels']}
    dictionaries = Dictionaries.load_dictionaries_into_config(str(args.dictionary))
    pkt = PktDecoder(dictionaries.packet, dictionaries.channel_id)
    ch = ChDecoder(dictionaries.channel_id)
    evr = EventDecoder(dictionaries.event_id)
    file_decoder = FileDecoder()
    chain = (EagerChain if args.eager else SpacePacketSpaceDataLinkFramerDeframer)(
        scid=None, vcid=1, frame_size=None)
    counts = collections.Counter()
    remaining = b''
    with args.input.open('rb') as incoming, args.output.open('w', encoding='utf-8') as output:
        def emit(record):
            output.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
        while data := incoming.read(args.chunk_size):
            packets, remaining, discarded = chain.deframe_all(remaining + data, False)
            counts['discarded_bytes'] += len(discarded)
            for raw in packets:
                counts['packets'] += 1
                emit(dict(kind='packet', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
                descriptor = int.from_bytes(raw[:2], 'big')
                if descriptor == 4:
                    decoded = pkt.decode_api(raw[2:])
                elif descriptor == 1:
                    decoded = ch.decode_api(raw[2:])
                elif descriptor == 2:
                    if evr.decode_api(raw[2:]) is None:
                        raise RuntimeError('Event decoder returned no event')
                    counts['events'] += 1
                    decoded = []
                elif descriptor == 3:
                    file_packets = file_decoder.decode_api(raw[2:])
                    if not file_packets:
                        raise RuntimeError('File decoder returned no packet')
                    for part in file_packets:
                        counts['file_packets'] += 1
                        record = dict(sequence=part.seqID)
                        if part.packetType.name == 'START':
                            record.update(kind='file_start', size=part.size)
                        elif part.packetType.name == 'DATA':
                            record.update(kind='file_data', offset=part.offset, data_hex=part.dataVar.hex())
                        elif part.packetType.name == 'END':
                            record.update(kind='file_end', crc32=part.hashValue[0])
                        else:
                            record.update(kind='file_cancel')
                        emit(record)
                    decoded = []
                else:
                    counts['other'] += 1
                    decoded = []
                if decoded is None:
                    raise RuntimeError('Telemetry decoder returned no data')
                for c in decoded:
                    name = c.template.get_full_name()
                    value = normalize(channels[name]['type'], c.get_val(), types)
                    t = c.time.to_jsonable()
                    emit(dict(kind='channel', name=name, value=value, base=t['base'], context=t['context'],
                              seconds=t['seconds'], microseconds=t['microseconds']))
                    counts['channels'] += 1
    result = dict(decoded=dict(counts), remaining_stream_bytes=len(remaining),
                  pending_packet_bytes=len(chain.deframers[0].pending), eager_completion=args.eager,
                  gds_source=__import__('fprime_gds').__path__[0], scope='full imports and dictionary decoders; headless, no GDS web UI')
    args.stats.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dictionary', type=Path, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--stats', type=Path, required=True)
    p.add_argument('--chunk-size', type=int, default=113)
    p.add_argument('--eager', action='store_true')
    decode(p.parse_args())
