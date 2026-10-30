"""Fetch pinned upstream font ranges into the ignored preview font cache.

Only metadata and this code are distributed. No fonts are fetched on import.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile
import zlib


class FontError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checksum(data):
    padded = data + b'\0' * (-len(data) % 4)
    return sum(value[0] for value in struct.iter_unpack('>I', padded)) & 0xffffffff


def face_tables(data, offset):
    if offset < 0 or offset + 12 > len(data):
        raise FontError('Invalid font offset')
    count = struct.unpack_from('>H', data, offset + 4)[0]
    if not 0 < count < 256 or offset + 12 + count * 16 > len(data):
        raise FontError('Invalid font table directory')
    tables = {}
    for i in range(count):
        tag, _, start, length = struct.unpack_from('>4sIII', data, offset + 12 + 16*i)
        if start + length > len(data) or tag in tables:
            raise FontError('Invalid font table bounds')
        tables[tag] = data[start:start+length]
    return tables


def postscript_names(table):
    if len(table) < 6:
        raise FontError('Invalid name table')
    _, count, strings = struct.unpack_from('>HHH', table)
    names = set()
    for i in range(count):
        if 6 + (i+1)*12 > len(table):
            raise FontError('Invalid name records')
        platform, _, _, name_id, length, start = struct.unpack_from('>6H', table, 6+i*12)
        if name_id == 6:
            raw = table[strings+start:strings+start+length]
            names.add(raw.decode('utf-16-be' if platform in (0, 3) else 'mac_roman'))
    return names


def extract_sfnt(data, postscript_name):
    """Copy one TTC face into a standalone SFNT; preserve all tables except head checksum."""
    if data[:4] == b'ttcf':
        count = struct.unpack_from('>I', data, 8)[0]
        if not 0 < count <= 64 or 12 + count*4 > len(data):
            raise FontError('Invalid font collection')
        offsets = struct.unpack_from('>' + 'I'*count, data, 12)
    else:
        offsets = [0]
    selected = None
    for offset in offsets:
        tables = face_tables(data, offset)
        if postscript_name in postscript_names(tables.get(b'name', b'')):
            selected = (offset, tables)
            break
    if selected is None:
        raise FontError(f'Upstream collection has no {postscript_name}')
    offset, tables = selected
    head = bytearray(tables.get(b'head', b''))
    if len(head) < 12:
        raise FontError('Font has no valid head table')
    head[8:12] = b'\0'*4
    tables[b'head'] = bytes(head)
    count = len(tables)
    power = 2 ** (count.bit_length()-1)
    header = data[offset:offset+4] + struct.pack('>4H', count, 16*power, power.bit_length()-1, 16*(count-power))
    directory = bytearray()
    body = bytearray()
    start = 12 + count*16
    head_start = None
    for tag, value in sorted(tables.items()):
        directory += struct.pack('>4sIII', tag, checksum(value), start, len(value))
        if tag == b'head':
            head_start = start
        padded = value + b'\0' * (-len(value) % 4)
        body += padded
        start += len(padded)
    output = bytearray(header + directory + body)
    struct.pack_into('>I', output, head_start+8, (0xb1b0afba-checksum(output)) & 0xffffffff)
    return bytes(output)


def load_manifest(root):
    font_dir = Path(root) / 'design-library/foundations/fonts'
    manifest = json.loads((font_dir/'manifest.json').read_text(encoding='utf-8'))
    url = urlsplit(manifest['source']['archiveUrl'])
    if manifest['schemaVersion'] != 1 or url.scheme != 'https' or url.hostname != 'github.com':
        raise FontError('Unsupported font manifest or source')
    license_file = font_dir/manifest['source']['licenseFile']
    if license_file.parent != font_dir or not license_file.is_file() or digest(license_file.read_bytes()) != manifest['source']['licenseSha256']:
        raise FontError('Font license notice failed validation')
    ids = set()
    for font in manifest['fonts']:
        if font['id'] in ids or Path(font['file']).name != font['file'] or not font['file'].endswith('.ttf'):
            raise FontError('Invalid font cache name')
        ids.add(font['id'])
        item = font['download']
        if (item['rangeEnd'] - item['rangeStart'] + 1 != item['bytes'] or item['rangeStart'] < 0
                or item['rangeEnd'] >= manifest['source']['archiveBytes']):
            raise FontError('Invalid pinned download range')
        for value in (font['sha256'], font['sourceSha256'], item['sha256']):
            if not re.fullmatch('[a-f0-9]{64}', value):
                raise FontError('Font source requires fixed SHA256 values')
    if not ids:
        raise FontError('Empty font manifest')
    return font_dir, manifest


def status(root):
    font_dir, manifest = load_manifest(root)
    result = []
    for font in manifest['fonts']:
        path = font_dir/font['file']
        state = 'missing'
        if path.is_file():
            state = 'ready' if path.stat().st_size == font['bytes'] and digest(path.read_bytes()) == font['sha256'] else 'corrupt'
        result.append({'id': font['id'], 'file': font['file'], 'state': state})
    return {'ready': all(f['state'] == 'ready' for f in result), 'fonts': result}


def fetch_range(url, spec, output):
    """Use a positive HTTP range; reject ignored ranges and unverified bytes."""
    byte_range = f'{spec["rangeStart"]}-{spec["rangeEnd"]}'
    socks = any(urlsplit(os.environ.get(k, '')).scheme.startswith('socks') for k in
                ('HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy'))
    if socks:
        curl = shutil.which('curl.exe') or shutil.which('curl')
        if not curl:
            raise FontError('SOCKS proxy requires curl; use an HTTP proxy or --archive for offline preparation')
        result = subprocess.run([curl, '--location', '--fail', '--silent', '--show-error', '--connect-timeout', '15',
                                 '--max-time', '180', '--range', byte_range, '--max-filesize', str(spec['bytes']),
                                 '--output', str(output), '--write-out', '%{http_code}', url],
                                capture_output=True, text=True)
        if result.returncode or result.stdout.strip() != '206':
            raise FontError('Upstream range download failed; check the network/proxy or use --archive')
    else:
        request = Request(url, headers={'Range': 'bytes='+byte_range, 'Accept-Encoding': 'identity',
                                        'User-Agent': 'AlbumGenie-font-bootstrap'})
        with urlopen(request, timeout=60) as response, output.open('wb') as target:
            if response.status != 206:
                raise FontError('Server did not honor the font byte range; use --archive')
            received = 0
            while chunk := response.read(256*1024):
                received += len(chunk)
                if received > spec['bytes']:
                    raise FontError('Font download exceeds its declared size')
                target.write(chunk)
    data = output.read_bytes()
    if len(data) != spec['bytes'] or digest(data) != spec['sha256']:
        raise FontError('Downloaded font range failed SHA256 or size validation')
    return data


def ensure(root, *, offline=False, archive=None, progress=None):
    font_dir, manifest = load_manifest(root)
    current = status(root)
    missing = {f['id'] for f in current['fonts'] if f['state'] != 'ready'}
    if not missing:
        return {**current, 'downloaded': []}
    if offline and archive is None:
        raise FontError('Preview fonts are not cached. Run fonts, supply --archive, or use gallery --offline for system fonts.')
    work = Path(root)/'.local/font-downloads'
    work.mkdir(parents=True, exist_ok=True)
    staged = []
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=work) as temporary:
        temporary = Path(temporary)
        for font in manifest['fonts']:
            if font['id'] not in missing:
                continue
            if progress:
                progress(f'Preparing {font["postscriptName"]} from pinned upstream source')
            if archive is not None:
                try:
                    with zipfile.ZipFile(archive) as source:
                        info = source.getinfo(font['sourceMember'])
                        if info.file_size != font['sourceBytes']:
                            raise FontError('Offline font collection size mismatch')
                        raw = source.read(info)
                except (zipfile.BadZipFile, KeyError) as error:
                    raise FontError('Offline archive is invalid or has no required font collection') from error
            else:
                compressed = fetch_range(manifest['source']['archiveUrl'], font['download'], temporary/(font['id']+'.deflate'))
                decoder = zlib.decompressobj(-15)
                raw = decoder.decompress(compressed, font['sourceBytes']+1)
                if not decoder.eof or decoder.unused_data or len(raw) != font['sourceBytes']:
                    raise FontError('Invalid compressed font collection')
            if digest(raw) != font['sourceSha256']:
                raise FontError('Upstream font collection failed SHA256 validation')
            data = extract_sfnt(raw, font['postscriptName'])
            if len(data) != font['bytes'] or digest(data) != font['sha256']:
                raise FontError('Prepared preview font failed SHA256 validation')
            path = temporary/font['file']
            path.write_bytes(data)
            staged.append((path, font_dir/font['file']))
        for source, target in staged:
            os.replace(source, target)
    return {**status(root), 'downloaded': sorted(missing)}
