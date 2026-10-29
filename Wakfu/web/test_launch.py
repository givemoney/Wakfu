import importlib.util
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('wakfu_launch',Path(__file__).resolve().parents[1]/'launch.py')
launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)

class LauncherTests(unittest.TestCase):
    def test_different_installations_have_different_identity(self):
        self.assertNotEqual(launch.installation_id(Path('first')),launch.installation_id(Path('second')))
    def test_busy_port_does_not_stop_another_application(self):
        with socket.socket() as busy:
            busy.bind(('127.0.0.1',0));busy.listen()
            preferred=busy.getsockname()[1]
            self.assertNotEqual(launch.available_port(preferred),preferred)
    def test_existing_server_reused_only_for_this_installation(self):
        with patch.object(launch,'status',return_value={'installation_id':launch.installation_id(launch.ROOT)}),patch.object(launch.subprocess,'Popen') as spawn:
            self.assertEqual(launch.launch(8879,False),'http://127.0.0.1:8879/')
            spawn.assert_not_called()
    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError):launch.launch(65536,False)

if __name__=='__main__':unittest.main()
