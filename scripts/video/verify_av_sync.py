"""Offline cross-check of encoded audio and page boundaries against render sources."""
import json,subprocess
from pathlib import Path
import numpy as np
from scipy.signal import correlate
from PIL import Image
from audit_sync import audit

def decoded8k(path):
 data=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-ar','8000','-ac','1','-f','s16le','-'])
 return np.frombuffer(data,dtype='<i2').astype(np.float64)
def verify(path):
 path=Path(path);result=audit(path);meta=json.loads((path/'timeline.json').read_text());video=path/(path.name+'.mp4');reference=decoded8k(path/'narration.wav');encoded=decoded8k(video)
 offsets=[];scores=[]
 for scene in meta['scenes']:
  at=round((scene['start']+1)*8000);pattern=reference[at:at+12000];lo=max(0,at-1600);search=encoded[lo:min(len(encoded),at+12000+1600)]
  cross=correlate(search,pattern,mode='valid',method='fft');squares=np.concatenate(([0.],np.cumsum(search*search)));energy=squares[len(pattern):]-squares[:-len(pattern)]
  norm=np.sqrt(np.maximum(energy,1)*max(np.dot(pattern,pattern),1));coefficient=cross/norm;best=int(np.argmax(coefficient));lag=(lo+best-at)/8000;score=float(coefficient[best]);offsets.append(lag);scores.append(score)
  if abs(lag)>.025 or score<.95:raise ValueError(f'Encoded speech mismatch at scene {scene["scene"]}: {lag}s / {score}')
 expression='+'.join(f'eq(n\\,{s["startFrame"]})' for s in meta['scenes'])
 raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(video),'-an','-vf',f'select={expression},scale=320:180','-vsync','0','-pix_fmt','rgb24','-f','rawvideo','-'])
 frames=np.frombuffer(raw,dtype=np.uint8).reshape((-1,180,320,3));errors=[]
 if len(frames)!=len(meta['scenes']):raise ValueError('Page boundary sample count mismatch')
 for index,frame in enumerate(frames):
  expected=np.asarray(Image.open(path/f'frame-{index:02}-000.png').convert('RGB').resize((320,180),Image.Resampling.BICUBIC))
  error=float(np.abs(frame.astype(float)-expected.astype(float)).mean());errors.append(error)
  if error>6:raise ValueError(f'Wrong page at scene boundary {index+1}: error={error}')
 result.update({'sceneStartAudioMaxOffsetSeconds':max(abs(v) for v in offsets),'minimumSpeechCorrelation':min(scores),'pageBoundaryMaxPixelError':max(errors),'pageBoundariesChecked':len(frames),'status':'passed'})
 return result
if __name__=='__main__':
 import sys
 for path in sys.argv[1:]:print(json.dumps(verify(path)),flush=True)
