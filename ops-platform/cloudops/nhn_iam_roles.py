"""Validated role helpers shared in behavior with infra/nhn-lab/roles.py.
No credential, account, or infrastructure lifecycle operations.
"""
import json,re
from .providers import CloudError
LabError=CloudError
ROLE_NAMES=['Infrastructure VIEWER', 'Object Storage Object READER', 'Object Storage Object WRITER', 'RDS for MySQL VIEWER']

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

def assignments(roles, allow_empty=False):
    if not isinstance(roles, list) or (not roles and not allow_empty):
        raise LabError('Empty or missing role assignments')
    result = []
    for role in roles:
        if not isinstance(role, dict):
            raise LabError('Role assignment must be an object; no write allowed')
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

def student_assignments(detail, label):
    roles = detail.get('roles')
    if not isinstance(roles, list):
        fields = ', '.join(sorted(str(k) for k in detail if isinstance(k, str) and re.fullmatch(r'[A-Za-z0-9_]{1,60}', k)))
        raise LabError(label + ': roles must be an explicit list; returned field names: ' + fields + '. No write allowed.')
    return assignments(roles, allow_empty=True)

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

def normalize_member_roles(data, project):
    # Live IAM responses use relatedRoles; the published schema uses roles.
    # Both represent explicit role bundles. Never treat absent/null data as empty.
    result = dict(data)
    if 'relatedRoles' in data:
        related = data['relatedRoles']
        if not isinstance(related, list):
            raise LabError(project + ': relatedRoles must be an explicit list; no write allowed')
        normalized = assignments(related, allow_empty=True)
        if 'roles' in data:
            if assignments(data['roles'], allow_empty=True) != normalized:
                raise LabError(project + ': roles and relatedRoles disagree; no write allowed')
        else:
            result['roles'] = related
    return result

def member(api, project, uuid, iam=True):
    path = '/v1/' + ('iam/' if iam else '') + 'projects/' + ident(project) + '/members/' + ident(uuid)
    data = api.call('GET', path).get('projectMember')
    if not isinstance(data, dict) or data.get('uuid') != uuid:
        raise LabError('Member lookup identity mismatch')
    return normalize_member_roles(data, project)

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
