import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import lab
from repair_s3 import repair_template, validate_changes

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.c = lab.load_config(Path(__file__).with_name('config.example.json'))
        self.c['access_mode'] = 'ssm'
        self.t = lab.template(self.c, 's01')
        self.t['Resources']['Boundary']['Properties']['PolicyDocument']['Statement'] = [
            x for x in self.t['Resources']['Boundary']['Properties']['PolicyDocument']['Statement']
            if x.get('Sid') != 'S3ConsoleBucketNames']
        student = self.t['Resources']['Student']['Properties']
        student.pop('ManagedPolicyArns')
        student['Policies'] = [{'PolicyName': 'AssignedLabOnly', 'PolicyDocument': copy.deepcopy(
            self.t['Resources']['Boundary']['Properties']['PolicyDocument'])}]
        self.t['Resources']['NodeRole']['Properties']['Policies'] = [
            x for x in self.t['Resources']['NodeRole']['Properties']['Policies']
            if x['PolicyName'] != 'OwnPracticeObjects']

    def test_only_expected_iam_properties_change(self):
        original = copy.deepcopy(self.t)
        result = repair_template(self.t)
        self.assertEqual(self.t, original)
        for key in self.t:
            if key != 'Resources':
                self.assertEqual(result[key], self.t[key])
        for key in self.t['Resources']:
            if key not in ['Student', 'Boundary', 'NodeRole']:
                self.assertEqual(result['Resources'][key], self.t['Resources'][key])
        before = self.t['Resources']['Student']['Properties']
        after = result['Resources']['Student']['Properties']
        for key in before:
            if key not in ['Policies', 'ManagedPolicyArns']:
                self.assertEqual(before[key], after[key])
        self.assertEqual(after['ManagedPolicyArns'], [{'Ref': 'Boundary'}])
        self.assertNotIn('Policies', after)
        self.assertEqual(repair_template(result), result)

    def test_refuses_custom_policy_mismatch(self):
        self.t['Resources']['Student']['Properties']['Policies'][0]['PolicyDocument']['Statement'] = []
        with self.assertRaises(ValueError):
            repair_template(self.t)

    def test_preserves_other_policies_and_attachments(self):
        student = self.t['Resources']['Student']['Properties']
        extra = {'PolicyName': 'ExtraDeny', 'PolicyDocument': {'Version': '2012-10-17',
                 'Statement': [{'Effect': 'Deny', 'Action': '*', 'Resource': '*'}]}}
        student['Policies'].append(extra)
        student['ManagedPolicyArns'] = ['arn:aws:iam::123456789012:policy/CustomDeny']
        result = repair_template(self.t)['Resources']['Student']['Properties']
        self.assertEqual(result['Policies'], [extra])
        self.assertEqual(result['ManagedPolicyArns'], student['ManagedPolicyArns'] + [{'Ref': 'Boundary'}])

    def test_refuses_missing_grant_and_custom_boundary(self):
        for field in ['Policies', 'PermissionsBoundary']:
            t = copy.deepcopy(self.t)
            t['Resources']['Student']['Properties'].pop(field)
            with self.assertRaises(ValueError):
                repair_template(t)

    def test_new_template_is_already_repaired(self):
        t = lab.template(self.c, 's01')
        self.assertEqual(repair_template(t), t)

    def test_change_set_rejects_data_and_replacement(self):
        for name, action, replacement in [('Web', 'Modify', 'False'), ('Bucket', 'Remove', 'False'),
                                           ('Student', 'Modify', 'True'), ('Boundary', 'Add', 'False')]:
            with self.assertRaises(ValueError):
                validate_changes([{'ResourceChange': {'LogicalResourceId': name,
                    'Action': action, 'Replacement': replacement}}])
        validate_changes([{'ResourceChange': {'LogicalResourceId': name,
            'Action': 'Modify', 'Replacement': 'False'}} for name in ['Student', 'Boundary', 'NodeRole']])

if __name__ == '__main__':
    unittest.main()

