"""Font bootstrap behavior using tiny synthetic tables, never bundled real fonts."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import font_bootstrap as fonts
import design_library as library


def fixture_font(name):
    value = name.encode('utf-16-be')
    name_table = struct.pack('>9H', 0, 1, 18, 3, 1, 0x409, 6, len(value), 0) + value
    tables = {b'head': b'\0'*54, b'name': name_table, b'test': b'original-table-content'}
    result = bytearray(b'\x00\x01\x00\x00' + struct.pack('>4H', 3, 32, 1, 16))
    body = bytearray()
    start = 12 + 3*16
    for tag, data in sorted(tables.items()):
        result += struct.pack('>4sIII', tag, 0, start, len(data))
        padded = data+b'\0'*(-len(data)%4)
        body += padded
        start += len(padded)
    return bytes(result+body)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='albumgenie-font-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root/'design-library/foundations/fonts'
        self.directory.mkdir(parents=True)
        self.raw = fixture_font('FixturePreview')
        self.expected = fonts.extract_sfnt(self.raw, 'FixturePreview')
        compressor = zlib.compressobj(wbits=-15)
        self.compressed = compressor.compress(self.raw)+compressor.flush()
        license_data = b'Test license notice\n'
        (self.directory/'LICENSE.txt').write_bytes(license_data)
        item = {'id':'W8', 'file':'Fixture.ttf', 'postscriptName':'FixturePreview',
                'bytes':len(self.expected), 'sha256':fonts.digest(self.expected),
                'sourceMember':'Fixture.ttc', 'sourceBytes':len(self.raw), 'sourceSha256':fonts.digest(self.raw),
                'download':{'rangeStart':100,'rangeEnd':99+len(self.compressed),
                            'bytes':len(self.compressed),'sha256':fonts.digest(self.compressed)}}
        self.manifest = {'schemaVersion':1,'source':{'archiveUrl':'https://github.com/example/fonts.zip',
                         'archiveBytes':100000,'licenseFile':'LICENSE.txt','licenseSha256':fonts.digest(license_data)},
                         'fonts':[item]}
        self.save_manifest()

    def save_manifest(self):
        (self.directory/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')

    def test_first_use_fetches_then_reuses_cache_without_network_or_file_changes(self):
        with patch.object(fonts,'fetch_range',return_value=self.compressed) as network:
            first = fonts.ensure(self.root)
            stamp = (self.directory/'Fixture.ttf').stat().st_mtime_ns
            second = fonts.ensure(self.root)
        self.assertEqual(network.call_count,1)
        self.assertEqual(first['downloaded'],['W8'])
        self.assertEqual(second['downloaded'],[])
        self.assertEqual((self.directory/'Fixture.ttf').stat().st_mtime_ns,stamp)
        self.assertTrue(second['ready'])

    def test_offline_missing_cache_never_fetches(self):
        with patch.object(fonts,'fetch_range',side_effect=AssertionError('Network forbidden')) as network:
            with self.assertRaises(fonts.FontError): fonts.ensure(self.root,offline=True)
        network.assert_not_called()
        self.assertFalse((self.root/'.local').exists())

    def test_download_failure_preserves_existing_file(self):
        target=self.directory/'Fixture.ttf'
        target.write_bytes(b'existing-file')
        with patch.object(fonts,'fetch_range',side_effect=fonts.FontError('download failed')):
            with self.assertRaises(fonts.FontError): fonts.ensure(self.root)
        self.assertEqual(target.read_bytes(),b'existing-file')
        self.assertEqual(list((self.root/'.local/font-downloads').iterdir()),[])

    def test_source_checksum_mismatch_does_not_install(self):
        self.manifest['fonts'][0]['sourceSha256']='0'*64
        self.save_manifest()
        with patch.object(fonts,'fetch_range',return_value=self.compressed):
            with self.assertRaisesRegex(fonts.FontError,'collection failed SHA256'): fonts.ensure(self.root)
        self.assertFalse((self.directory/'Fixture.ttf').exists())

    def test_prepared_checksum_mismatch_does_not_install(self):
        self.manifest['fonts'][0]['sha256']='0'*64
        self.save_manifest()
        with patch.object(fonts,'fetch_range',return_value=self.compressed):
            with self.assertRaisesRegex(fonts.FontError,'Prepared preview font failed SHA256'): fonts.ensure(self.root)
        self.assertFalse((self.directory/'Fixture.ttf').exists())

    def test_offline_archive_reads_only_declared_member(self):
        archive=self.root/'source.zip'
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('Fixture.ttc',self.raw)
            out.writestr('../unexpected-file.txt',b'must not be extracted')
        with patch.object(fonts,'fetch_range',side_effect=AssertionError('Network forbidden')):
            result=fonts.ensure(self.root,offline=True,archive=archive)
        self.assertTrue(result['ready'])
        self.assertFalse((self.root/'unexpected-file.txt').exists())

    def test_face_selection_uses_postscript_name_and_preserves_table_content(self):
        wrong=bytearray(fixture_font('WrongFace'))
        right=bytearray(self.raw)
        offset1=20
        offset2=20+len(wrong)
        for data,base in ((wrong,offset1),(right,offset2)):
            for i in range(3):
                start=struct.unpack_from('>I',data,12+i*16+8)[0]
                struct.pack_into('>I',data,12+i*16+8,start+base)
        collection=struct.pack('>4s4I',b'ttcf',0x10000,2,offset1,offset2)+wrong+right
        result=fonts.extract_sfnt(collection,'FixturePreview')
        self.assertIn('FixturePreview'.encode('utf-16-be'),result)
        self.assertNotIn('WrongFace'.encode('utf-16-be'),result)
        self.assertIn(b'original-table-content',result)
        self.assertEqual(fonts.checksum(result),0xb1b0afba)

    def test_manifest_cannot_escape_font_cache(self):
        self.manifest['fonts'][0]['file']='../outside.ttf'
        self.save_manifest()
        with self.assertRaises(fonts.FontError): fonts.status(self.root)

    def test_range_download_rejects_full_response_and_wrong_hash(self):
        spec=self.manifest['fonts'][0]['download']
        for status,data in ((200,self.compressed),(206,b'x'*len(self.compressed))):
            with self.subTest(status=status):
                response=io.BytesIO(data)
                response.status=status
                with patch.dict(os.environ,{},clear=True),patch.object(fonts,'urlopen',return_value=response):
                    with self.assertRaises(fonts.FontError):
                        fonts.fetch_range('https://example.invalid/source.zip',spec,self.root/'download.part')


class OfflineLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='albumgenie-library-fonts-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        shutil.copytree(ROOT/'design-library',self.root/'design-library',
                        ignore=shutil.ignore_patterns('v1','*.ttf','*.woff','*.woff2'))
        for name,value in (('ROOT',self.root),('LIBRARY',self.root/'design-library')):
            p=patch.object(library,name,value)
            p.start()
            self.addCleanup(p.stop)

    def test_static_check_allows_missing_declared_fonts_but_requires_them_on_request(self):
        with patch.object(fonts,'fetch_range',side_effect=AssertionError('Network forbidden')):
            self.assertTrue(library.check_library()['passed'])
            self.assertFalse(library.check_library(require_fonts=True)['passed'])

    def test_missing_nonfont_resource_still_fails(self):
        (self.root/'design-library/foundations/placeholders/office.svg').unlink()
        result=library.check_library()
        self.assertFalse(result['passed'])
        self.assertTrue(any('missing/outside dependency' in e for e in result['errors']))

    def test_offline_gallery_has_fallback_notice_and_does_not_download(self):
        with patch.object(fonts,'ensure',side_effect=AssertionError('Network forbidden')):
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                result=library.main(['gallery','--offline'])
        self.assertEqual(result,0)
        page=(self.root/'.local/previews/component-catalog.html').read_text(encoding='utf-8')
        self.assertIn('系统字体',page)

    def test_offline_gallery_rejects_corrupt_cached_fonts(self):
        target=self.root/'design-library/foundations/fonts/DreamHanSansSC-W8.ttf'
        target.write_bytes(b'corrupt-cache')
        with contextlib.redirect_stderr(io.StringIO()): result=library.main(['gallery','--offline'])
        self.assertEqual(result,1)
        self.assertFalse((self.root/'.local/previews/component-catalog.html').exists())

    def test_normal_gallery_prepares_fonts_on_first_use(self):
        with patch.object(fonts,'ensure',return_value={'ready':True}) as prepare:
            with contextlib.redirect_stdout(io.StringIO()): result=library.main(['gallery'])
        self.assertEqual(result,0)
        prepare.assert_called_once()

    def test_failed_font_preparation_does_not_overwrite_an_existing_gallery(self):
        output=self.root/'.local/previews/component-catalog.html'
        output.parent.mkdir(parents=True)
        output.write_text('previous-gallery',encoding='utf-8')
        with patch.object(fonts,'ensure',side_effect=fonts.FontError('download failed')):
            with contextlib.redirect_stderr(io.StringIO()): result=library.main(['gallery'])
        self.assertEqual(result,1)
        self.assertEqual(output.read_text(encoding='utf-8'),'previous-gallery')


if __name__=='__main__': unittest.main()
