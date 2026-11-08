import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('lab', Path(__file__).with_name('lab.py'))
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)

class LabTests(unittest.TestCase):
    def setUp(self):
        self.c = lab.load_config(Path(__file__).with_name('config.example.json'))
        self.c['lab_id'] = 'gju-2026'
        self.c['access_mode'] = 'ssh'
        self.c['ssh_cidrs'] = {student:'8.8.8.8/32' for student in self.c['students']}
        self.t = lab.template(self.c, 's01')
    def test_no_shared_resource_writes(self):
        statements = self.t['Resources']['Boundary']['Properties']['PolicyDocument']['Statement']
        writes = [x for x in statements if any(a in json.dumps(x['Action']) for a in ['StartInstances','StopInstances','RebootInstances','PutObject','DeleteObject','ChangePassword'])]
        self.assertTrue(writes)
        for statement in writes:
            self.assertNotEqual(statement['Resource'], '*')
        actions = [a for x in statements for a in (x['Action'] if isinstance(x['Action'], list) else [x['Action']])]
        for action in ['iam:PassRole','ec2:RunInstances','ec2:CreateTags','rds:CreateDBInstance','s3:PutBucketPolicy','cloudformation:CreateStack']:
            self.assertNotIn(action, actions)
    def test_boundary_and_inline_match(self):
        r = self.t['Resources']
        self.assertEqual(r['Student']['Properties']['PermissionsBoundary'], {'Ref':'Boundary'})
        self.assertEqual(r['Student']['Properties']['Policies'][0]['PolicyDocument'], r['Boundary']['Properties']['PolicyDocument'])
    def test_ssh_source_and_database_isolation(self):
        r = self.t['Resources']
        self.assertEqual(r['WebSecurity']['Properties']['SecurityGroupIngress'][0]['CidrIp'], {'Ref':'SshCidr'})
        self.assertFalse(r['Database']['Properties']['PubliclyAccessible'])
        rule = r['DbSecurity']['Properties']['SecurityGroupIngress'][0]
        self.assertNotIn('CidrIp', rule)
        self.assertEqual(rule['SourceSecurityGroupId'], {'Ref':'WebSecurity'})
    def test_bucket_private_and_prefix_limited(self):
        r = self.t['Resources']
        self.assertTrue(all(r['Bucket']['Properties']['PublicAccessBlockConfiguration'].values()))
        statements = r['Boundary']['Properties']['PolicyDocument']['Statement']
        self.assertTrue(any(x['Resource']=={'Fn::Sub':'${Bucket.Arn}/practice/*'} for x in statements))
    def test_secrets_not_outputs_or_template(self):
        self.assertTrue(self.t['Parameters']['LoginPassword']['NoEcho'])
        self.assertTrue(self.t['Parameters']['DbPassword']['NoEcho'])
        self.assertNotIn('Password', json.dumps(self.t['Outputs']))
    def test_optional_services(self):
        self.c.update(rds=False,s3=False)
        t=lab.template(self.c,'s01')
        self.assertNotIn('Database',t['Resources'])
        self.assertNotIn('Bucket',t['Resources'])
    def test_wide_ssh_source_rejected(self):
        self.c['ssh_cidrs']['s01']='0.0.0.0/0'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'c.json';p.write_text(json.dumps(self.c))
            with self.assertRaises(ValueError):lab.load_config(p,True)
    def test_credentials_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'secret.json';lab.save_private(p,{'secret':'one'})
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):lab.save_private(p,{'secret':'two'})
    def test_foreign_stack_not_deleted(self):
        with patch.object(lab,'aws',return_value={'Stacks':[{'Tags':[]}]} ) as mocked:
            with self.assertRaises(ValueError):lab.destroy(self.c)
            self.assertEqual(mocked.call_count,1)
    def test_low_quota_fails_before_mutation(self):
        with patch.object(lab,'aws',side_effect=[{'Quotas':[{'QuotaName':'VPCs per Region','Value':5}]},{'Stacks':[]},{'Vpcs':[{}]*5}]):
            with self.assertRaises(ValueError):lab.preflight(self.c)

    def test_network_is_created_only_once(self):
        network=lab.network_template(self.c)
        self.assertEqual(sum(r['Type']=='AWS::EC2::VPC' for r in network['Resources'].values()),1)
        for student in self.c['students']:
            template=lab.template(self.c,student)
            self.assertFalse(any(r['Type'] in ['AWS::EC2::VPC','AWS::EC2::Subnet','AWS::EC2::Route'] for r in template['Resources'].values()))
            self.assertEqual(template['Resources']['Web']['Properties']['SubnetId'],{'Ref':'SharedPublicSubnet'})
    def test_private_ips_and_broad_networks_rejected(self):
        for value in ['192.168.1.2/32','8.8.8.0/24','::/0']:
            with self.assertRaises(ValueError):lab.validate_ip_cidr(value)
    def test_ssh_updates_only_selected_group_rule(self):
        stack={'Outputs':[{'OutputKey':'WebSecurityGroupId','OutputValue':'sg-student01'}]}
        response={'SecurityGroupRules':[{'IsEgress':False,'IpProtocol':'tcp','FromPort':22,'ToPort':22,'CidrIpv4':'8.8.8.8/32','SecurityGroupRuleId':'sgr-student01'}]}
        with patch.object(lab,'owned_stack',return_value=stack),patch.object(lab,'aws',side_effect=[response,{}]) as mock:
            lab.set_ssh(self.c,'s01','1.1.1.1')
            args=mock.call_args.args
            self.assertEqual(args[1:3],('ec2','modify-security-group-rules'))
            self.assertIn('sg-student01',args)
            self.assertEqual(json.loads(args[-1])[0]['SecurityGroupRule']['CidrIpv4'],'1.1.1.1/32')
    def test_ssh_refuses_unknown_student(self):
        with patch.object(lab,'aws') as mock:
            with self.assertRaises(ValueError):lab.set_ssh(self.c,'s99','1.1.1.1')
            mock.assert_not_called()
    def test_ssh_refuses_unexpected_extra_rules(self):
        with patch.object(lab,'owned_stack',return_value={'Outputs':[{'OutputKey':'WebSecurityGroupId','OutputValue':'sg-student01'}]}),patch.object(lab,'aws',return_value={'SecurityGroupRules':[]}) as mock:
            with self.assertRaises(ValueError):lab.set_ssh(self.c,'s01','1.1.1.1')
            self.assertEqual(mock.call_count,1)

    def test_shared_network_retained_for_other_student(self):
        stacks={'Stacks':[{'StackName':'gju-2026-s02','Tags':[{'Key':'LabId','Value':'gju-2026'}]}]}
        with patch.object(lab,'find_network',return_value={'StackName':'gju-2026-shared'}),patch.object(lab,'aws',return_value=stacks) as mock:
            lab.cleanup_network(self.c)
            self.assertEqual(mock.call_count,1)
    def test_shared_network_deleted_after_last_student(self):
        with patch.object(lab,'find_network',return_value={'StackName':'gju-2026-shared'}),patch.object(lab,'aws',side_effect=[{'Stacks':[]},{},{}]) as mock:
            lab.cleanup_network(self.c)
            self.assertEqual(mock.call_count,3)
            self.assertIn('delete-stack',mock.call_args_list[1].args)
            self.assertIn('gju-2026-shared',mock.call_args_list[1].args)

    def test_ssm_has_no_ssh_key_or_inbound_port(self):
        self.c['access_mode']='ssm';self.c.pop('ssh_cidrs',None)
        t=lab.template(self.c,'s01');r=t['Resources']
        self.assertNotIn('Key',r);self.assertNotIn('KeyName',r['Web']['Properties'])
        self.assertNotIn('PublicKey',t['Parameters']);self.assertNotIn('SshCidr',t['Parameters'])
        self.assertTrue(all(x['FromPort']!=22 for x in r['WebSecurity']['Properties']['SecurityGroupIngress']))
        self.assertIn('NodeRole',r);self.assertIn('NodeProfile',r)
    def test_ssm_session_target_and_session_ownership_scoped(self):
        self.c['access_mode']='ssm';t=lab.template(self.c,'s01')
        statements=t['Resources']['Boundary']['Properties']['PolicyDocument']['Statement']
        start=[x for x in statements if x['Action']=='ssm:StartSession'][0]
        self.assertIn('instance/${Web}',start['Resource']['Fn::Sub'])
        self.assertEqual(start['Condition'],{'BoolIfExists':{'ssm:SessionDocumentAccessCheck':'true'}})
        channels=[x for x in statements if isinstance(x['Action'],list) and 'ssm:TerminateSession' in x['Action']][0]
        self.assertIn('${!aws:username}-*',channels['Resource'][0]['Fn::Sub'])
    def test_ssm_role_cannot_read_account_parameters(self):
        self.c['access_mode']='ssm';role=lab.template(self.c,'s01')['Resources']['NodeRole']
        actions=role['Properties']['Policies'][0]['PolicyDocument']['Statement'][0]['Action']
        self.assertNotIn('ssm:GetParameter',actions);self.assertNotIn('ssm:GetParameters',actions)
        self.assertNotIn('s3:GetObject',actions)
    def test_ssm_document_does_not_override_default(self):
        self.c['access_mode']='ssm';doc=lab.network_template(self.c)['Resources']['SessionDocument']
        self.assertEqual(doc['Properties']['Name'],'gju-2026-shell')
        self.assertNotEqual(doc['Properties']['Name'],'SSM-SessionManagerRunShell')

if __name__=='__main__':unittest.main()
