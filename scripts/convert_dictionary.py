"""Convert FPP JSON to Hermes protobuf JSON for the local headless receiver.

Wire types follow Hermes' pinned src/extensions/fprime/src/dictionary/json.ts.
This adapter is local lab code; it is not the Hermes VS Code dictionary loader.
All types, commands, channels, events, parameters and packet sets are retained.
"""
import argparse
import json
import re
from pathlib import Path

STRING_LENGTH_TYPE = 'UINT_U16'

def wire_type(t):
    kind = t['kind']
    if kind == 'integer':
        bits = t['size']
        if bits not in (8, 16, 32, 64):
            raise ValueError(f'Unsupported integer: {t}')
        return {'int': {'kind': f"INT_{'I' if t.get('signed') else 'U'}{bits}"}}
    if kind == 'float':
        if t['size'] not in (32, 64):
            raise ValueError(f'Unsupported float: {t}')
        return {'float': {'kind': f"F_F{t['size']}"}}
    if kind == 'bool':
        return {'bool': {'encodeType': 'UINT_U8'}}
    if kind == 'string':
        return {'string': {'lengthType': STRING_LENGTH_TYPE, 'maxLength': t.get('size', 0)}}
    if kind == 'qualifiedIdentifier':
        return {'ref': {'name': t['name']}}
    raise ValueError(f'Unsupported descriptor: {t}')


def named(item):
    component, name = item['name'].rsplit('.', 1)
    return {'component': component, 'name': name}


def fields(params):
    return [{'name': x['name'], 'type': wire_type(x['type'])} for x in params]


def convert(src):
    global STRING_LENGTH_TYPE
    size_type = next((t['underlyingType'] for t in src.get('typeDefinitions', [])
                      if t['qualifiedName'] == 'FwSizeStoreType'),
                     {'kind': 'integer', 'size': 16, 'signed': False})
    if size_type['kind'] != 'integer' or size_type.get('signed') or size_type['size'] not in (8, 16, 32, 64):
        raise ValueError(f'Unsupported string size type: {size_type}')
    STRING_LENGTH_TYPE = f"UINT_U{size_type['size']}"
    types = {}
    for t in src.get('typeDefinitions', []):
        name = t['qualifiedName']
        if t['kind'] == 'alias':
            types[name] = wire_type(t['underlyingType'])
        elif t['kind'] == 'enum':
            types[name] = {'enum': {
                'name': name,
                'encodeType': wire_type(t['representationType'])['int']['kind'],
                'items': [{'name': x['name'], 'value': x['value']} for x in t['enumeratedConstants']],
            }}
        elif t['kind'] == 'array':
            types[name] = {'array': {'name': name, 'static': t['size'],
                                     'elType': wire_type(t['elementType'])}}
        elif t['kind'] == 'struct':
            members = []
            for key, value in sorted(t['members'].items(), key=lambda x: x[1]['index']):
                ty = wire_type(value['type'])
                if 'size' in value:
                    ty = {'array': {'static': value['size'], 'elType': ty}}
                members.append({'name': key, 'type': ty})
            types[name] = {'object': {'name': name, 'fields': members}}
        else:
            raise ValueError(f'Unsupported typedef: {t}')

    tlm = {x['name']: dict(named(x), id=x['id'], type=wire_type(x['type']))
           for x in src.get('telemetryChannels', [])}
    severity = dict(DIAGNOSTIC='EVR_DIAGNOSTIC', ACTIVITY_LO='EVR_ACTIVITY_LOW',
                    ACTIVITY_HI='EVR_ACTIVITY_HIGH', WARNING_LO='EVR_WARNING_LOW',
                    WARNING_HI='EVR_WARNING_HIGH', COMMAND='EVR_COMMAND', FATAL='EVR_FATAL')
    evr = {}
    for x in src.get('events', []):
        fmt = re.sub(r'{(\d*\.?\d*[cdxoefgCDXOEFG])}', r'%\1', x.get('format', '')).replace('{}', '%v')
        evr[x['name']] = dict(named(x), id=x['id'], severity=severity[x['severity']],
                              formatString=fmt, arguments=fields(x['formalParams']))
    commands = {}
    for x in src.get('commands', []):
        n = named(x)
        commands[x['name']] = dict(component=n['component'], mnemonic=n['name'],
                                   opcode=x['opcode'], arguments=fields(x['formalParams']))
    parameters = {x['name']: dict(named(x), id=x['id'], type=wire_type(x['type']))
                  for x in src.get('parameters', [])}
    packets = {}
    for packet_set in src.get('telemetryPacketSets', []):
        for pkt in packet_set['members']:
            members = [{'name': key, 'type': tlm[key]['type']} for key in pkt['members']]
            packets[pkt['name']] = dict(name=pkt['name'], component='_', id=pkt['id'],
                type={'object': {'name': pkt['name'], 'fields': members}})
    metadata = {}
    for c in src.get('constants', []):
        if c['qualifiedName'] == 'ComCfg.SpacecraftId':
            metadata['SpacecraftId'] = str(c['value'])
    return {
        'head': {'type': 'fprime', 'name': src.get('metadata', {}).get('deploymentName', 'Ref')},
        'content': {'': dict(types=types, telemetry=tlm, events=evr, commands=commands, parameters=parameters),
                    'telemetry-packets': dict(types=types, telemetry=packets)},
        'metadata': metadata,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    converted = convert(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(converted, indent=2), encoding='utf-8')
    print(json.dumps({k: len(v) for k, v in converted['content'][''].items()}))
