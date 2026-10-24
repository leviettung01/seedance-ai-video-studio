import json
import pathlib
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from utils import safe_json_save
from account_manager import AccountManager


class PersistenceTests(unittest.TestCase):
    def test_concurrent_writes_never_publish_partial_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'state.json'
            safe_json_save(str(path), {'rows': [0] * 100})
            stopped = threading.Event()
            failures = []
            def read():
                while not stopped.is_set():
                    try:
                        json.loads(path.read_text(encoding='utf-8'))
                    except PermissionError:
                        # Windows may briefly deny opens during an atomic
                        # replacement; this must never publish partial JSON.
                        continue
                    except Exception as exc:
                        failures.append(type(exc).__name__)
            reader = threading.Thread(target=read)
            reader.start()
            try:
                with ThreadPoolExecutor(4) as workers:
                    list(workers.map(lambda n: safe_json_save(str(path), {'rows': [n] * 100}), range(20)))
            finally:
                stopped.set()
                reader.join()
            self.assertEqual(failures, [])

    def test_corrupt_read_keeps_existing_account_index(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'accounts.json'
            path.write_text('{"accounts": [{"name":"fixture"}]}', encoding='utf-8')
            with patch('account_manager.ACCOUNTS_STATE_FILE', str(path)):
                manager = AccountManager()
                path.write_text('{', encoding='utf-8')
                manager.load()
                self.assertIsNotNone(manager.get_account('fixture'))
