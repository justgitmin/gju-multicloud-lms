import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('https_config',Path(__file__).resolve().parents[2]/'scripts/configure-https.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class HttpsTests(unittest.TestCase):
    def test_domain_only(self):
        self.assertEqual(mod.domain_name('LMS.GJU-BOOT.TBITCLOUD.COM'),'lms.gju-boot.tbitcloud.com')
        for domain in ['https://example.com','example.com/path','15.165.254.45','example.com:443','bad\nexample.com']:
            with self.assertRaises(ValueError):mod.domain_name(domain)
    def test_env_changes_do_not_remove_other_secrets(self):
        text='POSTGRES_PASSWORD=keep-this\nAPP_ORIGIN=http://old\nAPP_ORIGIN=http://duplicate\nAWS_SECRET_ACCESS_KEY=keep-too\n'
        result=mod.update_env(text,{'APP_ORIGIN':'https://new.example.com'})
        self.assertEqual(result.count('APP_ORIGIN='),1);self.assertIn('POSTGRES_PASSWORD=keep-this',result);self.assertIn('AWS_SECRET_ACCESS_KEY=keep-too',result)
    def test_key_generation_preservation_and_invalid_key_rejection(self):
        first,new=mod.existing_key('');self.assertTrue(new)
        second,new=mod.existing_key('LAB_CREDENTIALS_KEY='+first+'\n');self.assertEqual(first,second);self.assertFalse(new)
        with self.assertRaises(ValueError):mod.existing_key('LAB_CREDENTIALS_KEY=invalid\n')
