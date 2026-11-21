"""Run the ME/CFS Recovery Planner on this computer."""

import argparse
from getpass import GetPassWarning, getpass
import hmac
from html import escape
from http.cookies import CookieError, SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from shutil import copyfileobj
import socket
import sqlite3
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlsplit
import warnings

from accounts import Accounts, LoginBusy, REMEMBER_SECONDS, write_token
from planner import DATA_FILE, PlannerStore


HOST = '127.0.0.1'
DEFAULT_PORT = 8022
PAGE = Path(__file__).resolve().parent / 'web' / 'index.html'
ASSETS = {
    '/planner.css': (PAGE.with_name('planner.css'), 'text/css'),
    '/planner.js': (PAGE.with_name('planner.js'), 'text/javascript'),
}


class PlannerServer(ThreadingHTTPServer):
    # Windows' SO_REUSEADDR can let two servers bind the same address.
    allow_reuse_address = not hasattr(socket, 'SO_EXCLUSIVEADDRUSE')
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class PlannerHandler(BaseHTTPRequestHandler):
    timeout = 10

    @property
    def origin(self):
        return getattr(self.server, 'https_origin', None) or f'http://{HOST}:{self.server.server_port}'

    @property
    def cookie_name(self):
        return ('__Host-planner_session' if self.origin.startswith('https://')
                else f'planner_session_{self.server.server_port}')

    def session_token(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            cookie = cookies.get(self.cookie_name)
            return cookie.value if cookie else ''
        except CookieError:
            return ''

    def session_cookie(self, token, max_age=None):
        cookie = f'{self.cookie_name}={token}; Path=/; HttpOnly; SameSite=Lax'
        if self.origin.startswith('https://'):
            cookie += '; Secure'
        if max_age is not None:
            cookie += f'; Max-Age={max_age}'
        return {'Set-Cookie': cookie}

    def account(self):
        return self.server.accounts.session_user(self.session_token())

    def planner(self, user):
        return PlannerStore(self.server.accounts.planner_path(user[0]))

    def do_GET(self):
        self.send_resource(include_body=True)

    def do_HEAD(self):
        self.send_resource(include_body=False)

    def allowed_host(self):
        hosts = self.headers.get_all('Host', [])
        return len(hosts) == 1 and hosts[0].lower() == urlsplit(self.origin).netloc

    def send_resource(self, *, include_body):
        if not self.allowed_host():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        path = self.path.partition('?')[0]
        if path in ASSETS:
            file, content_type = ASSETS[path]
            self.send_content(file.read_bytes(), content_type, include_body=include_body)
        elif path in {'/', '/login', '/api/planner'}:
            try:
                user = self.account()
                if path == '/login':
                    if user:
                        self.redirect('/')
                    else:
                        self.login_page(include_body=include_body)
                elif path == '/':
                    if user:
                        self.send_content(PAGE.read_bytes(), 'text/html', include_body=include_body)
                    else:
                        self.redirect('/login')
                elif user:
                    self.send_json({**self.planner(user).read(), 'username': user[1],
                                    'write_token': write_token(self.session_token())},
                                   include_body=include_body)
                else:
                    self.send_json({'error': 'Please sign in.'}, HTTPStatus.UNAUTHORIZED,
                                   include_body=include_body)
            except (OSError, ValueError, sqlite3.Error):
                self.send_json({'error': 'Could not open the local planner.'},
                               HTTPStatus.INTERNAL_SERVER_ERROR, include_body=include_body)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if not self.allowed_host() or self.headers.get_all('Origin') != [self.origin]:
            self.send_json({'error': 'Open the planner at its local address.'}, HTTPStatus.FORBIDDEN)
            return
        if self.path in {'/login', '/logout'}:
            try:
                if self.path == '/login':
                    self.sign_in()
                else:
                    self.server.accounts.sign_out(self.session_token())
                    self.redirect('/login', extra=self.session_cookie('', 0))
            except (OSError, sqlite3.Error):
                self.login_page('Could not open the local accounts. Try again.', HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        action = self.path.removeprefix('/api/planner/')
        if action not in {'plan', 'entry', 'mode', 'roadmap', 'routine'} or self.path != f'/api/planner/{action}':
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            user = self.account()
        except sqlite3.Error:
            self.send_json({'error': 'Could not open the local accounts.'}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if not user:
            self.send_json({'error': 'Please sign in.'}, HTTPStatus.UNAUTHORIZED)
            return
        submitted = self.headers.get('X-Planner-Session', '')
        expected = write_token(self.session_token())
        if not submitted.isascii() or not hmac.compare_digest(submitted, expected):
            self.send_json({'error': 'Your sign-in changed. Reload the page before saving.'},
                           HTTPStatus.CONFLICT)
            return
        if self.headers.get_content_type() != 'application/json':
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            payload = json.loads(self.read_body())
            if not isinstance(payload, dict):
                raise ValueError
        except ValueError:
            self.send_json({'error': 'The planner could not read this submission.'}, HTTPStatus.BAD_REQUEST)
            return
        try:
            result = self.planner(user).update(action, payload)
        except (OSError, json.JSONDecodeError):
            self.send_json({'error': 'Could not save to the local planner.'}, HTTPStatus.INTERNAL_SERVER_ERROR)
        except ValueError as error:
            self.send_json({'error': str(error)}, HTTPStatus.BAD_REQUEST)
        else:
            self.send_json(result)

    def read_body(self):
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1 or self.headers.get('Transfer-Encoding'):
            raise ValueError
        length = int(lengths[0])
        if not 0 < length <= 8192:
            raise ValueError
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError
        return body

    def sign_in(self):
        if self.headers.get_content_type() != 'application/x-www-form-urlencoded':
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            fields = parse_qs(self.read_body().decode('ascii'), max_num_fields=3, errors='strict')
            username = fields.get('username', [''])[0]
            password = fields.get('password', [''])[0]
            remember = fields.get('remember') == ['yes']
        except ValueError:
            self.login_page('Enter your username and password.', HTTPStatus.BAD_REQUEST)
            return
        try:
            token = self.server.accounts.login(username, password, remember)
        except LoginBusy:
            self.login_page('Too many sign-in attempts. Try again in a few minutes.', HTTPStatus.TOO_MANY_REQUESTS)
            return
        if not token:
            self.login_page('That username or password didn’t match.', HTTPStatus.UNAUTHORIZED)
            return
        self.server.accounts.sign_out(self.session_token())
        self.redirect('/', extra=self.session_cookie(token, REMEMBER_SECONDS if remember else None))

    def login_page(self, error='', status=HTTPStatus.OK, *, include_body=True):
        template = PAGE.with_name('login.html').read_text(encoding='utf-8')
        message = f'<p role="alert" class="error">{escape(error)}</p>' if error else ''
        page = template.replace('<!-- sign-in status -->', message)
        self.send_content(page.encode('utf-8'), 'text/html', status, include_body=include_body)

    def redirect(self, location, *, extra=None):
        self.send_content(b'', 'text/plain', HTTPStatus.SEE_OTHER, include_body=False,
                          extra={'Location': location, **(extra or {})})

    def send_json(self, data, status=HTTPStatus.OK, *, include_body=True):
        self.send_content(json.dumps(data).encode('utf-8'), 'application/json', status,
                          include_body=include_body)

    def send_content(self, data, content_type, status=HTTPStatus.OK, *, include_body=True, extra=None):
        self.send_response(status)
        self.send_header('Content-Type', f'{content_type}; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Planner-App', '1')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if include_body:
            self.wfile.write(data)

    def log_message(self, format, *args):
        pass


def validate_https_origin(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.path or parsed.query or parsed.fragment or port in (0, 443)
                or any(char.isspace() for char in value)
                or value.lower() != f'https://{parsed.netloc.lower()}'):
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError('Use an HTTPS origin, such as https://planner.example.net.') from None
    return value.lower()


def manage_account(accounts, args):
    if args.import_planner is not None:
        username = args.import_planner
        user = accounts.user_id(username)
        if user is None:
            raise ValueError('Create the local user before importing a planner.')
        if not DATA_FILE.is_file():
            raise ValueError('There is no existing local planner to import.')
        destination = accounts.planner_path(user)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            source_copy = Path(temporary.name)
            try:
                with DATA_FILE.open('rb') as source:
                    copyfileobj(source, temporary)
                temporary.close()
                destination.hardlink_to(source_copy)
            except FileExistsError:
                raise ValueError('This user already has planner data.') from None
            finally:
                temporary.close()
                source_copy.unlink()
        print('Existing planner imported. The original file is still in local_data.')
        return
    create = args.add_user is not None
    username = args.add_user if create else args.reset_password
    with warnings.catch_warnings():
        warnings.simplefilter('error', GetPassWarning)
        password = getpass('New passphrase: ')
        if password != getpass('Repeat passphrase: '):
            raise ValueError('The passphrases did not match.')
    accounts.set_password(username, password, create=create)
    print('Local account created.' if create else 'Password changed and existing sessions signed out.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='local port (default: %(default)s)')
    parser.add_argument('--https-origin', type=validate_https_origin,
                        help='browser-facing HTTPS origin for a local reverse proxy')
    account = parser.add_mutually_exclusive_group()
    account.add_argument('--add-user', metavar='USERNAME', help='create a user and prompt for a passphrase')
    account.add_argument('--reset-password', metavar='USERNAME', help='replace a local user’s passphrase')
    account.add_argument('--import-planner', metavar='USERNAME', help='give existing local data to one user')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')

    try:
        accounts = Accounts()
        accounts.initialize()
        if args.add_user is not None or args.reset_password is not None or args.import_planner is not None:
            manage_account(accounts, args)
            return
        with PlannerServer((HOST, args.port), PlannerHandler) as server:
            server.accounts = accounts
            server.https_origin = args.https_origin
            address = args.https_origin or f'http://{HOST}:{args.port}'
            print(f'ME/CFS Recovery Planner is running at {address}', flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped the planner.')
    except (EOFError, GetPassWarning):
        parser.exit(1, 'Run the account command in a terminal with a hidden passphrase prompt.\n')
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'Could not run the planner: {error}\n')


if __name__ == '__main__':
    main()
