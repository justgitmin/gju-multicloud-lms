#!/usr/bin/env python3
"""Operator-only, AWS CLI v2-based lab provisioning. plan is entirely offline."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import string
import subprocess
import sys


def load_config(path, deployment=False):
    c = json.loads(Path(path).read_text())
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,24}', c['lab_id']):
        raise ValueError('lab_id: 3–25 lowercase letters/digits/hyphens')
    if c['region'] != 'ap-northeast-2':
        raise ValueError('This tested template design targets ap-northeast-2 only')
    if not c['students'] or len(c['students']) > 30 or len(set(c['students'])) != len(c['students']):
        raise ValueError('students: 1–30 unique IDs')
    if any(not re.fullmatch(r's[0-9]{2}', s) for s in c['students']):
        raise ValueError('Student IDs must use s01 format')
    if c['instance_type'] not in ['t3.micro', 't3.small'] or c['db_class'] not in ['db.t4g.micro', 'db.t4g.small']:
        raise ValueError('Unsupported instance class')
    if type(c['volume_gb']) is not int or not 8 <= c['volume_gb'] <= 30:
        raise ValueError('volume_gb: 8–30')
    if any(type(c[k]) is not bool for k in ['s3', 'rds']):
        raise ValueError('s3/rds must be true or false')
    c.setdefault('access_mode', 'ssm')
    if c['access_mode'] not in ['ssm', 'ssh']:
        raise ValueError('access_mode must be ssm or ssh')
    if c['access_mode'] == 'ssh':
        if not isinstance(c.get('ssh_cidrs'), dict) or set(c['ssh_cidrs']) != set(c['students']):
            raise ValueError('ssh_cidrs must contain exactly one entry for each student')
        if deployment:
            for student in c['students']:
                validate_ip_cidr(c['ssh_cidrs'][student])
    return c


def legacy_template(c, student):
    name = c['lab_id'] + '-' + student
    tags = [{'Key': 'LabId', 'Value': c['lab_id']}, {'Key': 'StudentId', 'Value': student}, {'Key': 'Name', 'Value': name}]
    def ref(x): return {'Ref': x}
    def sub(x): return {'Fn::Sub': x}
    def resource(kind, **props): return {'Type': 'AWS::' + kind, 'Properties': props}
    r = {}
    r['Vpc'] = resource('EC2::VPC', CidrBlock='10.20.0.0/16', EnableDnsSupport=True, EnableDnsHostnames=True, Tags=tags)
    r['Gateway'] = resource('EC2::InternetGateway', Tags=tags)
    r['Attachment'] = resource('EC2::VPCGatewayAttachment', VpcId=ref('Vpc'), InternetGatewayId=ref('Gateway'))
    r['PublicSubnet'] = resource('EC2::Subnet', VpcId=ref('Vpc'), CidrBlock='10.20.1.0/24', AvailabilityZone={'Fn::Select': [0, {'Fn::GetAZs': ''}]}, MapPublicIpOnLaunch=True, Tags=tags)
    r['PrivateA'] = resource('EC2::Subnet', VpcId=ref('Vpc'), CidrBlock='10.20.10.0/24', AvailabilityZone={'Fn::Select': [0, {'Fn::GetAZs': ''}]}, Tags=tags)
    r['PrivateB'] = resource('EC2::Subnet', VpcId=ref('Vpc'), CidrBlock='10.20.11.0/24', AvailabilityZone={'Fn::Select': [1, {'Fn::GetAZs': ''}]}, Tags=tags)
    r['PublicRoutes'] = resource('EC2::RouteTable', VpcId=ref('Vpc'), Tags=tags)
    r['PublicRoute'] = resource('EC2::Route', RouteTableId=ref('PublicRoutes'), DestinationCidrBlock='0.0.0.0/0', GatewayId=ref('Gateway'))
    r['PublicRoute']['DependsOn'] = 'Attachment'
    r['RouteAssociation'] = resource('EC2::SubnetRouteTableAssociation', SubnetId=ref('PublicSubnet'), RouteTableId=ref('PublicRoutes'))
    r['WebSecurity'] = resource('EC2::SecurityGroup', GroupDescription='Training SSH source and public HTTP only', VpcId=ref('Vpc'), Tags=tags,
        SecurityGroupIngress=[{'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'CidrIp': ref('SshCidr')}, {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'CidrIp': '0.0.0.0/0'}])
    r['Key'] = resource('EC2::KeyPair', KeyName=name, PublicKeyMaterial=ref('PublicKey'), Tags=tags)
    r['Web'] = resource('EC2::Instance', ImageId=ref('UbuntuAmi'), InstanceType=c['instance_type'], SubnetId=ref('PublicSubnet'), SecurityGroupIds=[ref('WebSecurity')], KeyName=ref('Key'), Tags=tags,
        MetadataOptions={'HttpTokens': 'required', 'HttpEndpoint': 'enabled'}, CreditSpecification={'CPUCredits': 'standard'},
        BlockDeviceMappings=[{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': c['volume_gb'], 'VolumeType': 'gp3', 'Encrypted': True, 'DeleteOnTermination': True}}])
    r['Web']['DependsOn'] = ['PublicRoute', 'RouteAssociation']
    statements = [
        {'Effect': 'Allow', 'Action': ['ec2:DescribeInstances', 'ec2:DescribeInstanceStatus', 'ec2:DescribeVpcs', 'ec2:DescribeSubnets', 'ec2:DescribeRouteTables', 'ec2:DescribeInternetGateways', 'ec2:DescribeSecurityGroups', 'ec2:DescribeNetworkAcls', 'ec2:DescribeVolumes', 'ec2:DescribeTags', 'ec2:DescribeKeyPairs'], 'Resource': '*', 'Condition': {'StringEquals': {'aws:RequestedRegion': c['region']}}},
        {'Effect': 'Allow', 'Action': ['ec2:StartInstances', 'ec2:StopInstances', 'ec2:RebootInstances'], 'Resource': sub('arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${Web}')},
        {'Effect': 'Allow', 'Action': ['iam:ChangePassword', 'iam:GetUser'], 'Resource': sub('arn:${AWS::Partition}:iam::${AWS::AccountId}:user/' + name)},
        {'Effect': 'Allow', 'Action': 'iam:GetAccountPasswordPolicy', 'Resource': '*'}]
    out = {'Username': {'Value': name}, 'LoginUrl': {'Value': sub('https://${AWS::AccountId}.signin.aws.amazon.com/console/')}, 'InstanceId': {'Value': ref('Web')}, 'PublicIp': {'Value': {'Fn::GetAtt': ['Web', 'PublicIp']}}, 'VpcId': {'Value': ref('Vpc')}}
    if c['s3']:
        r['Bucket'] = resource('S3::Bucket', Tags=tags, BucketEncryption={'ServerSideEncryptionConfiguration': [{'ServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]}, PublicAccessBlockConfiguration={'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True}, OwnershipControls={'Rules': [{'ObjectOwnership': 'BucketOwnerEnforced'}]})
        statements += [{'Effect': 'Allow', 'Action': ['s3:GetBucketLocation', 's3:ListBucket'], 'Resource': {'Fn::GetAtt': ['Bucket', 'Arn']}}, {'Effect': 'Allow', 'Action': ['s3:PutObject', 's3:GetObject', 's3:DeleteObject'], 'Resource': sub('${Bucket.Arn}/practice/*')}]
        out['BucketName'] = {'Value': ref('Bucket')}
        out['S3ConsoleUrl'] = {'Value': sub('https://s3.console.aws.amazon.com/s3/buckets/${Bucket}?region=${AWS::Region}&prefix=practice/&showversions=false')}
    if c['rds']:
        r['DbSecurity'] = resource('EC2::SecurityGroup', GroupDescription='MySQL only from assigned web security group', VpcId=ref('Vpc'), Tags=tags, SecurityGroupIngress=[{'IpProtocol': 'tcp', 'FromPort': 3306, 'ToPort': 3306, 'SourceSecurityGroupId': ref('WebSecurity')}])
        r['DbSubnets'] = resource('RDS::DBSubnetGroup', DBSubnetGroupDescription=name, SubnetIds=[ref('PrivateA'), ref('PrivateB')], Tags=tags)
        r['Database'] = resource('RDS::DBInstance', Engine='mysql', DBInstanceClass=c['db_class'], AllocatedStorage='20', StorageType='gp3', StorageEncrypted=True, PubliclyAccessible=False, MultiAZ=False, MasterUsername='labadmin', MasterUserPassword=ref('DbPassword'), DBName='labdb', BackupRetentionPeriod=0, DeleteAutomatedBackups=True, DeletionProtection=False, DBSubnetGroupName=ref('DbSubnets'), VPCSecurityGroups=[ref('DbSecurity')], Tags=tags)
        r['Database']['DeletionPolicy'] = 'Delete'
        r['Database']['UpdateReplacePolicy'] = 'Delete'
        out['DbEndpoint'] = {'Value': {'Fn::GetAtt': ['Database', 'Endpoint.Address']}}
    # Identical permissions boundary caps additional identity-policy grants. No student IAM administration,
    # PassRole, resource creation, security changes, snapshots, sharing, or CloudFormation permissions.
    doc = {'Version': '2012-10-17', 'Statement': statements}
    r['Boundary'] = resource('IAM::ManagedPolicy', Description=name + ' lab maximum identity permissions', PolicyDocument=doc)
    r['Student'] = resource('IAM::User', UserName=name, Tags=tags, PermissionsBoundary=ref('Boundary'), LoginProfile={'Password': ref('LoginPassword'), 'PasswordResetRequired': True}, Policies=[{'PolicyName': 'AssignedLabOnly', 'PolicyDocument': doc}])
    result = {'AWSTemplateFormatVersion': '2010-09-09', 'Description': 'GJU assigned-resource video lab: ' + name, 'Parameters': {'SshCidr': {'Type': 'String'}, 'PublicKey': {'Type': 'String'}, 'LoginPassword': {'Type': 'String', 'NoEcho': True, 'MinLength': 16}, 'DbPassword': {'Type': 'String', 'NoEcho': True, 'MinLength': 16}, 'UbuntuAmi': {'Type': 'AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>', 'Default': c['ami_parameter']}}, 'Resources': r, 'Outputs': out}
    if not c['rds']:
        del result['Parameters']['DbPassword']
    return result


NETWORK_RESOURCES = ['Vpc', 'Gateway', 'Attachment', 'PublicSubnet', 'PrivateA', 'PrivateB', 'PublicRoutes', 'PublicRoute', 'RouteAssociation']
SHARED_REFS = {'Vpc': 'SharedVpc', 'PublicSubnet': 'SharedPublicSubnet', 'PrivateA': 'SharedPrivateA', 'PrivateB': 'SharedPrivateB'}


def validate_ip_cidr(value):
    net = ipaddress.ip_network(value, strict=True)
    if net.version != 4 or net.prefixlen != 32 or not net.network_address.is_global:
        raise ValueError('Each SSH source must be a public IPv4 /32, not a whole network')
    return str(net)


def network_template(c):
    old = legacy_template(c, 'shared')
    resources = {key: old['Resources'][key] for key in NETWORK_RESOURCES}
    # A dedicated main route table with no internet route protects both shared private DB subnets.
    result = {'AWSTemplateFormatVersion': '2010-09-09', 'Description': 'GJU shared lab network', 'Resources': resources,
              'Outputs': {param: {'Value': {'Ref': logical}} for logical, param in SHARED_REFS.items()}}
    if c.get('access_mode', 'ssm') == 'ssm':
        resources['SessionDocument'] = {'Type':'AWS::SSM::Document','Properties':{
            'Name':c['lab_id']+'-shell','DocumentType':'Session','DocumentFormat':'JSON',
            'Content':{'schemaVersion':'1.0','description':'Training browser shell','sessionType':'Standard_Stream',
                'inputs':{'s3EncryptionEnabled':True,'cloudWatchEncryptionEnabled':True,'cloudWatchStreamingEnabled':False,
                          'runAsEnabled':True,'runAsDefaultUser':'ubuntu','idleSessionTimeout':'20','maxSessionDuration':'180',
                          'shellProfile':{'linux':'cd /home/ubuntu; exec /bin/bash -l','windows':''}}}}}
        result['Outputs']['SharedSessionDocument']={'Value':{'Ref':'SessionDocument'}}
    return result



def template(c, student):
    t = legacy_template(c, student)
    for key in NETWORK_RESOURCES:
        del t['Resources'][key]
    del t['Resources']['Web']['DependsOn']
    def rewrite(value):
        if isinstance(value, dict):
            if set(value) == {'Ref'} and value['Ref'] in SHARED_REFS:
                return {'Ref': SHARED_REFS[value['Ref']]}
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return value
    t = rewrite(t)
    for key in SHARED_REFS.values():
        if not c['rds'] and key in ['SharedPrivateA', 'SharedPrivateB']:
            continue
        t['Parameters'][key] = {'Type': 'String'}
    t['Outputs']['WebSecurityGroupId'] = {'Value': {'Ref': 'WebSecurity'}}
    if c.get('access_mode', 'ssm') == 'ssm':
        enable_ssm(t, c)
    return t


def enable_ssm(t, c):
    r=t['Resources']; web=r['Web']['Properties']
    del r['Key']; web.pop('KeyName',None)
    for key in ['SshCidr','PublicKey']:t['Parameters'].pop(key,None)
    r['WebSecurity']['Properties']['GroupDescription']='Public training HTTP; no inbound SSH'
    r['WebSecurity']['Properties']['SecurityGroupIngress']=[rule for rule in r['WebSecurity']['Properties']['SecurityGroupIngress'] if rule['FromPort']!=22]
    t['Parameters']['SharedSessionDocument']={'Type':'String'}
    # Deliberately no GetParameter/GetParameters or S3 rights on the instance role.
    # Students with sudo can obtain this role's temporary credentials, so keep it channel-only.
    r['NodeRole']={'Type':'AWS::IAM::Role','Properties':{
        'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'ec2.amazonaws.com'},'Action':'sts:AssumeRole'}]},
        'Policies':[{'PolicyName':'SessionAgentOnly','PolicyDocument':{'Version':'2012-10-17','Statement':[{
            'Effect':'Allow','Action':['ssm:UpdateInstanceInformation','ssmmessages:CreateControlChannel','ssmmessages:CreateDataChannel','ssmmessages:OpenControlChannel','ssmmessages:OpenDataChannel'],'Resource':'*'}]}}]}}
    r['NodeProfile']={'Type':'AWS::IAM::InstanceProfile','Properties':{'Roles':[{'Ref':'NodeRole'}]}}
    web['IamInstanceProfile']={'Ref':'NodeProfile'}
    web['UserData']={'Fn::Base64':'#!/bin/bash\nset -eu\nif snap list amazon-ssm-agent >/dev/null 2>&1; then\n  snap start --enable amazon-ssm-agent\nelse\n  systemctl enable --now amazon-ssm-agent\nfi\n'}
    own_instance={'Fn::Sub':'arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${Web}'}
    shell={'Fn::Sub':'arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:document/${SharedSessionDocument}'}
    own_sessions={'Fn::Sub':'arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:session/${!aws:username}-*'}
    doc=r['Boundary']['Properties']['PolicyDocument']
    doc['Statement'] += [
        {'Effect':'Allow','Action':'ssm:StartSession','Resource':own_instance,'Condition':{'BoolIfExists':{'ssm:SessionDocumentAccessCheck':'true'}}},
        {'Effect':'Allow','Action':['ssm:StartSession','ssm:GetDocument','ssm:DescribeDocument'],'Resource':shell},
        {'Effect':'Allow','Action':['ssm:ResumeSession','ssm:TerminateSession','ssmmessages:OpenDataChannel'],'Resource':[own_sessions,{'Fn::Sub':'arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:session/${!aws:userid}-*'}]},
        {'Effect':'Allow','Action':['ssm:DescribeSessions','ssm:GetConnectionStatus','ssm:DescribeInstanceInformation','ssm:DescribeInstanceProperties','ssm:ListDocuments'],'Resource':'*','Condition':{'StringEquals':{'aws:RequestedRegion':c['region']}}}]
    # Both reference the same object in memory; explicitly set for clarity after JSON serialization.
    r['Student']['Properties']['Policies'][0]['PolicyDocument']=doc
    t['Outputs']['SessionDocument']={'Value':{'Ref':'SharedSessionDocument'}}
    t['Outputs']['SessionConsoleUrl']={'Value':{'Fn::Sub':'https://${AWS::Region}.console.aws.amazon.com/systems-manager/session-manager/start-session?region=${AWS::Region}&target=${Web}&documentName=${SharedSessionDocument}'}}
    t['Description']+=' (Session Manager, no SSH key)'


def find_network(c):
    # Enumerating existing stacks avoids treating authorization or network errors as missing stacks.
    stacks = aws(c, 'cloudformation', 'describe-stacks').get('Stacks', [])
    match = next((x for x in stacks if x['StackName'] == c['lab_id'] + '-shared'), None)
    if match is None:
        return None
    tags = {x['Key']: x['Value'] for x in match.get('Tags', [])}
    if tags.get('LabId') != c['lab_id'] or tags.get('StudentId') != 'shared' or tags.get('ManagedBy') != 'gju-lab-tool':
        raise ValueError('Shared stack ownership mismatch')
    if match['StackStatus'] not in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
        raise ValueError('Shared stack is not ready: ' + match['StackStatus'])
    return match


def ensure_network(c, state):
    existing = find_network(c)
    if existing is not None and c.get('access_mode','ssm') == 'ssm' and not any(o['OutputKey']=='SharedSessionDocument' for o in existing.get('Outputs',[])):
        raise ValueError('Existing network is an older SSH lab. Use a new lab_id; in-place conversion is not supported.')
    if existing is None:
        path = state / (c['lab_id'] + '-shared-template.json')
        path.write_text(json.dumps(network_template(c)))
        name = c['lab_id'] + '-shared'
        aws(c, 'cloudformation', 'validate-template', '--template-body', 'file://' + str(path))
        aws(c, 'cloudformation', 'create-stack', '--stack-name', name, '--template-body', 'file://' + str(path), '--tags', 'Key=LabId,Value=' + c['lab_id'], 'Key=StudentId,Value=shared', 'Key=ManagedBy,Value=gju-lab-tool')
        print(name, 'shared network creation requested', flush=True)
        aws(c, 'cloudformation', 'wait', 'stack-create-complete', '--stack-name', name)
        existing = find_network(c)
    return {x['OutputKey']: x['OutputValue'] for x in existing['Outputs']}


def set_ssh(c, student, ip):
    if student not in c['students']:
        raise ValueError('Unknown student')
    cidr = validate_ip_cidr(ip if '/' in ip else ip + '/32')
    stack = owned_stack(c, student)
    outputs = {x['OutputKey']: x['OutputValue'] for x in stack.get('Outputs', [])}
    group = outputs.get('WebSecurityGroupId')
    if not group:
        raise ValueError('Not a shared-network v2 student stack')
    data = aws(c, 'ec2', 'describe-security-group-rules', '--filters', 'Name=group-id,Values=' + group)
    rules = [r for r in data['SecurityGroupRules'] if not r['IsEgress'] and r['IpProtocol'] == 'tcp' and r.get('FromPort') == 22 and r.get('ToPort') == 22]
    if len(rules) != 1 or 'CidrIpv4' not in rules[0]:
        raise ValueError('Unexpected SSH rules; refusing to change group')
    change = [{'SecurityGroupRuleId': rules[0]['SecurityGroupRuleId'], 'SecurityGroupRule': {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'CidrIpv4': cidr, 'Description': 'Assigned student home IPv4'}}]
    aws(c, 'ec2', 'modify-security-group-rules', '--group-id', group, '--security-group-rules', json.dumps(change))
    print(student, 'SSH source updated to', cidr, '(also update ssh_cidrs in your local config)')


def aws(c, *args):
    result = subprocess.run(['aws', '--region', c['region'], '--output', 'json', '--no-cli-pager', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def save_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2)


def owned_stack(c, student):
    name = c['lab_id'] + '-' + student
    data = aws(c, 'cloudformation', 'describe-stacks', '--stack-name', name)['Stacks'][0]
    tags = {x['Key']: x['Value'] for x in data.get('Tags', [])}
    if tags.get('LabId') != c['lab_id'] or tags.get('StudentId') != student or tags.get('ManagedBy') != 'gju-lab-tool':
        raise ValueError('Ownership mismatch; refusing operation: ' + name)
    return data


def preflight(c):
    # Read-only quota checks before creating any student environment.
    quotas = aws(c, 'service-quotas', 'list-service-quotas', '--service-code', 'vpc')['Quotas']
    count = 0 if find_network(c) else 1
    checks = [('VPCs per Region', 'describe-vpcs', 'Vpcs'), ('Internet gateways per Region', 'describe-internet-gateways', 'InternetGateways')]
    for label, action, key in checks:
        quota = next((q['Value'] for q in quotas if q['QuotaName'].lower() == label.lower()), None)
        if quota is None:
            raise ValueError('Cannot determine quota: ' + label + '; check Service Quotas')
        existing = len(aws(c, 'ec2', action)[key])
        if existing + count > quota:
            raise ValueError(f'{label}: existing {existing} + requested {count} exceeds quota {quota}. Request increase first.')
    print('VPC/Internet gateway quotas checked. Also check EC2 vCPU, RDS and available budget before apply.')


def deploy(c, state):
    preflight(c)
    network = ensure_network(c, state)
    identity = aws(c, 'sts', 'get-caller-identity')
    print('Target AWS account:', identity['Account'], 'region:', c['region'])
    for student in c['students']:
        name = c['lab_id'] + '-' + student
        folder = state / name
        # Existing state is never silently overwritten. status then use a new config containing remaining IDs.
        folder.mkdir(mode=0o700)
        if c.get('access_mode','ssm') == 'ssh':
            subprocess.run(['ssh-keygen', '-q', '-t', 'rsa', '-b', '3072', '-N', '', '-f', str(folder / 'ssh-key')], check=True)
        password = 'Gju9!' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(23))
        dbpass = 'Gju9' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        save_private(folder / 'credentials.json', {'account_id': identity['Account'], 'username': name, 'initial_password': password, 'db_user': 'labadmin', 'db_password': dbpass if c['rds'] else None})
        template_path = folder / 'template.json'
        student_template = template(c, student)
        template_path.write_text(json.dumps(student_template))
        values={'LoginPassword':password,'DbPassword':dbpass}
        if c.get('access_mode','ssm') == 'ssh':
            values.update(SshCidr=c['ssh_cidrs'][student],PublicKey=(folder/'ssh-key.pub').read_text().strip())
        params=[{'ParameterKey':k,'ParameterValue':v} for k,v in values.items() if k in student_template['Parameters']]
        params += [{'ParameterKey': k, 'ParameterValue': v} for k, v in network.items() if k in student_template['Parameters']]
        if not c['rds']:
            params = [p for p in params if p['ParameterKey'] != 'DbPassword']
        save_private(folder / 'parameters.json', params)
        try:
            aws(c, 'cloudformation', 'validate-template', '--template-body', 'file://' + str(template_path))
            aws(c, 'cloudformation', 'create-stack', '--stack-name', name, '--template-body', 'file://' + str(template_path), '--parameters', 'file://' + str(folder / 'parameters.json'), '--capabilities', 'CAPABILITY_NAMED_IAM', '--tags', 'Key=LabId,Value=' + c['lab_id'], 'Key=StudentId,Value=' + student, 'Key=ManagedBy,Value=gju-lab-tool')
            print(name, 'creation requested; waiting for completion', flush=True)
            aws(c, 'cloudformation', 'wait', 'stack-create-complete', '--stack-name', name)
            outputs = owned_stack(c, student).get('Outputs', [])
            save_private(folder / 'outputs.json', {o['OutputKey']: o['OutputValue'] for o in outputs})
            print(name, 'ready; distribute ONLY this student directory securely', flush=True)
        finally:
            (folder / 'parameters.json').unlink(missing_ok=True)


def destroy(c):
    # Each stack is independently ownership-checked before mutations. No account-wide tag sweeping.
    for student in c['students']:
        name = c['lab_id'] + '-' + student
        stack = owned_stack(c, student)
        resources = aws(c, 'cloudformation', 'list-stack-resources', '--stack-name', name)['StackResourceSummaries']
        found = {x['LogicalResourceId']: x for x in resources}
        user = found.get('Student', {}).get('PhysicalResourceId')
        if user and found['Student']['ResourceStatus'] != 'DELETE_COMPLETE':
            deny = json.dumps({'Version': '2012-10-17', 'Statement': [{'Effect': 'Deny', 'Action': '*', 'Resource': '*'}]})
            # Replace existing stack-owned inline policy, so CloudFormation removes it with the user.
            aws(c, 'iam', 'put-user-policy', '--user-name', user, '--policy-name', 'AssignedLabOnly', '--policy-document', deny)
        bucket = found.get('Bucket', {}).get('PhysicalResourceId')
        if bucket and found['Bucket']['ResourceStatus'] != 'DELETE_COMPLETE':
            # Nonversioned lab bucket only. Refuse rather than leak retained versions/delete markers.
            versioning = aws(c, 's3api', 'get-bucket-versioning', '--bucket', bucket)
            if versioning.get('Status'):
                raise ValueError('Versioned bucket requires explicit operator cleanup: ' + bucket)
            aws(c, 's3', 'rm', 's3://' + bucket + '/', '--recursive', '--only-show-errors')
        aws(c, 'cloudformation', 'delete-stack', '--stack-name', name)
        print(name, 'deletion requested; waiting', flush=True)
        aws(c, 'cloudformation', 'wait', 'stack-delete-complete', '--stack-name', name)
        print(name, 'stack deleted (local credentials retained for operator disposal)')

    cleanup_network(c)


def cleanup_network(c):
    network = find_network(c)
    if network:
        stacks = aws(c, 'cloudformation', 'describe-stacks').get('Stacks', [])
        remaining = [x['StackName'] for x in stacks if x['StackName'] != c['lab_id'] + '-shared' and
                     {t['Key']: t['Value'] for t in x.get('Tags', [])}.get('LabId') == c['lab_id']]
        if remaining:
            print('Shared network retained; remaining lab stacks:', ', '.join(remaining))
        else:
            aws(c, 'cloudformation', 'delete-stack', '--stack-name', c['lab_id'] + '-shared')
            aws(c, 'cloudformation', 'wait', 'stack-delete-complete', '--stack-name', c['lab_id'] + '-shared')
            print('Shared network deleted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'apply', 'status', 'destroy', 'set-ssh'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--student')
    parser.add_argument('--ip', help='New home public IPv4, optionally with /32')
    parser.add_argument('--state', default='.lab-state')
    parser.add_argument('--confirm-account', help='Required for apply/destroy/set-ssh; must match STS account ID')
    args = parser.parse_args()
    c = load_config(args.config, args.action == 'apply')
    if args.action == 'plan':
        print(json.dumps({'lab': c['lab_id'], 'region': c['region'], 'students': len(c['students']), 'stacks': [c['lab_id'] + '-' + s for s in c['students']], 'resources_per_student': {'iam_user': 1, 'vpc': 0, 'ec2': 1, 's3': int(c['s3']), 'rds': int(c['rds'])}, 'shared_network': {'vpc': 1, 'public_subnets': 1, 'private_subnets': 2}, 'access_mode': c['access_mode'], 'ssh_sources': c.get('ssh_cidrs',{}) if c['access_mode']=='ssh' else 'not required', 'note': 'No AWS calls. Costs and service quotas must be checked before apply.'}, indent=2))
        return
    if args.action in ['apply', 'destroy', 'set-ssh']:
        actual = aws(c, 'sts', 'get-caller-identity')['Account']
        if args.confirm_account != actual:
            raise ValueError('Pass --confirm-account with the intended AWS account ID; no changes made')
    if args.action == 'apply':
        state = Path(args.state).resolve()
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(state, 0o700)
        deploy(c, state)
    elif args.action == 'set-ssh':
        if not args.student or not args.ip:
            raise ValueError('set-ssh requires --student and --ip')
        set_ssh(c, args.student, args.ip)
    elif args.action == 'destroy':
        destroy(c)
    else:
        for student in c['students']:
            stack = owned_stack(c, student)
            print(json.dumps({'student': student, 'status': stack['StackStatus'], 'outputs': stack.get('Outputs', [])}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
