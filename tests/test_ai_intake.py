import copy
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
import requests
from streamlit.testing.v1 import AppTest
import ai_intake
import storage

DRAFT = {
    'summary': 'Water enters through the bedroom ceiling during rain.',
    'specialty': 'Roofing and gutters', 'priority': 'High',
    'attention_flags': [], 'missing_information': ['Is water entering now?'],
    'provider_message': 'Can you assess a reported bedroom ceiling leak? Are you available?',
}
RESULT = {'draft': DRAFT, 'model': ai_intake.MODEL, 'prompt_version': ai_intake.PROMPT_VERSION,
          'seconds': 1.2, 'input_tokens': 80, 'output_tokens': 100}

class ModelTest(unittest.TestCase):
    def test_structured_request_and_valid_response(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(DRAFT)}}], 'usage': {'prompt_tokens': 80, 'completion_tokens': 100}}
        with patch('ai_intake.requests.post', return_value=response) as post:
            result = ai_intake.generate_draft('There is a ceiling leak.', 'test-key')
        self.assertEqual(result['draft'], DRAFT)
        self.assertEqual(result['input_tokens'], 80)
        self.assertEqual(post.call_args.args[0], 'https://api.openai.com/v1/chat/completions')
        self.assertTrue(post.call_args.kwargs['json']['response_format']['json_schema']['strict'])
        self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_invalid_output_is_rejected(self):
        for change in ({'specialty': 'Unknown'}, {'priority': 'Low'}, {'attention_flags': 'not a list'}, {'summary': ''}, {'extra': 'unexpected'}):
            draft = dict(DRAFT, **change)
            with self.subTest(change=change), self.assertRaises(ai_intake.IntakeError):
                ai_intake.validate_draft(draft)

    def test_network_and_api_errors_do_not_expose_credentials(self):
        with patch('ai_intake.requests.post', side_effect=requests.Timeout('sensitive test-key')):
            with self.assertRaises(ai_intake.IntakeError) as error:
                ai_intake.generate_draft('Leak', 'test-key')
            self.assertNotIn('test-key', str(error.exception))
        for status in (401, 429, 500, 302):
            with self.subTest(status=status), patch('ai_intake.requests.post', return_value=Mock(status_code=status)):
                with self.assertRaises(ai_intake.IntakeError):
                    ai_intake.generate_draft('Leak', 'test-key')

    def test_refusal_and_truncated_response_are_rejected(self):
        for message, reason in [({'refusal': 'refused'}, 'stop'), ({'content': '{}'}, 'length')]:
            response = Mock(status_code=200)
            response.json.return_value = {'choices': [{'message': message, 'finish_reason': reason}]}
            with patch('ai_intake.requests.post', return_value=response), self.assertRaises(ai_intake.IntakeError):
                ai_intake.generate_draft('Leak', 'test-key')

    def test_blank_input_and_missing_key_do_not_call_api(self):
        with patch('ai_intake.requests.post') as post:
            for text,key in [('', 'test-key'), ('x'*6001, 'test-key'), ('Leak','')]:
                with self.assertRaises(ai_intake.IntakeError):
                    ai_intake.generate_draft(text,key)
            post.assert_not_called()

class IntakeScreenTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DATABASE_URL': '', 'RENTAL_DB_PATH': self.temp.name+'/test.db', 'OPENAI_API_KEY':'test-only'})
        self.env.start()
        self.auth = patch('access.require_access')
        self.auth.start()
        self.generate = patch('ai_intake.generate_draft', return_value=copy.deepcopy(RESULT))
        self.model = self.generate.start()
        self.app = AppTest.from_file('app.py').run()
        self.app.sidebar.radio[0].set_value('AI intake').run()

    def tearDown(self):
        self.generate.stop()
        self.auth.stop()
        self.env.stop()
        self.temp.cleanup()

    def generate_draft(self):
        self.app.text_area[0].set_value('There is a ceiling leak during rain.')
        next(b for b in self.app.button if b.label=='Generate AI draft').click().run()
        self.assertEqual(len(self.app.exception),0)

    def test_review_required_and_only_edited_output_saved(self):
        self.generate_draft()
        self.assertEqual(storage.rows('SELECT * FROM incidents'), [])
        next(b for b in self.app.button if b.label=='Save reviewed request').click().run()
        self.assertEqual(storage.rows('SELECT * FROM incidents'), [])
        self.app.text_input[0].set_value('Demo house')
        next(t for t in self.app.text_area if t.label=='Reviewed summary').set_value('Owner corrected summary')
        self.app.checkbox[0].check()
        next(b for b in self.app.button if b.label=='Save reviewed request').click().run()
        self.assertEqual(len(self.app.exception),0)
        self.assertEqual(storage.rows('SELECT * FROM incidents')[0]['description'], 'Owner corrected summary')
        self.assertIn('not sent', storage.rows('SELECT * FROM updates')[0]['note'])
        self.assertEqual(len(self.app.success),1)
        self.app.run()
        self.assertEqual(len(storage.rows('SELECT * FROM incidents')),1)
        self.assertFalse(any(b.label=='Save reviewed request' for b in self.app.button))
        self.assertEqual(self.model.call_count,1)

    def test_failed_regeneration_clears_old_draft(self):
        self.generate_draft()
        self.model.side_effect = ai_intake.IntakeError('Try again later')
        next(b for b in self.app.button if b.label=='Generate AI draft').click().run()
        self.assertEqual(len(self.app.exception),0)
        self.assertFalse(any(b.label=='Save reviewed request' for b in self.app.button))
        self.assertEqual(storage.rows('SELECT * FROM incidents'), [])
