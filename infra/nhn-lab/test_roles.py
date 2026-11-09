import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('nhn_roles', Path(__file__).with_name('roles.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

CONFIG = {'orgId': r.DEFAULT_ORG, 'projectPrefix': 'TBIT_Edu01_Pro', 'studentPrefix': 'educity',
          'start': 1, 'end': 2, 'operatorEmail': 'web@tbit.co.kr', 'anchorProjectId': r.DEFAULT_ANCHOR}


def role(role_id, name, **extra):
    return {'roleId': role_id, 'roleName': name, 'categoryTypeCode': 'ROLE',
            'roleCategory': 'PROJECT_SERVICE_ROLE', 'categoryKey': 'ProjectServiceRole', **extra}


class FakeApi:
    def __init__(self):
        self.projects = [{'orgId': r.DEFAULT_ORG, 'projectId': pid, 'projectName': f'TBIT_Edu01_Pro{i:02d}',
                          'projectStatusCode': 'STABLE'} for i, pid in enumerate([r.DEFAULT_ANCHOR, 'project2', 'project3'], 1)]
        self.catalog = [role('service.role.' + str(i), name) for i, name in enumerate(r.ROLE_NAMES)]
        self.iam = {p['projectId']: [{'id': f'educity{i:02d}', 'uuid': 'student-' + str(i)}] for i, p in enumerate(self.projects, 1)}
        self.details = {(p['projectId'], 'student-' + str(i)): {'uuid': 'student-' + str(i), 'id': f'educity{i:02d}',
                         'roles': [role('project-admin', 'ADMIN', categoryKey='ProjectRole', roleCategory='PROJECT_ROLE')]}
                        for i, p in enumerate(self.projects, 1)}
        self.admin = {'uuid': 'operator', 'roles': [role('project-admin', 'ADMIN', categoryKey='ProjectRole')]}
        self.writes = []
        self.fail_write = None
        self.readback_wrong = False

    def call(self, method, path, body=None, query=None):
        if path == '/v1/organizations/' + r.DEFAULT_ORG + '/projects':
            return {'projectList': copy.deepcopy(self.projects), 'paging': {'totalCount': len(self.projects)}}
        parts = path.strip('/').split('/')
        if parts[1] == 'iam':
            pid = parts[3]
            if len(parts) == 5:
                return {'projectMembers': copy.deepcopy(self.iam[pid]), 'paging': {'totalCount': len(self.iam[pid])}}
            key = (pid, parts[5])
            if method == 'PUT':
                self.writes.append((path, copy.deepcopy(body)))
                if self.fail_write == pid:
                    raise r.LabError('simulated timeout')
                self.details[key]['roles'] = [dict(x) for x in body['assignRoles']]
                return {}
            detail = copy.deepcopy(self.details[key])
            if self.readback_wrong and self.writes:
                detail['roles'] = [role('unexpected', 'ADMIN')]
            return {'projectMember': detail}
        pid = parts[2]
        if path.endswith('/roles'):
            return {'roles': copy.deepcopy(self.catalog), 'totalCount': len(self.catalog)}
        if method == 'POST' and path.endswith('/members/search'):
            return {'projectMembers': [{'uuid': 'operator', 'memberTypeCode': 'TOAST_CLOUD', 'emailAddress': 'web@tbit.co.kr'}],
                    'paging': {'totalCount': 1}}
        if parts[-1] == 'operator':
            return {'projectMember': copy.deepcopy(self.admin)}
        raise AssertionError((method, path))


class RoleTests(unittest.TestCase):
    def test_plan_has_no_writes_and_matches_exact_pairs(self):
        api = FakeApi(); plan = r.build_plan(api, CONFIG)
        self.assertEqual(api.writes, [])
        self.assertEqual([row['username'] for row in plan['rows']], ['educity01', 'educity02'])
        self.assertEqual(len(plan['rows'][0]['after']), 4)

    def test_apply_only_replaces_target_iam_roles_and_preserves_operator(self):
        api = FakeApi(); plan = r.build_plan(api, CONFIG); admin = copy.deepcopy(api.admin)
        third = copy.deepcopy(api.details[('project3', 'student-3')])
        with tempfile.TemporaryDirectory() as d:
            journal = r.apply_plan(api, plan, Path(d) / 'journal.json')
        self.assertEqual([x['status'] for x in journal['results']], ['VERIFIED', 'VERIFIED'])
        self.assertEqual(api.admin, admin); self.assertEqual(api.details[('project3', 'student-3')], third)
        self.assertTrue(all('/v1/iam/projects/' in path for path, _ in api.writes))
        self.assertTrue(all(len(body['assignRoles']) == 4 for _, body in api.writes))

    def test_missing_project_or_student_refuses_batch(self):
        for mode in ['project', 'student']:
            api = FakeApi()
            if mode == 'project': api.projects.pop(1)
            else: api.iam['project2'] = []
            with self.assertRaises(r.LabError): r.build_plan(api, CONFIG)
            self.assertFalse(api.writes)

    def test_cross_project_membership_blocks_changes(self):
        api = FakeApi(); api.iam['project3'].append({'id': 'educity01', 'uuid': 'student-1'})
        with self.assertRaisesRegex(r.LabError, 'also belongs'): r.build_plan(api, CONFIG)
        self.assertFalse(api.writes)

    def test_wrong_org_anchor_or_operator_admin_refuses(self):
        for mode in ['org', 'anchor', 'operator']:
            api = FakeApi()
            if mode == 'org': api.projects[0]['orgId'] = 'another-org'
            elif mode == 'anchor': api.projects[0]['projectId'] = 'wrong-id'
            else: api.admin['roles'][0]['roleName'] = 'MEMBER'
            with self.assertRaises(r.LabError): r.build_plan(api, CONFIG)
            self.assertFalse(api.writes)

    def test_role_name_collisions_and_partial_catalogs_fail_closed(self):
        for mode in ['missing', 'duplicate', 'group']:
            api = FakeApi()
            if mode == 'missing': api.catalog.pop()
            elif mode == 'duplicate': api.catalog.append(role('collision', r.ROLE_NAMES[0]))
            else: api.catalog[0]['categoryTypeCode'] = 'ROLE_GROUP'
            with self.assertRaises(r.LabError): r.build_plan(api, CONFIG)
            self.assertFalse(api.writes)

    def test_stale_or_tampered_plan_cannot_write(self):
        for mode in ['stale', 'edited']:
            api = FakeApi(); plan = r.build_plan(api, CONFIG)
            if mode == 'stale': api.details[(r.DEFAULT_ANCHOR, 'student-1')]['roles'] = [role('new-role', 'changed')]
            else: plan['rows'][0]['after'] = [{'roleId': 'project-admin'}]
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(r.LabError, 'stale or edited'): r.apply_plan(api, plan, Path(d) / 'journal.json')
            self.assertFalse(api.writes)

    def test_mid_batch_failure_retains_backup_and_stops(self):
        api = FakeApi(); plan = r.build_plan(api, CONFIG); api.fail_write = 'project2'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'journal.json'
            with self.assertRaises(r.LabError): r.apply_plan(api, plan, path)
            journal = json.loads(path.read_text())
        self.assertEqual(journal['plan'], plan)
        self.assertEqual([x['status'] for x in journal['results']], ['VERIFIED', 'STOPPED_CHECK_LIVE_STATE'])

    def test_readback_disagreement_stops_first_row(self):
        api = FakeApi(); plan = r.build_plan(api, CONFIG); api.readback_wrong = True
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(r.LabError): r.apply_plan(api, plan, Path(d) / 'journal.json')
        self.assertEqual(len(api.writes), 1)

    def test_matching_state_is_verified_without_put(self):
        api = FakeApi()
        for key in api.details:
            api.details[key]['roles'] = copy.deepcopy(api.catalog)
        plan = r.build_plan(api, CONFIG)
        with tempfile.TemporaryDirectory() as d: r.apply_plan(api, plan, Path(d) / 'journal.json')
        self.assertFalse(api.writes)

    def test_conditions_preserved_and_metadata_not_replayed(self):
        assigned = role('a.b:c', 'old', conditions=[{'attributeId': 'attribute', 'attributeOperatorTypeCode': 'ANY_CONTAINS',
                                                    'attributeValues': ['b', 'a'], 'description': 'display-only'}])
        result = r.assignments([assigned])
        self.assertEqual(result, [{'roleId': 'a.b:c', 'conditions': [{'attributeId': 'attribute',
                          'attributeOperatorTypeCode': 'ANY_CONTAINS', 'attributeValues': ['a', 'b']}]}])
        assigned['roleApplyPolicyCode'] = 'DENY'
        with self.assertRaises(r.LabError): r.assignments([assigned])

    def test_pagination_reads_all_pages_and_detects_repeated_records(self):
        class Pages:
            def call(self, method, path, body=None, query=None):
                page = query['page']; return {'items': [{'uuid': str(page)}], 'paging': {'totalCount': 2}}
        self.assertEqual(len(r.paged(Pages(), '/v1/test', 'items')), 2)
        class Repeat:
            def call(self, *args, **kwargs): return {'items': [{'uuid': 'same'}], 'paging': {'totalCount': 2}}
        with self.assertRaises(r.LabError): r.paged(Repeat(), '/v1/test', 'items')

    def test_existing_journal_prevents_all_writes(self):
        api = FakeApi(); plan = r.build_plan(api, CONFIG)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'journal.json'; path.write_text('existing')
            with self.assertRaises(FileExistsError): r.apply_plan(api, plan, path)
        self.assertFalse(api.writes)

    def test_auth_and_framework_requests_use_official_distinct_hosts(self):
        calls = []
        class Response:
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps(self.data).encode()
        class Opener:
            def open(self, req, timeout):
                calls.append(req)
                if req.full_url.endswith('/create'): return Response({'access_token': 'test-token', 'token_type': 'Bearer'})
                if req.full_url.endswith('/revoke'): return Response({})
                return Response({'header': {'isSuccessful': True}})
        api = r.Api('fake-key', 'fake-secret'); api.opener = Opener(); api.login(); api.call('GET', '/v1/organizations'); api.close()
        self.assertEqual(calls[0].full_url, r.AUTH + '/oauth2/token/create')
        self.assertEqual(calls[0].data, b'grant_type=client_credentials')
        self.assertEqual(calls[1].get_header('X-nhn-authorization'), 'Bearer test-token')
        self.assertEqual(calls[1].full_url, r.CORE + '/v1/organizations')
        self.assertNotIn('Authorization', calls[1].headers)
        self.assertEqual(api.basic, ''); self.assertIsNone(api.token)

class DiagnosticTests(unittest.TestCase):
    def test_http_error_identifies_endpoint_but_does_not_echo_credentials(self):
        import io
        import urllib.error
        class Opener:
            def open(self, request, timeout):
                body = json.dumps({'error': 'invalid_client', 'error_description': 'DO-NOT-PRINT-SECRET',
                                   'header': {'resultCode': -100, 'resultMessage': 'DO-NOT-PRINT-SECRET'}}).encode()
                raise urllib.error.HTTPError(request.full_url, 400, 'bad', {}, io.BytesIO(body))
        api = r.Api('hidden-key', 'hidden-secret'); api.opener = Opener()
        with self.assertRaises(r.LabError) as raised: api.login()
        message = str(raised.exception)
        self.assertIn('POST /oauth2/token/create: HTTP 400', message)
        self.assertIn('oauth=invalid_client', message)
        self.assertIn('resultCode=-100', message)
        self.assertNotIn('DO-NOT-PRINT', message)
        self.assertNotIn('hidden-secret', message)

    def test_untrusted_machine_error_is_not_printed(self):
        import io
        import urllib.error
        class Opener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 400, 'bad', {}, io.BytesIO(b'{"error":"secret-echo","header":{"resultCode":"secret-echo"}}'))
        api = r.Api('key', 'secret'); api.opener = Opener()
        with self.assertRaises(r.LabError) as raised: api.login()
        self.assertNotIn('secret-echo', str(raised.exception))



class EmptyRoleTests(unittest.TestCase):
    def test_explicit_empty_student_roles_can_be_planned_backed_up_and_applied(self):
        api = FakeApi()
        api.details[(r.DEFAULT_ANCHOR, 'student-1')]['roles'] = []
        plan = r.build_plan(api, CONFIG)
        self.assertEqual(plan['rows'][0]['before'], [])
        self.assertFalse(api.writes)
        with tempfile.TemporaryDirectory() as d:
            journal = r.apply_plan(api, plan, Path(d) / 'journal.json')
        self.assertEqual(journal['plan']['rows'][0]['before'], [])
        self.assertEqual(journal['results'][0]['status'], 'VERIFIED')

    def test_missing_or_null_roles_are_not_assumed_empty(self):
        for mode in ['missing', 'null', 'object']:
            api = FakeApi()
            detail = api.details[(r.DEFAULT_ANCHOR, 'student-1')]
            if mode == 'missing': del detail['roles']
            else: detail['roles'] = None if mode == 'null' else {}
            with self.assertRaisesRegex(r.LabError, 'TBIT_Edu01_Pro01 / educity01: roles must be an explicit list'):
                r.build_plan(api, CONFIG)
            self.assertFalse(api.writes)

    def test_operator_and_desired_roles_still_cannot_be_empty(self):
        with self.assertRaises(r.LabError): r.assignments([])
        api = FakeApi(); api.admin['roles'] = []
        with self.assertRaises(r.LabError): r.build_plan(api, CONFIG)
        self.assertFalse(api.writes)

if __name__ == '__main__':
    unittest.main()
