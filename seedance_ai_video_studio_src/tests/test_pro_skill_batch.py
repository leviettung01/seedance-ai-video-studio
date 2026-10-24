import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from dola_skill_automation import skill_metadata, SKILL_LABEL
from pro_skill_batch import ProSkillBatch, assign_prompts


class SkillAssetTests(unittest.TestCase):
    def test_uploaded_skill_metadata_and_dola_normalized_label(self):
        metadata = skill_metadata()
        self.assertEqual(metadata['name'], 'MianBrothers-seedance-2-5-30s')
        self.assertTrue(SKILL_LABEL.fullmatch('Mianbrothers Seedance 2 5 30s'))
        self.assertFalse(SKILL_LABEL.fullmatch('Another Seedance Skill'))

    def test_invalid_asset_is_rejected_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            file = pathlib.Path(directory) / 'SKILL.md'
            file.write_text('not a skill', encoding='utf-8')
            with self.assertRaises(ValueError):
                skill_metadata(file)


class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, actual=30, cancel_first=False):
        calls, completed, cleaned = [], [], []
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = pathlib.Path(temporary.name) / 'fixture.mp4'
        path.write_bytes(b'unit-test-fixture')
        class Browser:
            async def launch_temp_chrome(self, *a, **kw):
                self.assertions = kw
                if kw.get('proxy_url') != 'http://fixture.invalid:10000':
                    raise AssertionError('Pro must receive selected proxy')
                if not kw.get('load_extension'):
                    raise AssertionError('Pro Chrome must load the Dola extension')
            async def connect_worker(self, *a, **kw): return True
            async def inject_session_to_worker(self, *a): return True
            async def get_worker_page(self, *a): return Page()
            async def cleanup_all(self): cleaned.append(True)
        class Native:
            def cancel(self): pass
            async def execute_skill_batch(self, page, prompts, **kwargs):
                for number, prompt in zip(kwargs['prompt_numbers'], prompts):
                    calls.append((number, prompt, kwargs['model_version']))
                    (path.parent / f'prompt_{number:02d}_test_fixture.mp4').write_bytes(b'fixture')
                    await kwargs['on_video_found']({'prompt_number': number,
                        'url': f'https://example.invalid/{number}.mp4'})
        class Page:
            url = 'https://www.dola.com/chat/'
            async def goto(self, *args, **kwargs): pass
        class Downloader:
            async def download_video(self, *a, **kw): return str(path)
            def get_video_info(self, *a): return {'width':1280, 'duration':actual}
        class Accounts:
            def get_proxy_for_account(self, name): return ''
            def get_account(self, name): return None
            def save(self): pass
        class Proxies:
            async def get_proxy_for_account(self, *args): return 'http://fixture.invalid:10000'
            async def test_proxy(self, proxy): return {'success': True}
        runner = ProSkillBatch()
        if cancel_first:
            runner.cancel()
        with patch('config.OUTPUT_DIR', str(temporary.name)), patch('config.DATA_DIR', str(temporary.name)), patch('browser_manager.BrowserManager', Browser), patch('video_downloader.VideoDownloader', Downloader), patch('pro_skill_batch.NativeVideoAutomation', Native), patch('account_manager.AccountManager', Accounts), patch('proxy_manager.ProxyManager', Proxies):
            try:
                result = await runner.run('test', ['one', 'two'], '', 2, '16:9', '', on_video=completed.append)
            except BaseException as error:
                return error, calls, completed, cleaned
        return result, calls, completed, cleaned

    async def test_two_prompts_are_two_independent_verified_outputs(self):
        result, calls, completed, cleaned = await self.exercise()
        self.assertEqual(calls, [(1, 'one', '2.5'), (2, 'two', '2.5')])
        self.assertEqual(len(result), 2)
        self.assertEqual(len(completed), 2)
        self.assertEqual(cleaned, [True])

    def test_prompts_are_assigned_as_consecutive_pairs(self):
        groups = assign_prompts(['a', 'b', 'c', 'd', 'e'], [str(i) for i in range(10)])
        self.assertEqual({name: [number for number, _ in rows] for name, rows in groups.items()},
                         {'a': [1, 2], 'b': [3, 4], 'c': [5, 6], 'd': [7, 8], 'e': [9, 10]})

    async def test_short_result_stops_batch_without_completion_or_resubmission(self):
        error, calls, completed, cleaned = await self.exercise(actual=15)
        self.assertIn('DURATION_MISMATCH', str(error))
        self.assertEqual(len(calls), 1)
        self.assertEqual(completed, [])
        self.assertEqual(cleaned, [True])

    async def test_cancelled_batch_sends_no_requests(self):
        import asyncio
        error, calls, completed, cleaned = await self.exercise(cancel_first=True)
        self.assertIsInstance(error, asyncio.CancelledError)
        self.assertEqual(calls, [])
        self.assertEqual(cleaned, [])

    async def test_count_mismatch_never_silently_repeats_prompts(self):
        with self.assertRaises(ValueError):
            await ProSkillBatch().run('test', ['one'], '', 50, '16:9', '')


if __name__ == '__main__':
    unittest.main()
