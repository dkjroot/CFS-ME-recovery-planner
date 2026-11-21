"""Run the planner's local behavior and HTTP checks."""

from argparse import Namespace
from datetime import date, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from accounts import Accounts, LoginBusy, MAX_ATTEMPTS, REMEMBER_SECONDS
from planner import PlannerStore, activity_view
from run import HOST, PlannerHandler, PlannerServer, main, manage_account


class StartupTests(unittest.TestCase):
    def test_default_listen_address(self):
        with (
            patch('sys.argv', ['run.py']),
            patch('run.PlannerServer') as server,
            patch('run.Accounts'),
            patch('builtins.print'),
        ):
            main()

        server.assert_called_once_with(('127.0.0.1', 8022), PlannerHandler)

    def test_second_planner_cannot_take_over_a_live_port(self):
        with PlannerServer((HOST, 0), PlannerHandler) as server:
            with self.assertRaises(OSError):
                PlannerServer((HOST, server.server_port), PlannerHandler)


class AccountTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.accounts = Accounts(Path(temporary.name))
        self.accounts.initialize()
        self.password = secrets.token_urlsafe(20)
        self.accounts.set_password('Sample', self.password, create=True)

    def test_password_reset_revokes_existing_sessions(self):
        token = self.accounts.login('sample', self.password, True)
        self.assertEqual(self.accounts.session_user(token)[1], 'Sample')
        replacement = secrets.token_urlsafe(20)
        self.accounts.set_password('Sample', replacement, create=False)
        self.assertIsNone(self.accounts.session_user(token))
        self.assertIsNone(self.accounts.login('Sample', self.password, False))
        self.assertIsNotNone(self.accounts.login('Sample', replacement, False))

    def test_session_expires_and_attempts_are_limited(self):
        with patch('accounts.time.time', return_value=100):
            token = self.accounts.login('Sample', self.password, True)
        with patch('accounts.time.time', return_value=100 + REMEMBER_SECONDS):
            self.assertIsNone(self.accounts.session_user(token))
        with patch('accounts.password_hash', return_value=b'\xff' * 32):
            for _ in range(MAX_ATTEMPTS):
                self.assertIsNone(self.accounts.login('missing', 'incorrect', False))
            with self.assertRaises(LoginBusy):
                self.accounts.login('Sample', self.password, False)

    def test_legacy_import_is_explicit_and_does_not_overwrite(self):
        source = self.accounts.directory / 'planner.json'
        source.write_text('{"plan": null, "activities": {}}', encoding='utf-8')
        args = Namespace(import_planner='Sample')
        with patch('run.DATA_FILE', source), patch('builtins.print'):
            manage_account(self.accounts, args)
            with self.assertRaises(ValueError):
                manage_account(self.accounts, args)
        destination = self.accounts.planner_path(self.accounts.user_id('Sample'))
        self.assertEqual(source.read_bytes(), destination.read_bytes())
        source.write_text('{}', encoding='utf-8')
        self.assertNotEqual(source.read_bytes(), destination.read_bytes())

    def test_local_setup_prompts_for_confirmation(self):
        args = Namespace(add_user='Mama', reset_password=None, import_planner=None)
        with patch('run.getpass', side_effect=[self.password, 'different']), patch('builtins.print'):
            with self.assertRaises(ValueError):
                manage_account(self.accounts, args)
        self.assertIsNone(self.accounts.user_id('Mama'))
        with patch('run.getpass', side_effect=[self.password, self.password]), patch('builtins.print'):
            manage_account(self.accounts, args)
        self.assertIsNotNone(self.accounts.login('Mama', self.password, False))


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 1, 19)
        self.plan = {'activity': 'Reading', 'limit': 10, 'step_back': 4, 'stepped_back': False}
        self.entries = {
            self.day(offset): {'minutes': value, 'feeling': 'usual', 'planned': 10, 'context': ''}
            for offset, value in enumerate([10, 10, 9, 12, 8, 45, 9, 8, 8], start=-8)
        }

    def day(self, offset):
        return (self.today + timedelta(days=offset)).isoformat()

    def view(self):
        return activity_view(self.plan, self.entries, self.today)

    def test_typical_recent_minutes_recalculate_without_changing_limit(self):
        self.assertEqual(self.view()['projection'], 10)
        self.entries[self.day(-3)]['minutes'] = 7
        self.entries[self.day(0)]['feeling'] = 'better'
        self.assertEqual(self.view()['projection'], 9.5)
        self.assertEqual(self.view()['plan']['limit'], 10)

    def test_low_invalidates_previous_three_days_and_shows_lookback(self):
        self.entries[self.day(-3)]['feeling'] = 'worse'
        result = self.view()
        self.assertEqual(result['sample_size'], 2)
        self.assertIsNone(result['projection'])
        self.assertEqual([item['date'] for item in result['lows'][0]['prior']],
                         [self.day(-4), self.day(-5), self.day(-6)])
        self.assertEqual(result['lows'][0]['prior'][1]['minutes'], 12)

    def test_recent_crash_pauses_projection_and_keeps_missing_days_visible(self):
        self.entries.pop(self.day(-1))
        self.entries[self.day(0)]['feeling'] = 'crash'
        result = self.view()
        self.assertTrue(result['paused'])
        self.assertTrue(result['above_before_low'])
        self.assertIsNone(result['projection'])
        self.assertEqual(result['lows'][0]['prior'][0], {'date': self.day(-1)})
        self.assertEqual(result['lows'][0]['prior'][2]['minutes'], 45)

    def test_missing_followup_is_not_counted_as_usual(self):
        self.entries.pop(self.day(-4))
        self.assertEqual(self.view()['sample_size'], 2)
        self.assertIsNone(self.view()['projection'])

    def test_active_step_back_holds_even_after_better_days(self):
        self.plan['stepped_back'] = True
        self.entries[self.day(0)]['feeling'] = 'better'
        self.assertTrue(self.view()['paused'])
        self.assertIsNone(self.view()['projection'])


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 1, 19)
        self.store = PlannerStore()
        self.state = {'plan': None, 'activities': {}}

    def log(self, offset, feeling='usual', **fields):
        day = self.today + timedelta(days=offset)
        activity = self.state['plan']['activity'] if self.state['plan'] else None
        self.store.apply(self.state, 'entry',
                         {'date': day.isoformat(), 'activity': activity, 'feeling': feeling, **fields}, day)

    def guide(self, offset=0):
        return self.store.view(self.state, self.today + timedelta(days=offset))['roadmap']

    def test_starting_roadmap_is_available_without_an_exercise_plan(self):
        result = self.guide()
        self.assertEqual(result['stage'], 0)
        self.assertEqual(result['stages'][1]['review_date'], '2026-01-25')
        self.assertEqual(result['stages'][2]['review_date'], '2026-02-01')
        self.assertEqual(result['suggestions'][0]['name'], 'Quiet rest')
        self.assertFalse(result['ready'])

    def test_above_plan_waits_for_follow_up_even_on_a_better_day(self):
        self.store.apply(self.state, 'plan', {'activity': 'Reading', 'limit': 10}, self.today)
        for offset in range(-7, 0):
            self.log(offset, minutes=10)
        self.assertTrue(self.guide()['ready'])
        self.log(0, 'better', minutes=14)
        result = self.guide()
        self.assertFalse(result['ready'])
        self.assertEqual(result['stages'][1]['review_date'], '2026-01-22')
        self.log(1, minutes=10)
        self.log(2, minutes=10)
        self.assertFalse(self.guide(2)['ready'])
        self.log(3, minutes=10)
        result = self.guide(3)
        self.assertTrue(result['ready'])
        self.assertEqual(result['stage'], 0)
        self.assertEqual(result['findings']['2026-01-19']['status'], 'observed')
        self.store.apply(self.state, 'roadmap', {'direction': 'next'}, self.today + timedelta(days=3))
        result = self.guide(3)
        self.assertEqual(result['stage'], 1)
        self.assertEqual(result['logged_days'], 0)
        self.assertEqual(self.state['plan']['limit'], 10)

    def test_crash_two_days_later_resets_review_and_switches_suggestions(self):
        self.store.apply(self.state, 'plan', {'activity': 'Reading', 'limit': 10}, self.today)
        for offset in range(-7, 0):
            self.log(offset, minutes=10)
        self.log(0, 'better', minutes=16)
        original_review = self.guide()['stages'][1]['review_date']
        self.log(2, 'crash', minutes=0)
        result = self.guide(2)
        self.assertGreater(result['stages'][1]['review_date'], original_review)
        self.assertEqual(result['logged_days'], 0)
        self.assertEqual(result['findings']['2026-01-19']['days_until_low'], 2)
        self.assertIn('help', [item['key'] for item in result['suggestions']])
        self.log(3, 'better')
        self.assertTrue(self.guide(3)['setback'])
        self.log(4)
        self.assertFalse(self.guide(4)['setback'])
        self.assertFalse(self.guide(4)['ready'])

    def test_routine_amounts_are_available_in_lookback_and_keep_old_plan(self):
        action = {'operation': 'add', 'suggestion': 'quiet-rest', 'planned': 15}
        self.store.apply(self.state, 'routine', action, self.today)
        rest = next(iter(self.state['routine']))
        self.store.apply(self.state, 'routine',
                         {'operation': 'add', 'name': 'Reading', 'kind': 'Thinking', 'planned': 6}, self.today)
        reading = next(key for key in self.state['routine'] if key != rest)
        self.log(-2, routine={rest: 24, reading: 9})
        self.store.apply(self.state, 'routine', {'operation': 'remove', 'id': reading}, self.today)
        self.log(-2, routine={rest: 24})
        self.log(0, 'crash')
        view = self.store.view(self.state, self.today)
        entry = view['lows'][0]['prior'][1]
        self.assertEqual(entry['routine'][reading]['planned'], 6)
        self.assertEqual(entry['routine'][reading]['minutes'], 9)
        self.assertTrue(view['above_before_low'])
        self.assertTrue(view['roadmap']['findings']['2026-01-17']['above_plan'])

    def test_missing_follow_ups_are_not_reported_as_observed(self):
        self.store.apply(self.state, 'plan', {'activity': 'Reading', 'limit': 10}, self.today)
        for offset in range(-12, -4):
            self.log(offset, minutes=10)
        self.log(-4, minutes=15)
        self.log(-2)
        self.log(0)
        result = self.guide()
        self.assertEqual(result['findings']['2026-01-15']['status'], 'incomplete')
        self.assertEqual(result['review_items'], ['Reading'])
        self.assertEqual(result['missing_follow_ups'], 1)
        self.assertFalse(result['ready'])


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.accounts = Accounts(Path(temporary.name))
        cls.accounts.initialize()
        cls.password = secrets.token_urlsafe(20)
        for username in ('Sample', 'Second'):
            cls.accounts.set_password(username, cls.password, create=True)
        cls.server = ThreadingHTTPServer((HOST, 0), PlannerHandler)
        cls.server.accounts = cls.accounts
        cls.addClassCleanup(cls.server.server_close)
        worker = Thread(target=cls.server.serve_forever, daemon=True)
        worker.start()
        cls.addClassCleanup(worker.join)
        cls.addClassCleanup(cls.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection(HOST, self.server.server_port, timeout=3)
        self.addCleanup(connection.close)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.headers, response.read()

    @property
    def origin(self):
        return f'http://{HOST}:{self.server.server_port}'

    def sign_in(self, username='Sample', remember=False, **overrides):
        fields = {'username': username, 'password': self.password}
        if remember:
            fields['remember'] = 'yes'
        return self.request('POST', '/login', urlencode(fields),
                            {'Content-Type': 'application/x-www-form-urlencoded',
                             'Origin': self.origin, **overrides})

    def authenticate(self, username='Sample', remember=False):
        status, headers, _ = self.sign_in(username, remember)
        self.assertEqual(status, 303)
        self.cookie = headers['Set-Cookie'].partition(';')[0]
        status, _, body = self.request('GET', '/api/planner', headers={'Cookie': self.cookie})
        self.assertEqual(status, 200)
        self.write_token = json.loads(body)['write_token']

    def test_home_page(self):
        self.authenticate()
        status, headers, body = self.request('GET', '/?test=1', headers={'Cookie': self.cookie})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn(b'ME/CFS Recovery Planner', body)
        self.assertIn(b'Activity over time', body)
        self.assertIn(b'src="planner.js"', body)
        self.assertIn(b'id="account-bar" class="account-bar" hidden', body)
        self.assertIn(b'id="dashboard" hidden', body)
        self.assertNotIn(b'action="/logout"', body)

    def test_head_has_headers_without_body(self):
        _, get_headers, _ = self.request('GET', '/login')
        status, headers, body = self.request('HEAD', '/login')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Length'], get_headers['Content-Length'])
        self.assertEqual(body, b'')

    def test_server_does_not_serve_private_files(self):
        for path in ('/missing', '/README.md', '/agent_docs/reference.pdf',
                     '/local_data/planner.json', '/local_data/accounts.sqlite3', '/.env'):
            with self.subTest(path=path):
                status, _, _ = self.request('GET', path)
                self.assertEqual(status, 404)

    def test_frontend_assets(self):
        for path, content_type in [('/planner.js', 'text/javascript'), ('/planner.css', 'text/css')]:
            with self.subTest(path=path):
                status, headers, body = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Type'], f'{content_type}; charset=utf-8')
                self.assertTrue(body)

    def write(self, action, payload, origin=None):
        return self.request('POST', f'/api/planner/{action}', json.dumps(payload),
                            {'Content-Type': 'application/json', 'Origin': origin or self.origin,
                             'Cookie': self.cookie, 'X-Planner-Session': self.write_token})

    def test_local_plan_check_in_and_step_back(self):
        self.authenticate()
        plan = {'activity': 'Puzzles', 'limit': 10, 'step_back': 0}
        status, _, body = self.write('plan', plan)
        self.assertEqual(status, 200)
        today = json.loads(body)['today']
        entry = {'date': today, 'activity': 'Puzzles', 'minutes': 15, 'feeling': 'better'}
        status, _, body = self.write('entry', entry)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['plan']['limit'], 10)
        self.assertEqual(json.loads(body)['history'][0]['planned'], 10)

        status, _, body = self.write('mode', {'activity': 'Puzzles', 'stepped_back': True})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['plan']['stepped_back'])
        status, _, body = self.write('entry', {**entry, 'feeling': 'crash'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['history'][0]['planned'], 10)
        self.assertTrue(json.loads(body)['review'])

        status, headers, body = self.request('GET', '/api/planner', headers={'Cookie': self.cookie})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertTrue(json.loads(body)['plan']['stepped_back'])
        status, _, body = self.write('mode', {'activity': 'Puzzles', 'stepped_back': False})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)['plan']['stepped_back'])

    def test_cross_origin_write_and_invalid_plan_are_rejected(self):
        self.authenticate()
        plan = {'activity': 'Puzzles', 'limit': 10, 'step_back': 12}
        status, _, _ = self.write('plan', plan, 'http://another.test')
        self.assertEqual(status, 403)
        status, _, _ = self.write('plan', plan)
        self.assertEqual(status, 400)

    def test_anonymous_visitors_cannot_read_write_or_register(self):
        status, headers, _ = self.request('GET', '/')
        self.assertEqual((status, headers['Location']), (303, '/login'))
        self.assertEqual(self.request('GET', '/api/planner')[0], 401)
        for path, expected in (('/api/planner/plan', 401), ('/register', 404)):
            result = self.request('POST', path, '{}',
                                  {'Origin': self.origin, 'Content-Type': 'application/json'})
            self.assertEqual(result[0], expected)
        self.assertEqual(self.sign_in('missing')[0], 401)
        self.assertEqual(self.sign_in(Origin='https://elsewhere.test')[0], 403)

    def test_remembered_session_can_be_revoked_by_signout(self):
        status, headers, _ = self.sign_in(remember=True)
        self.assertEqual(status, 303)
        cookie = headers['Set-Cookie']
        for attribute in ('HttpOnly', 'SameSite=Lax', f'Max-Age={REMEMBER_SECONDS}'):
            self.assertIn(attribute, cookie)
        request_headers = {'Cookie': cookie.partition(';')[0], 'Origin': self.origin}
        status, headers, _ = self.request('POST', '/logout', headers=request_headers)
        self.assertEqual((status, headers['Location']), (303, '/login'))
        self.assertEqual(headers['X-Planner-App'], '1')
        self.assertIn('Max-Age=0', headers['Set-Cookie'])
        self.assertEqual(self.request('GET', '/api/planner', headers=request_headers)[0], 401)

    def test_two_accounts_are_isolated_and_old_tabs_cannot_write(self):
        self.authenticate()
        self.assertEqual(self.write('plan', {'activity': 'Reading', 'limit': 7})[0], 200)
        first_cookie, first_token = self.cookie, self.write_token
        self.authenticate('Second')
        status, _, body = self.request('GET', '/api/planner', headers={'Cookie': self.cookie})
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)['plan'])
        self.assertEqual(self.write('plan', {'activity': 'Walking', 'limit': 12})[0], 200)
        self.write_token = first_token
        self.assertEqual(self.write('plan', {'activity': 'Reading', 'limit': 8})[0], 409)
        status, _, body = self.request('GET', '/api/planner', headers={'Cookie': first_cookie})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['plan']['activity'], 'Reading')

    def test_configured_https_proxy_requires_correct_host_and_sets_secure_cookie(self):
        origin = 'https://planner.example.net'
        self.server.https_origin = origin
        try:
            self.assertEqual(self.request('GET', '/login')[0], 403)
            headers = {'Host': 'planner.example.net', 'Origin': origin}
            status, response, _ = self.sign_in(remember=True, **headers)
            self.assertEqual(status, 303)
            self.assertTrue(response['Set-Cookie'].startswith('__Host-planner_session='))
            self.assertIn('Secure', response['Set-Cookie'])
        finally:
            self.server.https_origin = None


if __name__ == '__main__':
    unittest.main()
