#!/usr/bin/env python3
"""Find static AlbumGenie components and check their local dependencies.

Python standard library only. Paths are resolved from this file, not cwd.
No production scripts, browsers, network requests or InDesign calls are run.
"""
from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import os
import font_bootstrap

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'design-library'
ID_RE = re.compile(r'[A-Z][0-9]{2}')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inside(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f'Path outside {base.name}: {relative}')
    return path


def shared_records():
    registry = read_json(LIBRARY / 'registry.json')
    records = []
    for entry in registry['components']:
        record = read_json(inside(LIBRARY, entry['metadata']))
        if record['id'] != entry['id']:
            raise ValueError(f'Registry ID mismatch: {entry["id"]}')
        record['_catalog'] = 'shared'
        record['_directory'] = inside(LIBRARY, entry['metadata']).parent
        records.append(record)
    return registry, records


def records(include_local=False):
    _, result = shared_records()
    ids = {r['id'] for r in result}
    if include_local:
        for path in sorted((LIBRARY / 'v1/assets').glob('*/metadata.json')):
            record = read_json(path)
            if record['id'] in ids:
                continue  # Shared revision takes precedence; legacy files stay intact.
            if not ID_RE.fullmatch(record['id']):
                raise ValueError(f'Invalid local ID: {record["id"]}')
            record['_catalog'] = 'local-v1'
            record['_directory'] = path.parent
            result.append(record)
            ids.add(record['id'])
    return sorted(result, key=lambda r: r['id'])


def native_status(record):
    return record.get('validation', {}).get('native', record.get('nativeMapping', {}).get('status', 'not-tested'))


def public_record(record):
    result = {k: v for k, v in record.items() if not k.startswith('_')}
    result['catalog'] = record['_catalog']
    result['directory'] = record['_directory'].relative_to(ROOT).as_posix()
    result['nativeStatus'] = native_status(record)
    return result


def select(all_records, args):
    result = []
    terms = (args.query or '').casefold().split()
    for record in all_records:
        if args.category and record['category'] != args.category:
            continue
        if args.subtype and record.get('subtype') != args.subtype:
            continue
        if args.native_verified and native_status(record) != 'verified':
            continue
        selection = record.get('selection', {})
        languages = selection.get('languages', [])
        if args.language and args.language not in languages:
            continue  # Unknown capacity is not asserted to be supported.
        count = selection.get('itemCount')
        if args.items is not None:
            if count is None or not count['min'] <= args.items <= count['max']:
                continue
        searchable = ' '.join(str(record.get(key, '')) for key in
                              ('id', 'name', 'category', 'subtype', 'tags', 'useWhen', 'contentCapacity')).casefold()
        if not all(term in searchable for term in terms):
            continue
        out = public_record(record)
        if args.width_mm is not None:
            width = record.get('contentFrameMm', record.get('frameMm', [None]))[0]
            out['widthAdvice'] = {
                'requestedMm': args.width_mm, 'demoMm': width,
                'requiresAdaptation': width is None or abs(args.width_mm - width) > .01,
                'note': 'Demo width is not a tested capacity limit; reflow and check actual content.'
            }
        result.append(out)
    return result


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'object', 'embed'):
            self.problems.append(f'Executable/embedded element: {tag}')
        for key, value in attrs:
            if key.lower().startswith('on'):
                self.problems.append(f'Event handler: {key}')
            if key in ('src', 'href', 'xlink:href') and value:
                self.paths.append(value)
            if key == 'style' and value:
                self.paths.extend(css_urls(value))


def css_urls(text):
    return [m.group(1).strip().strip('\"\'') for m in re.finditer(r'url\(\s*([^)]*?)\s*\)', text)]


def check_library(require_fonts=False):
    registry, all_records = shared_records()
    errors = []
    font_state = font_bootstrap.status(ROOT)
    font_dir, font_manifest = font_bootstrap.load_manifest(ROOT)
    managed_fonts = {(font_dir/font['file']).resolve() for font in font_manifest['fonts']}
    for font in font_state['fonts']:
        if font['state'] == 'corrupt' or (require_fonts and font['state'] != 'ready'):
            errors.append(f'Preview font {font["id"]}: {font["state"]}; run the fonts command')
    if registry.get('schemaVersion') != 1:
        errors.append('Unsupported registry schemaVersion')
    categories = {category['id'] for category in registry['categories']}
    ids = [record['id'] for record in all_records]
    if not ids or len(ids) != len(set(ids)):
        errors.append('Empty registry or duplicate component IDs')
    for category in registry['categories']:
        if category.get('count') != sum(r['category'] == category['id'] for r in all_records):
            errors.append(f'{category["id"]}: category count differs from registry entries')
    declared_metadata = set()
    for entry, record in zip(registry['components'], all_records):
        label = record['id']
        directory = record['_directory']
        declared_metadata.add(directory / 'metadata.json')
        if not ID_RE.fullmatch(label) or directory.name != label:
            errors.append(f'{label}: invalid ID or directory')
        if record['category'] not in categories:
            errors.append(f'{label}: unknown category')
        for key in ('name', 'useWhen', 'contentCapacity', 'slots', 'selection', 'nativeMapping', 'validation', 'distribution'):
            if not record.get(key):
                errors.append(f'{label}: missing {key}')
        if entry['metadata'] != f'components/{label}/metadata.json':
            errors.append(f'{label}: unexpected metadata path')
        for name in ('component.html', 'component.css', 'preview.html'):
            if not (directory / name).is_file():
                errors.append(f'{label}: missing {name}')
        if {f['path'] for f in record.get('files', [])} != {'component.html', 'component.css', 'preview.html'}:
            errors.append(f'{label}: file hash manifest must cover all component files')
        for item in record.get('files', []):
            path = inside(directory, item['path'])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                errors.append(f'{label}: missing or changed file {item["path"]}')
        for source in record.get('sourceReferences', []):
            if not inside(LIBRARY, source['licenseFile']).is_file():
                errors.append(f'{label}: missing source license')
    actual_metadata = set((LIBRARY / 'components').glob('*/metadata.json'))
    if actual_metadata != declared_metadata:
        errors.append('Registry and component directories differ')
    checked = 0
    for area in ('components', 'foundations'):
        for path in sorted((LIBRARY / area).rglob('*')):
            if path.suffix.lower() not in ('.html', '.css', '.svg', '.json'):
                continue
            checked += 1
            content = path.read_text(encoding='utf-8-sig')
            refs = []
            if path.suffix.lower() in ('.html', '.svg'):
                parser = References()
                parser.feed(content)
                refs += parser.paths
                errors += [f'{path.relative_to(LIBRARY)}: {p}' for p in parser.problems]
            if path.suffix.lower() == '.css':
                refs += css_urls(content)
            if re.search(r'(?i)(?:(?<![a-z0-9])[a-z]:[\\/]|file://|/Users/|/home/)', content):
                errors.append(f'{path.relative_to(LIBRARY)}: machine-specific path')
            for ref in refs:
                parsed = urlsplit(ref)
                if parsed.scheme == 'data' or ref.startswith('#'):
                    continue
                if parsed.scheme or parsed.netloc or ref.startswith('/'):
                    errors.append(f'{path.relative_to(LIBRARY)}: nonlocal dependency {ref}')
                    continue
                dependency = (path.parent / unquote(parsed.path)).resolve()
                if dependency in managed_fonts and not dependency.exists():
                    continue  # Declared first-use assets, not distributed source dependencies.
                if not dependency.is_relative_to(LIBRARY.resolve()) or not dependency.is_file():
                    errors.append(f'{path.relative_to(LIBRARY)}: missing/outside dependency {ref}')
    for source in read_json(LIBRARY / 'sources/manifest.json'):
        for item in source['files']:
            path = inside(LIBRARY, item['local'])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                errors.append(f'{source["id"]}: source evidence changed: {item["local"]}')
    return {'components': len(all_records), 'staticFilesChecked': checked, 'previewFonts': font_state,
            'errors': errors, 'passed': not errors,
            'scope': 'Local metadata, hashes and dependency checks only; no browser/native/visual verification.'}


def gallery(all_records, output, font_note=''):
    output = output.resolve()
    def link(path):
        from urllib.parse import quote
        return html.escape(quote(Path(os.path.relpath(path, output.parent)).as_posix()), quote=True)
    cards = []
    for record in all_records:
        directory = record['_directory']
        width, height = record['frameMm']
        px_w, px_h = width * 96 / 25.4 + 36, height * 96 / 25.4 + 36
        scale = min(288 / px_w, 175 / px_h)
        cards.append(f'''<article data-category="{html.escape(record['category'])}">
<div class="thumb"><iframe title="{html.escape(record['name'])}" loading="lazy" sandbox="allow-same-origin"
src="{link(directory / 'preview.html')}" style="width:{px_w:.2f}px;height:{px_h:.2f}px;transform:scale({scale:.5f})"></iframe></div>
<h2>{record['id']} · {html.escape(record['name'])}</h2>
<p class="meta">{html.escape(record['category'])} · {record['_catalog']} · native: {html.escape(native_status(record))}</p>
<p>{html.escape(record['useWhen'])}</p><p>{html.escape(record['contentCapacity'])}</p>
<a href="{link(directory / 'preview.html')}">原尺寸预览</a> ·
<a href="{link(directory / 'metadata.json')}">元数据</a> ·
<a href="{link(directory / 'component.html')}">组件源码</a></article>''')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>AlbumGenie 组件选型</title>
<style>body{margin:0;padding:32px;background:#f1f4f7;color:#203348;font:15px/1.65 system-ui,sans-serif}header{max-width:1000px;margin-bottom:24px}h1{margin:0}h2{font-size:17px;margin:12px 0 6px}.meta{font-size:12px;color:#5b6c7d}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:20px}article{background:white;padding:20px;border-radius:12px;border:1px solid #dbe1e7}p{margin:8px 0}a{color:#07559c}.thumb{height:180px;overflow:hidden;background:#f6f8fa}iframe{border:0;transform-origin:top left}</style>
<header><h1>AlbumGenie 组件选型</h1><p>先看内容角色、语种、数量、容量和图片比例。全部为候选，演示色与文案可替换；当前原生验证状态以各组件元数据为准。</p><p>此目录由本地工具生成，未进行浏览器或视觉验收。</p></header><main>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    if font_note:
        document = document.replace('</header>', '<p>'+html.escape(font_note)+'</p></header>')
    output.write_text(document + ''.join(cards) + '</main></html>\n', encoding='utf-8')
    return output


def positive_number(value):
    number = float(value)
    if not 0 < number < float('inf'):
        raise argparse.ArgumentTypeError('must be finite and positive')
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('list', 'select'):
        p = commands.add_parser(command)
        p.add_argument('--include-local', action='store_true')
        p.add_argument('--category')
        p.add_argument('--subtype')
        p.add_argument('--query')
        p.add_argument('--items', type=int)
        p.add_argument('--language', choices=('zh', 'bilingual', 'en'))
        p.add_argument('--width-mm', type=positive_number)
        p.add_argument('--native-verified', action='store_true')
        p.add_argument('--json', action='store_true')
    p = commands.add_parser('show')
    p.add_argument('id')
    p.add_argument('--include-local', action='store_true')
    p = commands.add_parser('check')
    p.add_argument('--require-fonts', action='store_true')
    p = commands.add_parser('fonts')
    p.add_argument('--status', action='store_true')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--archive', type=Path)
    p = commands.add_parser('gallery')
    p.add_argument('--include-local', action='store_true')
    p.add_argument('--output', type=Path, default=ROOT / '.local/previews/component-catalog.html')
    p.add_argument('--offline', action='store_true', help='Skip downloads; use system fonts when the cache is missing')
    p.add_argument('--font-archive', type=Path, help='Prepare fonts from an official archive downloaded separately')
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            result = check_library(args.require_fonts)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['passed'] else 1
        if args.command == 'fonts':
            result = font_bootstrap.status(ROOT) if args.status else font_bootstrap.ensure(
                ROOT, offline=args.offline, archive=args.archive, progress=lambda message: print(message, file=sys.stderr))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        all_records = records(getattr(args, 'include_local', False))
        if args.command in ('list', 'select'):
            selected = select(all_records, args)
            if args.json:
                print(json.dumps(selected, ensure_ascii=False, indent=2))
            else:
                for record in selected:
                    width = record.get('widthAdvice')
                    advice = ' | width: adapt + recheck' if width and width['requiresAdaptation'] else ''
                    print(f'{record["id"]} | {record["category"]} | {record["name"]} | {record["catalog"]} | native={record["nativeStatus"]}{advice}')
                print(f'{len(selected)} candidate(s). Capacity describes demo content, not a native production guarantee.')
        elif args.command == 'show':
            found = next((r for r in all_records if r['id'] == args.id.upper()), None)
            if found is None:
                parser.error('Unknown ID; local-only references require --include-local')
            print(json.dumps(public_record(found), ensure_ascii=False, indent=2))
        elif args.command == 'gallery':
            destination = args.output.resolve()
            for protected in ('components', 'foundations', 'sources', 'v1'):
                if destination.is_relative_to(LIBRARY / protected):
                    parser.error('Gallery output must not overwrite component or legacy sources')
            if destination.is_relative_to(ROOT) and not destination.is_relative_to(ROOT / '.local'):
                parser.error('Generated gallery inside the repo must be saved under .local/')
            note = ''
            if args.offline and args.font_archive is None:
                font_state = font_bootstrap.status(ROOT)
                if any(font['state'] == 'corrupt' for font in font_state['fonts']):
                    raise font_bootstrap.FontError('Cached preview font failed validation; run fonts to repair it before previewing.')
                if not font_state['ready']:
                    note = '部分预览字体未缓存，可能使用系统字体。运行 fonts 命令下载后，请重新检查排版效果。'
                    print(note, file=sys.stderr)
            else:
                font_bootstrap.ensure(ROOT, archive=args.font_archive, progress=lambda message: print(message, file=sys.stderr))
            print(gallery(all_records, destination, note))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Component library error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
