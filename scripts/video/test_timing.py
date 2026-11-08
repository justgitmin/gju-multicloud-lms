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
if __name__=='__main__':unittest.main()
