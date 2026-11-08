"""Check rendered PCM/frame alignment and sentence coverage without network access."""
import argparse,json,subprocess,wave
from pathlib import Path
from captions import display_caption
from render_lesson import FPS,RATE,SAMPLES_PER_FRAME,validate_audio

def audit(directory):
 path=Path(directory);meta=json.loads((path/'timeline.json').read_text());id=path.name
 with wave.open(str(path/'narration.wav')) as f:
  if f.getframerate()!=RATE or f.getnchannels()!=1:raise ValueError('Unexpected PCM format')
  samples=f.getnframes()
 if samples!=meta['totalFrames']*SAMPLES_PER_FRAME:raise ValueError('PCM/video frame count mismatch')
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path/f'{id}.mp4')],text=True))
 video=next(s for s in info['streams'] if s['codec_type']=='video');audio=next(s for s in info['streams'] if s['codec_type']=='audio')
 if int(video['nb_frames'])!=meta['totalFrames']:raise ValueError('Encoded frame count mismatch')
 gap=abs(float(video['duration'])-float(audio['duration']))
 if gap>.1:raise ValueError('Encoded streams drift')
 for i,scene in enumerate(meta['scenes']):
  with wave.open(str(path/f'scene-{i:02}.wav')) as f:
   if f.getnframes()!=(scene['endFrame']-scene['startFrame'])*SAMPLES_PER_FRAME:raise ValueError('Scene lengths differ')
  if scene['startFrame']/FPS!=scene['start']:raise ValueError('Scene boundary is not frame locked')
  if scene['duration']-scene['voiceDuration']<.399:raise ValueError('No safe speech-ending hold')
  bounds=json.loads((path/f'scene-{i:02}.json').read_text())['boundaries']
  if [s['text'] for s in scene['sentences']] != [display_caption(b['text']) for b in bounds]:raise ValueError('Display caption mismatch')
  if max(b['start']+b['duration'] for b in bounds)>scene['voiceDuration']+.18:raise ValueError('Speech end missing')
 subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(path/f'{id}.mp4'),'-f','null','-'],check=True)
 return {'id':id,'scenes':len(meta['scenes']),'duration':meta['duration'],'streamGapSeconds':gap,'PCMFrameLocked':True,'speechEndingCovered':True,'decode':'passed'}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('directories',nargs='+');args=parser.parse_args()
 for directory in args.directories:print(json.dumps(audit(directory)),flush=True)
