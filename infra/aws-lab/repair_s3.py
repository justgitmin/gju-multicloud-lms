#!/usr/bin/env python3
"""Plan/apply IAM-only S3 repair to existing, ownership-checked student stacks."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time


def repair_template(original):
    t = copy.deepcopy(original)
    r = t['Resources']
    for name, kind in [('Student', 'AWS::IAM::User'), ('Boundary', 'AWS::IAM::ManagedPolicy'),
                       ('NodeRole', 'AWS::IAM::Role'), ('Bucket', 'AWS::S3::Bucket')]:
        if r.get(name, {}).get('Type') != kind:
            raise ValueError('Unsupported stack resource: ' + name)
    boundary = r['Boundary']['Properties']['PolicyDocument']
    student = r['Student']['Properties']
    if student.get('PermissionsBoundary') != {'Ref': 'Boundary'}:
        raise ValueError('Custom permissions boundary; refusing overwrite')
    policies = student.get('Policies', [])
    inline = next((p for p in policies if p['PolicyName'] == 'AssignedLabOnly'), None)
    attached = student.get('ManagedPolicyArns', [])
    if inline is not None:
        if boundary != inline['PolicyDocument']:
            raise ValueError('Inline policy and boundary differ; review custom permissions manually')
    elif {'Ref': 'Boundary'} not in attached:
        raise ValueError('Expected assigned policy is missing; refusing permission changes')
    grant = {'Sid': 'S3ConsoleBucketNames', 'Effect': 'Allow',
             'Action': 's3:ListAllMyBuckets', 'Resource': '*'}
    if grant not in boundary['Statement']:
        boundary['Statement'].append(grant)
    # Reuse the existing customer-managed policy as both grant and boundary.
    # Removing the old large inline policy avoids the aggregate 2048-byte user quota.
    student['ManagedPolicyArns'] = copy.deepcopy(attached)
    if {'Ref': 'Boundary'} not in student['ManagedPolicyArns']:
        student['ManagedPolicyArns'].append({'Ref': 'Boundary'})
    remaining = [p for p in policies if p['PolicyName'] != 'AssignedLabOnly']
    if remaining:
        student['Policies'] = remaining
    else:
        student.pop('Policies', None)
    node_policy = {
        'PolicyName': 'OwnPracticeObjects',
        'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
            {'Effect': 'Allow', 'Action': 's3:GetBucketLocation', 'Resource': {'Fn::GetAtt': ['Bucket', 'Arn']}},
            {'Effect': 'Allow', 'Action': 's3:ListBucket', 'Resource': {'Fn::GetAtt': ['Bucket', 'Arn']},
             'Condition': {'StringLike': {'s3:prefix': ['practice/', 'practice/*']}}},
            {'Effect': 'Allow', 'Action': ['s3:PutObject', 's3:GetObject'],
             'Resource': {'Fn::Sub': '${Bucket.Arn}/practice/*'}}
        ]}}
    policies = r['NodeRole']['Properties']['Policies']
    existing = next((p for p in policies if p['PolicyName'] == node_policy['PolicyName']), None)
    if existing is not None and existing != node_policy:
        raise ValueError('Custom OwnPracticeObjects policy exists; refusing overwrite')
    if existing is None:
        policies.append(node_policy)
    return t


def validate_changes(changes):
    allowed = {'Student', 'Boundary', 'NodeRole'}
    if not changes:
        raise ValueError('Empty change set')
    for change in changes:
        resource = change.get('ResourceChange', {})
        if (resource.get('LogicalResourceId') not in allowed
                or resource.get('Action') != 'Modify'
                or resource.get('Replacement') != 'False'):
            raise ValueError('Change set affects non-IAM resources or may replace a resource')


def run(c, output, apply, account, lab):
    if lab.aws(c, 'sts', 'get-caller-identity')['Account'] != account:
        raise ValueError('AWS account mismatch')
    folder = Path(output).resolve()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    plans = []
    # Validate every stack and template before changing any cloud resource.
    for student in c['students']:
        stack = lab.owned_stack(c, student)
        if stack['StackStatus'] not in ['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']:
            raise ValueError('Stack not ready: ' + student)
        response = lab.aws(c, 'cloudformation', 'get-template', '--stack-name', stack['StackName'],
                           '--template-stage', 'Original')
        body = response['TemplateBody']
        original = json.loads(body) if isinstance(body, str) else body
        updated = repair_template(original)
        path = folder / (student + '-template.json')
        path.write_text(json.dumps(updated, indent=2))
        path.chmod(0o600)
        plans.append((stack, original, updated, path))
        print(student, 'already repaired' if original == updated else 'IAM-only repair planned')
    if not apply:
        print('Read-only plan complete. No cloud resources changed. Review files before --apply.')
        return
    for stack, original, updated, path in plans:
        if original == updated:
            continue
        name = 's3-permissions-' + str(time.time_ns())
        parameters = [{'ParameterKey': key, 'UsePreviousValue': True}
                      for key in original.get('Parameters', {})]
        created = lab.aws(c, 'cloudformation', 'create-change-set',
                          '--stack-name', stack['StackName'], '--change-set-name', name,
                          '--change-set-type', 'UPDATE', '--template-body', 'file://' + str(path),
                          '--parameters', json.dumps(parameters), '--capabilities', 'CAPABILITY_NAMED_IAM')
        change_id = created['Id']
        lab.aws(c, 'cloudformation', 'wait', 'change-set-create-complete', '--change-set-name', change_id)
        changes = []
        token = None
        while True:
            args = ['cloudformation', 'describe-change-set', '--change-set-name', change_id]
            if token:
                args += ['--next-token', token]
            page = lab.aws(c, *args)
            changes += page.get('Changes', [])
            token = page.get('NextToken')
            if not token:
                break
        validate_changes(changes)
        lab.aws(c, 'cloudformation', 'execute-change-set', '--change-set-name', change_id)
        lab.aws(c, 'cloudformation', 'wait', 'stack-update-complete', '--stack-name', stack['StackName'])
        print(stack['StackName'], 'IAM repair applied; verify student console and EC2 S3 access')


def main():
    import lab
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--confirm-account', required=True)
    p.add_argument('--output', default='.lab-s3-repair')
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    run(lab.load_config(a.config), a.output, a.apply, a.confirm_account, lab)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)

