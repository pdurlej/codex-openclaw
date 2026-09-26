from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/openclaw-bridge/scripts'))
from bridge_config import Config, load_config, save_config
import bridge_transport
from openclaw_bridge import Bridge

FAKE_CLI = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
method = sys.argv[3]
params = json.loads(sys.argv[sys.argv.index('--params') + 1])
record = Path(os.environ['FAKE_GATEWAY_RECORD'])
if method == 'health':
    result = {'ok': True, 'agents': [{'agentId': 'main'}]}
elif method == 'agent':
    record.write_text(json.dumps(params))
    result = {'runId': params['idempotencyKey']}
elif method == 'agent.wait':
    result = {'status': 'ok'}
elif method == 'chat.history':
    saved = json.loads(record.read_text())
    assert params['sessionKey'] == saved['sessionKey']
    result = {'messages': [{'role':'user','content':saved['message']},
                          {'role':'assistant','stopReason':'stop','content':'Fixture answer'}]}
print('CLI startup notice')
print(json.dumps(result))
'''

FAKE_SSH = '''#!/usr/bin/env python3
import shlex, subprocess, sys
# Execute the exact fixed remote argv locally; no real network or shell.
command = shlex.split(sys.argv[-1])
sys.exit(subprocess.run(command, input=sys.stdin.read(), text=True).returncode)
'''


class ConfigTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'OPENCLAW_BRIDGE_CONFIG': str(self.root / 'private/config.json'),
            'OPENCLAW_BRIDGE_DATA': str(self.root / 'state'),
            'FAKE_GATEWAY_RECORD': str(self.root / 'gateway.json'),
            'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
        })
        self.env.start()
        self.cli = self.root / 'fake-openclaw'
        self.cli.write_text(FAKE_CLI)
        self.cli.chmod(0o700)
        ssh = self.root / 'ssh'
        ssh.write_text(FAKE_SSH)
        ssh.chmod(0o700)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_config_is_private_and_existing_config_is_preserved(self):
        config = Config(transport='ssh', ssh_host='example')
        path = save_config(config)
        self.assertEqual(load_config(), config)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            save_config(replace(config, ssh_host='another-host'))
        self.assertEqual(load_config(), config)

    def test_missing_invalid_and_secret_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            load_config()
        path = self.root / 'private/config.json'
        path.parent.mkdir()
        for value in ['bad json', '[]', '{"token":"test-placeholder"}', '{"transport":null}']:
            path.write_text(value)
            with self.assertRaises(ValueError):
                load_config()
        for config in [Config(transport='ssh'), Config(transport='ssh', ssh_host='-oProxyCommand=bad'),
                       Config(agent_id='other:session'), Config(run_as_user='root'),
                       Config(openclaw_bin='-malicious'), Config(turn_timeout_seconds=True)]:
            with self.assertRaises(ValueError):
                config.validate()

    def test_config_changed_target_cannot_receive_old_request(self):
        original = Config(openclaw_bin=str(self.cli))
        bridge = Bridge(original)
        rid = str(uuid.uuid4())
        args = {'thread_id': 'chat', 'request_id': rid, 'message': 'Question'}
        bridge.ask(args)
        changed = Bridge(replace(original, agent_id='other'))
        with patch.object(changed, 'rpc') as rpc:
            with self.assertRaises(ValueError):
                changed.collect({'request_id': rid})
            with self.assertRaises(ValueError):
                changed.ask(args)
            rpc.assert_not_called()
        renamed = Bridge(replace(original, display_name='A new label'))
        self.assertEqual(renamed.collect({'request_id': rid})['answer'], 'Fixture answer')

    def test_real_subprocess_local_and_ssh_roundtrips(self):
        for transport in ('local', 'ssh'):
            with self.subTest(transport=transport):
                config = Config(transport=transport, openclaw_bin=str(self.cli),
                                ssh_host='example' if transport == 'ssh' else '', remote_python=sys.executable)
                bridge = Bridge(config)
                self.assertTrue(bridge.status()['agent_available'])
                rid = str(uuid.uuid4())
                args = {'thread_id': transport, 'request_id': rid, 'message': 'Quotes: " ` $()\nUnicode: żółć'}
                self.assertEqual(bridge.ask(args)['status'], 'pending')
                self.assertEqual(bridge.collect({'request_id': rid})['answer'], 'Fixture answer')
                sent = json.loads((self.root / 'gateway.json').read_text())
                self.assertIn(args['message'], sent['message'])
                self.assertFalse(sent['deliver'])
                self.assertTrue(sent['disableMessageTool'])

    def test_ssh_request_uses_stdin_and_existing_permissions(self):
        message = '$(command) `command` "quotes"'
        config = Config(transport='ssh', ssh_host='example', run_as_user='service')
        with patch.object(bridge_transport.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"ok":true}', '')) as runner:
            bridge_transport.call(config, 'agent', {'message': message})
            self.assertNotIn(message, ' '.join(runner.call_args.args[0]))
            self.assertNotIn('shell', runner.call_args.kwargs)
            self.assertIn('StrictHostKeyChecking=yes', runner.call_args.args[0])
            self.assertTrue(runner.call_args.args[0][-1].startswith('sudo -n -H -u service '))
            self.assertEqual(json.loads(runner.call_args.kwargs['input'])['params']['message'], message)

    def test_cli_errors_never_echo_raw_diagnostics(self):
        with patch.object(bridge_transport.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'credential-placeholder', 'credential-placeholder')):
            with self.assertRaises(RuntimeError) as error:
                bridge_transport.call(Config(), 'health', {})
            self.assertNotIn('credential-placeholder', str(error.exception))
        with self.assertRaises(RuntimeError):
            bridge_transport.parse_response('{"bridge_error":"no connection"}')

    def test_native_mcp_configured_connection_roundtrip(self):
        save_config(Config(openclaw_bin=str(self.cli)))
        rid = str(uuid.uuid4())
        requests = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'openclaw_ask','arguments':{'thread_id':'mcp-chat','request_id':rid,'message':'Question'}}},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'openclaw_collect','arguments':{'request_id':rid}}},
        ]
        result = subprocess.run([sys.executable, str(ROOT / 'bridge.py')], input=''.join(json.dumps(r)+'\n' for r in requests), capture_output=True, text=True, timeout=10, check=True)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 3)
        answer = json.loads(responses[-1]['result']['content'][0]['text'])
        self.assertEqual(answer['answer'], 'Fixture answer')
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
