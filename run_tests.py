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
from guidance import evaluate_assessment, level_activities
from planner import PlannerStore, blank_state
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
        source.write_text('{"version": 2, "profile": null}', encoding='utf-8')
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


class AssessmentTests(unittest.TestCase):
    def test_bedbound_or_walk_crash_starts_conservatively_in_phase_one(self):
        severe = evaluate_assessment({
            'upright': 0, 'walk_10': 0, 'household': 0, 'mental': 0, 'stability': 0,
        })
        self.assertEqual(severe['recommended_level'], 1)
        self.assertEqual(severe['phase'], 1)

        walk_crash = evaluate_assessment({
            'upright': 2, 'walk_10': 1, 'household': 2, 'mental': 2, 'stability': 1,
        })
        self.assertLessEqual(walk_crash['recommended_level'], 3)
        self.assertEqual(walk_crash['phase'], 1)

    def test_steady_ten_minute_walker_starts_in_phase_two(self):
        moderate = evaluate_assessment({
            'upright': 3, 'walk_10': 3, 'household': 2, 'mental': 3, 'stability': 2,
        })
        self.assertGreaterEqual(moderate['recommended_level'], 5)
        self.assertLessEqual(moderate['recommended_level'], 7)
        self.assertEqual(moderate['phase'], 2)

    def test_invalid_answers_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_assessment({'upright': 1})
        with self.assertRaises(ValueError):
            evaluate_assessment({
                'upright': 5, 'walk_10': 1, 'household': 1, 'mental': 1, 'stability': 1,
            })


class ProgramGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.day0 = date(2026, 1, 1)
        self.store = PlannerStore()
        self.state = blank_state()
        self.store.apply(
            self.state,
            'assessment',
            {
                'answers': {
                    'upright': 2, 'walk_10': 2, 'household': 2, 'mental': 2, 'stability': 2,
                },
                'starting_level': 4,
            },
            self.day0,
        )

    def log(self, offset, feeling='steady', **fields):
        day = self.day0 + timedelta(days=offset)
        self.store.apply(
            self.state,
            'checkin',
            {'date': day.isoformat(), 'feeling': feeling, **fields},
            day,
        )

    def view(self, offset=0):
        return self.store.view(self.state, self.day0 + timedelta(days=offset))

    def test_prepopulated_activities_and_optional_category_toggles(self):
        v = self.view()
        ids = {item['id'] for item in v['program']['activities']}
        self.assertEqual(ids, {'rest', 'household', 'walking', 'stretching', 'mental', 'social'})

        self.store.apply(
            self.state,
            'preferences',
            {'disabled_categories': ['Social']},
            self.day0,
        )
        v2 = self.view()
        ids2 = {item['id'] for item in v2['program']['activities']}
        self.assertNotIn('social', ids2)
        self.assertIn('walking', ids2)
        self.assertIn('mental', ids2)

        # Cushioned scaling reduces activity minutes proportionally.
        cushioned = level_activities(4, cushion_pct=15)
        walk = next(item for item in cushioned if item['id'] == 'walking')
        self.assertEqual(walk['minutes'], 7)

    def test_hold_window_step_up_and_reassess_five_days_shift_projection(self):
        # Level 4 default hold_days is 24.
        for offset in range(23):
            self.log(offset, 'steady', activities={'walking': 'just_right', 'mental': 'just_right'})
        v = self.view(22)
        self.assertFalse(v['program']['step_up_ready'])
        self.assertEqual(v['program']['steady_days'], 23)

        self.log(23, 'steady', activities={'walking': 'could_do_more'})
        v = self.view(23)
        self.assertTrue(v['program']['step_up_ready'])
        base_eta = date.fromisoformat(v['trajectory']['estimated_full_recovery_date'])

        # Choosing "Reassess in 5 days" extends hold by 5 and shifts Level 12 projection by 5 days.
        self.store.apply(self.state, 'decision', {'choice': 'hold_five'}, self.day0 + timedelta(days=23))
        v_held = self.view(23)
        self.assertFalse(v_held['program']['step_up_ready'])
        self.assertEqual(v_held['program']['hold_days'], 29)
        shifted_eta = date.fromisoformat(v_held['trajectory']['estimated_full_recovery_date'])
        self.assertEqual((shifted_eta - base_eta).days, 5)

        # Complete 5 more steady days then advance to Level 5.
        for offset in range(24, 29):
            self.log(offset, 'steady')
        v_ready = self.view(28)
        self.assertTrue(v_ready['program']['step_up_ready'])
        self.store.apply(self.state, 'decision', {'choice': 'advance'}, self.day0 + timedelta(days=28))
        v_next = self.view(28)
        self.assertEqual(v_next['program']['level'], 5)
        self.assertEqual(v_next['program']['steady_days'], 0)

    def test_beyond_plan_benchmark_delayed_crash_and_tolerated(self):
        # Tolerated unplanned event after 3 steady follow-ups
        self.log(0, 'steady', beyond_plan=[{'label': 'Short coffee', 'effort': 'light', 'minutes': 20}])
        self.log(1, 'steady')
        self.log(2, 'steady')
        # Still watching inside 3-day window — blocks step-up even if hold_days were shorter
        self.assertIsNotNone(self.view(2)['program']['pending_watch'])
        self.log(3, 'steady')
        v = self.view(3)
        self.assertIsNone(v['program']['pending_watch'])
        self.assertEqual(v['benchmarks'][0]['outcome'], 'tolerated')

        # Unplanned drive followed by crash 2 days later -> not_ready + enters stabilization
        self.log(10, 'steady', beyond_plan=[{'label': 'Long drive', 'effort': 'heavy', 'minutes': 60}])
        self.log(11, 'worn')
        self.log(12, 'crash')
        v_crash = self.view(12)
        self.assertEqual(v_crash['program']['mode'], 'stabilizing')
        self.assertEqual(v_crash['benchmarks'][0]['label'], 'Long drive')
        self.assertEqual(v_crash['benchmarks'][0]['outcome'], 'not_ready')
        self.assertIn('2 days later', v_crash['benchmarks'][0]['outcome_text'])

    def test_two_worse_days_and_adaptive_step_back_learning(self):
        # First setback: 2 consecutive worse days early at Level 4 with no external trigger -> step back to 3.
        self.log(0, 'steady')
        self.log(1, 'worse')
        self.log(2, 'worse')
        v_stab = self.view(2)
        self.assertEqual(v_stab['program']['mode'], 'stabilizing')
        self.assertFalse(v_stab['program']['ready_to_resume'])

        # 2 steady days unlock resume recommendation to Level 3.
        self.log(3, 'steady')
        self.log(4, 'steady')
        v_ready = self.view(4)
        self.assertTrue(v_ready['program']['ready_to_resume'])
        self.assertEqual(v_ready['program']['resume_recommendation']['recommended_level'], 3)
        self.assertEqual(v_ready['program']['resume_recommendation']['cushion_pct'], 0)

        self.store.apply(self.state, 'decision', {'choice': 'resume'}, self.day0 + timedelta(days=4))
        v_resumed = self.view(4)
        self.assertEqual(v_resumed['program']['mode'], 'active')
        self.assertEqual(v_resumed['program']['level'], 3)

        # Second crash within 21 days -> adaptive engine steps back further + applies 15% cushion & +7 hold days.
        self.log(7, 'crash')
        self.log(8, 'steady')
        self.log(9, 'steady')
        v_repeat = self.view(9)
        rec = v_repeat['program']['resume_recommendation']
        self.assertEqual(rec['recommended_level'], 1)
        self.assertEqual(rec['cushion_pct'], 15)
        self.assertEqual(rec['extra_hold_days'], 7)

        self.store.apply(self.state, 'decision', {'choice': 'resume'}, self.day0 + timedelta(days=9))
        v_soft = self.view(9)
        self.assertEqual(v_soft['program']['level'], 1)
        self.assertEqual(v_soft['program']['cushion_pct'], 15)
        self.assertEqual(v_soft['program']['hold_days'], 28)

    def test_external_trigger_after_seven_steady_days_offers_same_level_resume(self):
        for offset in range(8):
            self.log(offset, 'steady')
        self.log(8, 'steady', beyond_plan=[{'label': 'Medical appointment', 'effort': 'medium'}])
        self.log(10, 'crash')
        self.log(11, 'steady')
        self.log(12, 'steady')
        v = self.view(12)
        rec = v['program']['resume_recommendation']
        self.assertEqual(rec['recommended_level'], 4)
        self.assertTrue(rec['external_trigger'])


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

    def write(self, action, payload, origin=None):
        return self.request('POST', f'/api/planner/{action}', json.dumps(payload),
                            {'Content-Type': 'application/json', 'Origin': origin or self.origin,
                             'Cookie': self.cookie, 'X-Planner-Session': self.write_token})

    def test_home_page(self):
        self.authenticate()
        status, headers, body = self.request('GET', '/?test=1', headers={'Cookie': self.cookie})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn(b'ME/CFS Recovery Planner', body)
        self.assertIn(b'id="trajectory-chart"', body)
        self.assertIn(b'id="onboarding" class="onboarding" hidden', body)
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

    def test_end_to_end_assessment_checkin_preferences_and_crash_flow(self):
        self.authenticate()
        status, _, body = self.write('assessment', {
            'answers': {'upright': 2, 'walk_10': 2, 'household': 2, 'mental': 2, 'stability': 2},
            'starting_level': 4,
        })
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data['onboarded'])
        self.assertEqual(data['program']['level'], 4)
        today = data['today']

        status, _, body = self.write('checkin', {
            'date': today,
            'feeling': 'crash',
            'activities': {'walking': 'too_much', 'rest': 'just_right'},
            'factors': ['sleep'],
            'beyond_plan': [{'label': 'Family drive', 'effort': 'heavy', 'minutes': 45}],
            'note': 'Overdid the afternoon',
        })
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data['program']['mode'], 'stabilizing')
        self.assertEqual(data['benchmarks'][0]['outcome'], 'not_ready')

        status, _, body = self.write('preferences', {'disabled_categories': ['Social'], 'hold_scale': 1.25})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['profile']['disabled_categories'], ['Social'])

        status, _, body = self.write('decision', {'choice': 'resume', 'level': 3})
        self.assertEqual(status, 200)
        resumed = json.loads(body)
        self.assertEqual(resumed['program']['mode'], 'active')
        self.assertEqual(resumed['program']['level'], 3)

    def test_cross_origin_write_and_invalid_payloads_are_rejected(self):
        self.authenticate()
        bad_assessment = {'answers': {'upright': 99}}
        status, _, _ = self.write('assessment', bad_assessment, 'http://another.test')
        self.assertEqual(status, 403)
        status, _, _ = self.write('assessment', bad_assessment)
        self.assertEqual(status, 400)

    def test_anonymous_visitors_cannot_read_write_or_register(self):
        status, headers, _ = self.request('GET', '/')
        self.assertEqual((status, headers['Location']), (303, '/login'))
        self.assertEqual(self.request('GET', '/api/planner')[0], 401)
        for path, expected in (('/api/planner/assessment', 401), ('/register', 404)):
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
        self.assertEqual(self.write('assessment', {
            'answers': {'upright': 1, 'walk_10': 1, 'household': 1, 'mental': 1, 'stability': 1},
            'starting_level': 2,
        })[0], 200)
        first_cookie, first_token = self.cookie, self.write_token
        self.authenticate('Second')
        status, _, body = self.request('GET', '/api/planner', headers={'Cookie': self.cookie})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)['onboarded'])
        self.assertEqual(self.write('assessment', {
            'answers': {'upright': 3, 'walk_10': 3, 'household': 3, 'mental': 3, 'stability': 3},
            'starting_level': 6,
        })[0], 200)
        self.write_token = first_token
        self.assertEqual(self.write('decision', {'choice': 'set_level', 'level': 3})[0], 409)
        status, _, body = self.request('GET', '/api/planner', headers={'Cookie': first_cookie})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['program']['level'], 2)

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
