"""Integration checks run against a dedicated, disposable PostgreSQL database."""
import os
import unittest
from unittest.mock import patch
import storage

@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'Dedicated PostgreSQL test database not configured')
class PostgresTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'DATABASE_URL': os.environ['TEST_DATABASE_URL']})
        self.env.start()
        self.access = patch('access.require_access')
        self.access.start()
        storage.initialize()
        with storage.connect() as db:
            db.execute('TRUNCATE updates, incidents, providers RESTART IDENTITY')

    def tearDown(self):
        self.access.stop()
        self.env.stop()

    def test_persistence_history_and_rollback(self):
        storage.add_provider('Ana','Roofing and gutters','San José','50612345678','Test')
        storage.add_incident('Demo','Long-term','Leak','Roofing and gutters','High')
        storage.save_incident(1,'Schedule a visit',1,'Tuesday',25000,'Confirmed')
        storage.initialize()
        item = storage.rows('SELECT * FROM incidents')[0]
        self.assertEqual(item['provider_id'],1)
        self.assertEqual(item['cost'],25000)
        self.assertIsInstance(item['last_activity'],str)
        history = storage.rows('SELECT * FROM updates ORDER BY id')
        self.assertEqual(len(history),3)
        storage.save_incident(1,'Schedule a visit',1,'Tuesday',25000,'')
        self.assertEqual(storage.rows('SELECT * FROM updates ORDER BY id'),history)
        with self.assertRaises(ValueError):
            storage.save_incident(1,'Closed',999,'Tuesday',25000,'Invalid')
        self.assertEqual(storage.rows('SELECT * FROM incidents')[0]['status'],'Schedule a visit')
        self.assertEqual(storage.rows('SELECT * FROM updates ORDER BY id'),history)
        storage.save_incident(1,'Closed',1,'Tuesday',25000,'Verified')
        self.assertEqual(storage.rows('SELECT * FROM incidents')[0]['status'],'Closed')
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file('app.py').run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, '0')
        app.sidebar.radio[0].set_value('Details and follow-up').run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn('This repair is closed.', [message.value for message in app.success])
        reviewed_id = storage.add_incident('Demo AI', 'Long-term', 'Reviewed report', 'General / to be determined', 'Normal', followup_note='Reviewed draft, not sent')
        self.assertEqual(storage.rows('SELECT * FROM updates WHERE incident_id=?', (reviewed_id,))[0]['note'], 'Reviewed draft, not sent')
