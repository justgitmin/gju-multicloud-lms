import unittest
from render_lesson import validate_audio,focus_for,timestamp,topic_tokens
class TimingTests(unittest.TestCase):
 def test_complete_sentence_fits_audio(self):
  self.assertEqual(validate_audio(b'\0'*48000,[{'start':0,'duration':.9,'text':'끝까지 설명합니다.'}],'끝까지 설명합니다.'),1)
 def test_truncated_speech_cannot_be_accepted(self):
  with self.assertRaisesRegex(ValueError,'ends before'):validate_audio(b'\0'*48000,[{'start':0,'duration':4,'text':'끝까지 설명합니다.'}],'끝까지 설명합니다.')
 def test_missing_text_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'coverage'):validate_audio(b'\0'*48000,[{'start':0,'duration':.8,'text':'첫 문장.'}],'첫 문장. 마지막 문장.')
 def test_focus_does_not_move_without_a_match(self):
  self.assertIsNone(focus_for('한 번 생각해 보세요.',['키페어','보안 그룹','접속 주소']))
 def test_focus_only_marks_a_unique_topic(self):
  self.assertEqual(focus_for('키페어와 개인 키를 확인합니다.',['네트워크 경로','키페어와 개인 키','웹 서비스']),1)
 def test_vtt_millisecond_rollover(self):self.assertEqual(timestamp(59.9999),'00:01:00.000')

from captions import display_caption
class CaptionTests(unittest.TestCase):
 def test_cloud_names_and_particles(self):
  self.assertEqual(display_caption('에이 더블유 에스의 브이피씨와 엔에이치엔 클라우드'), 'AWS의 VPC와 NHN Cloud')
 def test_longest_terms_first(self):
  self.assertEqual(display_caption('에이치티티피에스, 아이피 버전 사, 마이에스큐엘'), 'HTTPS, IPv4, MySQL')
 def test_quiz_and_normal_korean(self):
  self.assertEqual(display_caption('에이는 확인합니다. 정답은 비입니다. 비밀번호와 에이전트'), 'A는 확인합니다. 정답은 B입니다. 비밀번호와 에이전트')
 def test_commands_addresses(self):
  self.assertEqual(display_caption('에스에스에이치 마이너스 아이, 티씨피 이십이 번'), 'SSH -i, TCP 22번')

if __name__=='__main__':unittest.main()
