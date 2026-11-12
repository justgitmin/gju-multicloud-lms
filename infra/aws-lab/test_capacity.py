import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('capacity_lab',Path(__file__).with_name('lab.py'));lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
class CapacityTests(unittest.TestCase):
 def cfg(self):return lab.load_config(Path(__file__).with_name('config.gju-aws14.json'))
 def responses(self,quota=32,used=0,dbmax=40,available=True):return [{'Quota':{'Value':quota}},{'Reservations':[{'Instances':[{'InstanceType':'t3.micro'} for _ in range(used)]}]},{'InstanceTypes':[{'InstanceType':'t3.micro','VCpuInfo':{'DefaultVCpus':2}}]},{'AccountQuotas':[{'AccountQuotaName':'DBInstances','Used':0,'Max':dbmax}]},{'OrderableDBInstanceOptions':[{'DBInstanceClass':'db.t4g.micro','Engine':'mysql','Vpc':True}] if available else []}]
 def test_full_profile_needs_28_vcpus_and_never_writes(self):
  with patch.object(lab,'aws',side_effect=self.responses()) as calls:lab.capacity_preflight(self.cfg())
  self.assertEqual(calls.call_count,5);self.assertTrue(all('create' not in str(c.args) for c in calls.call_args_list))
 def test_low_ec2_quota_blocks_before_rds_or_any_creation(self):
  with patch.object(lab,'aws',side_effect=self.responses(quota=5)) as calls:
   with self.assertRaisesRegex(lab.CapacityError,'requested 28'):lab.capacity_preflight(self.cfg())
  self.assertEqual(calls.call_count,3)
 def test_existing_active_usage_and_rds_limit_are_counted(self):
  with patch.object(lab,'aws',side_effect=self.responses(quota=28,used=1)):
   with self.assertRaisesRegex(lab.CapacityError,'existing 2'):lab.capacity_preflight(self.cfg())
  with patch.object(lab,'aws',side_effect=self.responses(dbmax=10)):
   with self.assertRaisesRegex(lab.CapacityError,'RDS DB instances'):lab.capacity_preflight(self.cfg())
 def test_unavailable_private_mysql_class_blocks(self):
  with patch.object(lab,'aws',side_effect=self.responses(available=False)):
   with self.assertRaisesRegex(lab.CapacityError,'unavailable'):lab.capacity_preflight(self.cfg())
 def test_existing_stack_is_blocked_before_credential_generation(self):
  responses=[{'Quotas':[{'QuotaName':'VPCs per Region','Value':5},{'QuotaName':'Internet gateways per Region','Value':5}]},{'Vpcs':[]},{'InternetGateways':[]},{'Stacks':[{'StackName':'gju-mc-2026-aws-s01','StackStatus':'CREATE_COMPLETE'}]}]
  with patch.object(lab,'find_network',return_value=None),patch.object(lab,'aws',side_effect=responses) as calls:
   with self.assertRaisesRegex(lab.CapacityError,'s01'):lab.preflight(self.cfg())
  self.assertEqual(calls.call_count,4)
if __name__=='__main__':unittest.main()
