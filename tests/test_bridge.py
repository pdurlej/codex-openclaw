import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/openclaw-bridge/scripts/openclaw_bridge.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('openclaw_bridge', SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'OPENCLAW_BRIDGE_DATA': self.tmp.name})
        self.env.start()
        self.client = bridge.Bridge(bridge.Config())
        self.rid = str(uuid.uuid4())
        self.args = {'thread_id': 'chat-one', 'request_id': self.rid, 'message': 'Question'}

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_acceptance_is_not_completion_and_replay_does_not_send(self):
        with patch.object(self.client, 'rpc', return_value={'runId': self.rid}) as rpc:
            self.assertEqual(self.client.ask(self.args)['status'], 'pending')
            self.assertEqual(self.client.ask(self.args)['status'], 'pending')
            self.assertEqual(rpc.call_count, 1)
            params = rpc.call_args.args[1]
            self.assertFalse(params['deliver'])
            self.assertTrue(params['disableMessageTool'])
            self.assertTrue(params['sessionKey'].startswith('agent:main:codex-bridge:'))

    def test_ambiguous_send_is_persisted_and_never_retried(self):
        with patch.object(self.client, 'rpc', side_effect=RuntimeError('transport failed')) as rpc:
            self.assertEqual(self.client.ask(self.args)['status'], 'unknown')
            self.assertEqual(self.client.ask(self.args)['status'], 'unknown')
            self.assertEqual(rpc.call_count, 1)
        with patch.object(self.client, 'rpc') as rpc:
            with self.assertRaises(ValueError):
                self.client.ask(dict(self.args, request_id=str(uuid.uuid4())))
            rpc.assert_not_called()

    def test_request_id_cannot_be_reused_for_different_content(self):
        with patch.object(self.client, 'rpc', return_value={'runId': self.rid}):
            self.client.ask(self.args)
            with self.assertRaises(ValueError):
                self.client.ask(dict(self.args, message='Different question'))
            with self.assertRaises(ValueError):
                self.client.ask(dict(self.args, thread_id='other-chat'))

    def test_matched_result_and_followup_share_session(self):
        sessions = []
        def rpc(method, params):
            if method == 'agent':
                sessions.append(params['sessionKey'])
                return {'runId': params['idempotencyKey']}
            if method == 'agent.wait':
                return {'status': 'ok'}
            return {'messages': [
                {'role': 'assistant', 'content': 'Old answer'},
                {'role': 'user', 'content': '[codex-openclaw:' + self.rid + ']\nQuestion'},
                {'role': 'assistant', 'stopReason': 'toolUse', 'content': [{'type': 'text', 'text': 'Working'}]},
                {'role': 'toolResult', 'content': 'raw tool response'},
                {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Answer from the agent'}]},
            ]}
        with patch.object(self.client, 'rpc', side_effect=rpc) as mocked:
            self.client.ask(self.args)
            result = self.client.collect({'request_id': self.rid})
            self.assertEqual(result['answer'], 'Answer from the agent')
            calls = mocked.call_count
            self.assertEqual(self.client.collect({'request_id': self.rid}), result)
            self.assertEqual(mocked.call_count, calls)
            self.client.ask(dict(self.args, request_id=str(uuid.uuid4()), message='Follow-up'))
            self.client.ask(dict(self.args, request_id=str(uuid.uuid4()), thread_id='chat-two'))
        self.assertEqual(sessions[0], sessions[1])
        self.assertNotEqual(sessions[0], sessions[2])

    def test_unknown_and_timeout_never_return_old_answer(self):
        with patch.object(self.client, 'rpc', return_value={'runId': self.rid}):
            self.client.ask(self.args)
        with patch.object(self.client, 'rpc', return_value={'status': 'timeout'}) as rpc:
            self.assertEqual(self.client.collect({'request_id': self.rid})['status'], 'pending')
            self.assertEqual(rpc.call_count, 2)
        with patch.object(self.client, 'rpc', side_effect=[{'status': 'ok'}, {'messages': [{'role': 'assistant', 'content': 'Stale'}]}]):
            self.assertEqual(self.client.collect({'request_id': self.rid})['status'], 'pending')

    def test_expired_run_snapshot_recovers_only_a_matched_terminal_answer(self):
        with patch.object(self.client, 'rpc', return_value={'runId': self.rid}):
            self.client.ask(self.args)
        history = {'messages': [
            {'role': 'user', 'content': '[codex-openclaw:' + self.rid + '] Question'},
            {'role': 'assistant', 'content': 'A partial answer'}]}
        with patch.object(self.client, 'rpc', side_effect=[{'status': 'timeout'}, history]):
            self.assertEqual(self.client.collect({'request_id': self.rid})['status'], 'pending')
        history['messages'][-1]['stopReason'] = 'stop'
        history['messages'][-1]['content'] = 'Recovered final answer'
        with patch.object(self.client, 'rpc', side_effect=[{'status': 'timeout'}, history]) as rpc:
            result = self.client.collect({'request_id': self.rid})
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['answer'], 'Recovered final answer')
            self.assertEqual([c.args[0] for c in rpc.call_args_list], ['agent.wait', 'chat.history'])

    def test_terminal_execution_timeout_releases_chat_without_resending(self):
        with patch.object(self.client, 'rpc', return_value={'runId': self.rid}):
            self.client.ask(self.args)
        with patch.object(self.client, 'rpc', return_value={'status': 'timeout', 'endedAt': 123, 'stopReason': 'timeout'}) as rpc:
            self.assertEqual(self.client.collect({'request_id': self.rid})['status'], 'failed')
            self.assertEqual(rpc.call_count, 1)
        with patch.object(self.client, 'rpc', return_value={'runId': 'next-run'}) as rpc:
            self.client.ask(dict(self.args, request_id=str(uuid.uuid4()), message='A new question'))
            self.assertEqual(rpc.call_count, 1)

    def test_validation_before_network(self):
        with patch.object(self.client, 'rpc') as rpc:
            for args in [dict(self.args, request_id='; rm anything'), dict(self.args, message=''), dict(self.args, message='a' * 24001)]:
                with self.assertRaises(ValueError):
                    self.client.ask(args)
            rpc.assert_not_called()

    def test_native_mcp_stdio_initialize_list_and_invalid_call(self):
        requests = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'openclaw_ask', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'ping'},
        ]
        result = subprocess.run([sys.executable, str(SCRIPT)], input=''.join(json.dumps(r) + '\n' for r in requests), text=True, capture_output=True, check=True)
        output = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(output), 4)
        self.assertEqual(len(output[1]['result']['tools']), 3)
        self.assertTrue(output[2]['result']['isError'])
        self.assertEqual(output[3]['result'], {})
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
