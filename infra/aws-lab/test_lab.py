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
        self.c['ssh_cidr'] = '203.0.113.10/32'
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
        self.c['ssh_cidr']='0.0.0.0/0'
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
        with patch.object(lab,'aws',side_effect=[{'Quotas':[{'QuotaName':'VPCs per Region','Value':5}]},{'Vpcs':[]}]):
            with self.assertRaises(ValueError):lab.preflight(self.c)

if __name__=='__main__':unittest.main()
