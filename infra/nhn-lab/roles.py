#!/usr/bin/env python3
"""Operator-only NHN IAM role batch tool. No cloud resource creation or deletion."""
import argparse
import base64
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import warnings

CORE = 'https://core.api.nhncloudservice.com'
AUTH = 'https://oauth.api.nhncloudservice.com'
ROLE_NAMES = ['Infrastructure VIEWER', 'Object Storage Object READER',
              'Object Storage Object WRITER', 'RDS for MySQL VIEWER']
DEFAULT_ORG = '8NQqYpYUnlEnixaG'
DEFAULT_ANCHOR = 'srwJJxcH'


class LabError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Api:
    def __init__(self, key, secret):
        basic = base64.b64encode((key + ':' + secret).encode()).decode()
        self.basic = 'Basic ' + basic
        self.token = None
        self.opener = urllib.request.build_opener(NoRedirect())

    def _request(self, method, url, headers, body):
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise LabError('API response too large')
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            # Only emit endpoint path and allowlisted machine codes; never raw bodies/messages.
            location = urllib.parse.urlsplit(url).path
            codes = []
            try:
                data = json.loads(error.read(65536))
                if isinstance(data, dict):
                    oauth = data.get('error')
                    if isinstance(oauth, str) and oauth in {'invalid_request', 'invalid_client', 'invalid_grant', 'unauthorized_client', 'unsupported_grant_type', 'invalid_scope', 'access_denied', 'server_error', 'temporarily_unavailable'}:
                        codes.append('oauth=' + oauth)
                    header = data.get('header')
                    code = header.get('resultCode') if isinstance(header, dict) else None
                    if type(code) is int:
                        codes.append('resultCode=' + str(code))
            except (ValueError, OSError, UnicodeError):
                pass
            suffix = ('; ' + ', '.join(codes)) if codes else '; no safe error code provided'
            raise LabError(method + ' ' + location + ': HTTP ' + str(error.code) + suffix) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise LabError('API network/TLS error; no automatic write retry') from None
        except (ValueError, UnicodeError):
            raise LabError('Invalid API response') from None

    def login(self):
        data = self._request('POST', AUTH + '/oauth2/token/create',
                             {'Authorization': self.basic, 'Content-Type': 'application/x-www-form-urlencoded'},
                             urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode())
        if not isinstance(data.get('access_token'), str) or data.get('token_type', '').lower() != 'bearer':
            raise LabError('Authentication did not return a Bearer token')
        self.token = data['access_token']
        print('AUTH_OK: token issued (token value hidden)', flush=True)

    def close(self):
        if self.token:
            try:
                self._request('POST', AUTH + '/oauth2/token/revoke',
                              {'Authorization': self.basic, 'Content-Type': 'application/x-www-form-urlencoded'},
                              urllib.parse.urlencode({'token': self.token}).encode())
            except LabError:
                print('Token revocation could not be confirmed; it will expire at its configured lifetime.', file=sys.stderr)
        self.token = None
        self.basic = ''

    def call(self, method, path, body=None, query=None):
        if not self.token or not re.fullmatch(r'/v1/[A-Za-z0-9_./-]+', path) or '..' in path:
            raise LabError('Invalid API request path')
        url = CORE + path
        if query:
            url += '?' + urllib.parse.urlencode(query, doseq=True)
        data = self._request(method, url, {'x-nhn-authorization': 'Bearer ' + self.token,
                                         'Content-Type': 'application/json'},
                             None if body is None else json.dumps(body).encode())
        if not isinstance(data, dict) or data.get('header', {}).get('isSuccessful') is not True:
            code = data.get('header', {}).get('resultCode', 'unknown') if isinstance(data, dict) else 'invalid'
            if not isinstance(code, int):
                code = 'unknown'
            raise LabError('API rejected request; resultCode=' + str(code))
        return data


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
        raise LabError('Invalid API identifier')
    return value


def paged(api, path, key, query=None):
    items, seen = [], set()
    for page in range(1, 101):
        response = api.call('GET', path, query={**(query or {}), 'limit': 20, 'page': page})
        batch = response.get(key)
        total = response.get('totalCount', response.get('paging', {}).get('totalCount'))
        if not isinstance(batch, list) or type(total) is not int or total < 0:
            raise LabError('Unexpected pagination schema; no permissions changed')
        for item in batch:
            marker = item.get('projectId') or item.get('uuid') or item.get('roleId')
            if not marker or marker in seen:
                raise LabError('Duplicate or incomplete paginated records')
            seen.add(marker)
            items.append(item)
        if len(items) == total:
            return items
        if not batch or len(items) > total:
            raise LabError('Pagination changed during scan; retry plan')
    raise LabError('Too many API pages')


def assignments(roles):
    if not isinstance(roles, list) or not roles:
        raise LabError('Empty or missing role assignments')
    result = []
    for role in roles:
        if role.get('roleApplyPolicyCode', 'ALLOW') != 'ALLOW':
            raise LabError('Non-ALLOW assignment requires manual review')
        role_id = role.get('roleId')
        if not isinstance(role_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', role_id):
            raise LabError('Invalid role ID')
        entry = {'roleId': role_id}
        conditions = []
        for condition in role.get('conditions') or []:
            values = condition.get('attributeValues')
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise LabError('Invalid role conditions')
            conditions.append({'attributeId': ident(condition.get('attributeId')),
                               'attributeOperatorTypeCode': ident(condition.get('attributeOperatorTypeCode')),
                               'attributeValues': sorted(values)})
        if conditions:
            entry['conditions'] = sorted(conditions, key=lambda c: json.dumps(c, sort_keys=True))
        result.append(entry)
    if len({r['roleId'] for r in result}) != len(result):
        raise LabError('Duplicate role assignments')
    return sorted(result, key=lambda r: r['roleId'])


def normal(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def desired_roles(roles):
    selected = []
    for name in ROLE_NAMES:
        matches = [r for r in roles if normal(r.get('roleName')) == normal(name)
                   and r.get('categoryTypeCode') == 'ROLE'
                   and r.get('roleCategory') == 'PROJECT_SERVICE_ROLE']
        if len(matches) != 1:
            raise LabError('Expected one service role named ' + name + '; catalogue differs, no write allowed')
        selected.append(matches[0])
    return selected


def member(api, project, uuid, iam=True):
    path = '/v1/' + ('iam/' if iam else '') + 'projects/' + ident(project) + '/members/' + ident(uuid)
    data = api.call('GET', path).get('projectMember')
    if not isinstance(data, dict) or data.get('uuid') != uuid:
        raise LabError('Member lookup identity mismatch')
    return data


def operator(api, project, email):
    found, seen = [], set()
    for page in range(1, 101):
        response = api.call('POST', '/v1/projects/' + ident(project) + '/members/search',
                            {'paging': {'limit': 20, 'page': page}})
        batch = response.get('projectMembers')
        total = response.get('paging', {}).get('totalCount')
        if not isinstance(batch, list) or type(total) is not int:
            raise LabError('Unexpected project member pagination')
        for item in batch:
            uuid = ident(item.get('uuid'))
            if uuid in seen:
                raise LabError('Duplicate project members')
            seen.add(uuid)
            if item.get('memberTypeCode') == 'TOAST_CLOUD' and normal(item.get('emailAddress')) == normal(email):
                found.append(item)
        if len(seen) == total:
            break
        if not batch or len(seen) > total:
            raise LabError('Project member list changed')
    else:
        raise LabError('Too many project member pages')
    if len(found) != 1:
        raise LabError('Expected operator ' + email + ' not uniquely visible in project ' + project)
    detail = member(api, project, found[0]['uuid'], iam=False)
    if not any(r.get('roleName') == 'ADMIN' and r.get('categoryKey') == 'ProjectRole'
               and not r.get('conditions') for r in detail.get('roles', [])):
        raise LabError('Operator has no direct unconditional project ADMIN; no changes permitted')
    return {'uuid': found[0]['uuid'], 'roles': assignments(detail['roles'])}


def settings(args):
    if not 1 <= args.start <= args.end <= 20:
        raise LabError('Range must be within 01..20')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,35}', args.project_prefix):
        raise LabError('Invalid project prefix')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{1,15}', args.student_prefix):
        raise LabError('Invalid student prefix')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', args.operator_email):
        raise LabError('Invalid operator email')
    return {'orgId': ident(args.org_id), 'projectPrefix': args.project_prefix,
            'studentPrefix': args.student_prefix, 'start': args.start, 'end': args.end,
            'operatorEmail': args.operator_email.lower(), 'anchorProjectId': ident(args.anchor_project_id)}


def build_plan(api, config):
    org = ident(config['orgId'])
    projects = paged(api, '/v1/organizations/' + org + '/projects', 'projectList')
    if any(p.get('orgId') != org or p.get('projectStatusCode') != 'STABLE' for p in projects):
        raise LabError('Organization/project status mismatch')
    anchor = [p for p in projects if p.get('projectName') == config['projectPrefix'] + '01']
    if len(anchor) != 1 or anchor[0]['projectId'] != config['anchorProjectId']:
        raise LabError('Pro01 anchor differs from expected organization; no changes allowed')
    targets = {config['studentPrefix'] + f'{i:02d}': config['projectPrefix'] + f'{i:02d}'
               for i in range(config['start'], config['end'] + 1)}
    selected = {}
    for username, name in targets.items():
        matches = [p for p in projects if p.get('projectName') == name]
        if len(matches) != 1:
            raise LabError('Missing or duplicate project ' + name + '; creation is separate')
        selected[username] = matches[0]
    memberships = {}
    for project in projects:
        pid = ident(project['projectId'])
        records = paged(api, '/v1/iam/projects/' + pid + '/members', 'projectMembers')
        memberships[pid] = records
        for item in records:
            username = item.get('id')
            if username in targets and pid != selected[username]['projectId']:
                raise LabError(username + ' also belongs to ' + project['projectName'] + '; resolve extra membership first')
    rows = []
    for username, project in selected.items():
        pid = project['projectId']
        records = [m for m in memberships[pid] if m.get('id') == username]
        if len(records) != 1:
            raise LabError('Expected exactly one ' + username + ' in ' + project['projectName'])
        uuid = ident(records[0]['uuid'])
        detail = member(api, pid, uuid)
        if detail.get('id') != username:
            raise LabError('IAM username mismatch')
        protected = operator(api, pid, config['operatorEmail'])
        if protected['uuid'] == uuid:
            raise LabError('Student matches protected operator')
        catalog = paged(api, '/v1/projects/' + pid + '/roles', 'roles', {'categoryTypeCodes': ['ROLE']})
        desired = desired_roles(catalog)
        before = assignments(detail.get('roles'))
        rows.append({'projectId': pid, 'projectName': project['projectName'], 'username': username,
                     'memberUuid': uuid, 'before': before, 'beforeNames': [r.get('roleName', r['roleId']) for r in detail['roles']],
                     'after': assignments(desired), 'operator': protected})
    return {'version': 1, 'config': config, 'rows': rows}


def fingerprint(plan):
    # Names are display-only; roles, identities, conditions and operator snapshot are binding.
    bound = {'version': plan['version'], 'config': plan['config'],
             'rows': [{k: v for k, v in row.items() if k != 'beforeNames'} for row in plan['rows']]}
    return hashlib.sha256(json.dumps(bound, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def print_plan(plan):
    print('Organization:', plan['config']['orgId'], '| protected operator:', plan['config']['operatorEmail'])
    print('Target roles:', ', '.join(ROLE_NAMES))
    for row in plan['rows']:
        state = 'NO CHANGE' if row['before'] == row['after'] else 'REPLACE'
        print(row['projectName'], '<->', row['username'], '|', state, '| current:', ', '.join(row['beforeNames']))
    print('Infrastructure VIEWER includes Key Pair/Direct Connect/NAS(Offline) write exceptions; not strict read-only.')
    print('Only existing project IAM role assignments are changed; no infrastructure, passwords or LMS records are modified.')


def apply_plan(api, saved, log_path):
    fresh = build_plan(api, saved['config'])
    if fingerprint(fresh) != fingerprint(saved):
        raise LabError('Plan is stale or edited. Run plan again before any writes.')
    journal = {'version': 1, 'plan': saved, 'results': []}
    # O_EXCL ensures the complete rollback material exists before the first mutation.
    save_json(log_path, journal)
    def record():
        temp = Path(str(log_path) + '.tmp')
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as file:
            json.dump(journal, file, ensure_ascii=False, indent=2)
        os.replace(temp, log_path)
    for row in fresh['rows']:
        result = {'projectName': row['projectName'], 'username': row['username'], 'status': 'PENDING'}
        journal['results'].append(result)
        record()
        try:
            current = member(api, row['projectId'], row['memberUuid'])
            if current.get('id') != row['username'] or assignments(current.get('roles')) != row['before']:
                raise LabError('Student changed after preflight')
            if operator(api, row['projectId'], saved['config']['operatorEmail']) != row['operator']:
                raise LabError('Operator roles changed after preflight')
            if row['before'] != row['after']:
                result['status'] = 'WRITE_REQUESTED'
                record()
                api.call('PUT', '/v1/iam/projects/' + row['projectId'] + '/members/' + row['memberUuid'],
                         {'assignRoles': row['after']})
            verified = member(api, row['projectId'], row['memberUuid'])
            if verified.get('id') != row['username'] or assignments(verified.get('roles')) != row['after']:
                raise LabError('Read-back verification failed')
            if operator(api, row['projectId'], saved['config']['operatorEmail']) != row['operator']:
                raise LabError('Protected operator snapshot changed')
            result['status'] = 'VERIFIED'
            record()
            print(row['projectName'], row['username'], 'VERIFIED', flush=True)
        except LabError:
            result['status'] = 'STOPPED_CHECK_LIVE_STATE'
            record()
            raise LabError('Batch stopped at ' + row['projectName'] + '. Earlier verified rows stay applied; review journal and live roles before retry.') from None
    return journal


def credentials():
    # Refuse getpass fallback to echoing stdin (e.g. PowerShell ISE/noninteractive host).
    if not sys.stdin.isatty():
        raise LabError('Run in an interactive PowerShell/Terminal; redirected credential input is not supported')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            key = getpass.getpass('NHN User Access Key (hidden): ').strip()
            secret = getpass.getpass('NHN Secret Access Key (hidden): ').strip()
        except getpass.GetPassWarning:
            raise LabError('Hidden input unavailable; use Windows Terminal or PowerShell console') from None
    if not key or not secret or ':' in key or any(c in key + secret for c in '\r\n'):
        raise LabError('Empty or invalid key input')
    return Api(key, secret)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'apply'])
    parser.add_argument('--org-id', default=DEFAULT_ORG)
    parser.add_argument('--project-prefix', default='TBIT_Edu01_Pro')
    parser.add_argument('--student-prefix', default='educity')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=10)
    parser.add_argument('--anchor-project-id', default=DEFAULT_ANCHOR)
    parser.add_argument('--operator-email', default='web@tbit.co.kr')
    parser.add_argument('--plan', default='.nhn-lab-state/roles-01-10.plan.json')
    args = parser.parse_args()
    saved = None
    if args.action == 'apply':
        saved = json.loads(Path(args.plan).read_text(encoding='utf-8'))
        c = saved.get('config', {})
        check = argparse.Namespace(org_id=c.get('orgId'), project_prefix=c.get('projectPrefix'),
                                  student_prefix=c.get('studentPrefix'), start=c.get('start', 0), end=c.get('end', 0),
                                  anchor_project_id=c.get('anchorProjectId'), operator_email=c.get('operatorEmail'))
        if settings(check) != c or saved.get('version') != 1:
            raise LabError('Invalid saved plan configuration')
    else:
        config = settings(args)
    api = credentials()
    try:
        api.login()
        if args.action == 'plan':
            plan = build_plan(api, config)
            print_plan(plan)
            save_json(args.plan, plan)
            print('PLAN_SAVED', args.plan, '(no role changes)')
        else:
            print_plan(saved)
            phrase = saved['config']['projectPrefix'] + f"{saved['config']['start']:02d}-{saved['config']['end']:02d}"
            if input('Apply ONLY these student roles; type ' + phrase + ': ').strip() != phrase:
                raise LabError('Confirmation did not match; no role changes')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            log_path = str(Path(args.plan).parent / ('apply-' + stamp + '.json'))
            apply_plan(api, saved, log_path)
            print('APPLY_VERIFIED; backup/journal:', log_path)
    finally:
        api.close()


if __name__ == '__main__':
    try:
        main()
    except (LabError, ValueError, OSError, KeyError, TypeError) as error:
        print('ERROR:', str(error) if isinstance(error, LabError) else 'Invalid configuration or local file; no automatic retry.', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nInterrupted. Inspect the local journal before repeating an apply.', file=sys.stderr)
        sys.exit(130)
