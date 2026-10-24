import asyncio
import pathlib
import sys
import tempfile
import unittest
import shutil
import subprocess
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from native_video_automation import stream_error, failure_message
from worker_pool import WorkerPool


class ResponseTests(unittest.TestCase):
    def test_rate_limit_in_http_200_sse_is_reported(self):
        response = 'event: STREAM_ERROR\ndata: {"error_code":710022002,"error_msg":"too many requests"}\n'
        self.assertIn('710022002', stream_error(response))
        self.assertIn('Quá nhiều yêu cầu', stream_error(response))

    def test_http_200_stream_business_error_is_not_success(self):
        response = 'event: SSE_HEARTBEAT\ndata: {}\n\nevent: STREAM_ERROR\ndata: {"error_code":710020202,"error_msg":"common invalid param"}\n'
        self.assertEqual(stream_error(response), 'Dola 710020202: common invalid param')

    def test_regular_sse_is_not_an_error(self):
        self.assertEqual(stream_error('event: MESSAGE\ndata: {"text":"generating"}\n'), '')

    def test_json_business_error(self):
        self.assertIn('not logged in', stream_error('{"code":401,"msg":"not logged in"}'))

    def test_failure_card_overrides_generating_text(self):
        self.assertTrue(failure_message('Video đang được tạo...', 1))

    def test_empty_task_is_a_failure(self):
        self.assertTrue(failure_message('Công cụ trả task_id rỗng.'))

    def test_accepted_text_is_not_a_failure(self):
        self.assertEqual(failure_message('Video đang tạo; còn 2 credit.'), '')


class PoolTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, duration=15, fail_first=False, target=15):
        calls, current, launches = [], {}, []
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        raw = pathlib.Path(temp.name) / 'download.mp4'
        raw.write_bytes(b'fixture')

        class Page:
            async def goto(self, *a, **kw): pass
        class Browser:
            async def launch_temp_chrome(self, wid, **kw): launches.append(kw)
            async def connect_worker(self, wid, **kw):
                self.setup_extension = kw.get('setup_extension')
                return object()
            async def inject_session_to_worker(self, wid, name): current['name'] = name; return True
            async def get_worker_page(self, wid): return Page()
            async def cleanup_worker(self, wid): pass
            async def cleanup_all(self): pass
        class Accounts:
            def get_proxy_for_account(self, name): return ''
            def load(self): pass
            def get_all(self): return [{'name':n,'status':'active'} for n in ('A','B')]
        class Sessions:
            def has_session(self, name): return True
        class Proxy:
            async def get_proxy_for_account(self, *a): return None
        class Automation:
            async def execute_generation_flow(self, **kw):
                calls.append(current['name'])
                if fail_first and len(calls) == 1:
                    raise RuntimeError('Dola 710020202: common invalid param')
                return 'https://example.invalid/generated.mp4'
        class Downloader:
            async def download_video(self, *a, **kw): return str(raw)
            @staticmethod
            def get_video_info(path): return {'width':1280,'height':720,'duration':duration}

        with patch('browser_manager.BrowserManager', Browser), patch('account_manager.AccountManager', Accounts), \
             patch('session_store.SessionStore', Sessions), patch('proxy_manager.ProxyManager', Proxy), \
             patch('native_video_automation.NativeVideoAutomation', Automation), patch('video_downloader.VideoDownloader', Downloader):
            pool = WorkerPool(1)
            job = pool.submit_job('A', 'test', duration_target=target, upscale='off', max_retries=2)
            await pool.start(1)
            try:
                # The real worker includes a two-second navigation settling delay.
                for _ in range(150):
                    if job.id not in pool.active_jobs:
                        break
                    await asyncio.sleep(.05)
                self.assertNotIn(job.id, pool.active_jobs, 'A failed retry must not strand the job')
            finally:
                await pool.stop()
        return job, calls, launches

    async def test_rejected_request_switches_account_and_completes(self):
        job, calls, launches = await self.exercise(fail_first=True)
        self.assertEqual(calls, ['A','B'])
        self.assertEqual(job.status, 'completed')
        self.assertTrue(all(not launch['load_extension'] for launch in launches))

    async def test_wrong_length_never_completes_or_spends_another_retry(self):
        job, calls, _ = await self.exercise(duration=10)
        self.assertEqual(job.status, 'failed')
        self.assertIn('DURATION_MISMATCH', job.error)
        self.assertEqual(len(calls), 1)

    async def test_thirty_second_request_rejects_fifteen_second_file(self):
        job, calls, launches = await self.exercise(duration=15, target=30)
        self.assertEqual(job.status, 'failed')
        self.assertIn('cần 30s', job.error)
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(not launch['load_extension'] for launch in launches))

    async def test_thirty_second_file_passes_requested_duration_check(self):
        job, calls, launches = await self.exercise(duration=30, target=30)
        self.assertEqual(job.status, 'completed')
        self.assertTrue(all(not launch['load_extension'] for launch in launches))


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class MediaDurationTests(unittest.TestCase):
    def test_real_probe_distinguishes_ten_from_fifteen_seconds(self):
        from video_downloader import VideoDownloader
        with tempfile.TemporaryDirectory() as directory:
            for seconds in (10, 15):
                path = pathlib.Path(directory) / f'{seconds}.mp4'
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                                f'color=black:s=32x32:r=1:d={seconds}',
                                '-c:v','libx264','-y',str(path)],check=True,
                               capture_output=True,timeout=15)
                self.assertAlmostEqual(VideoDownloader.get_video_info(str(path))['duration'], seconds, places=2)


if __name__ == '__main__':
    unittest.main()
