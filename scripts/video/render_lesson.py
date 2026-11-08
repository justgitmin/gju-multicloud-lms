"""Narrated lesson renderer with PCM/sample and video-frame locked scene timing.
Requires Pillow, edge-tts and ffmpeg/ffprobe. Never trusts a cached MP3's container
length alone: sentence coverage, decoded audio length and hashes are checked.
"""
import argparse,asyncio,json,os,hashlib,math,wave,html,re,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import edge_tts
from visuals import draw_visual
from captions import display_caption
FPS=15
RATE=24000
SAMPLES_PER_FRAME=RATE//FPS
HOLD_FRAMES=6

def run(args):return subprocess.check_output(args)
def decode(path):return run(['ffmpeg','-v','error','-i',str(path),'-ar',str(RATE),'-ac','1','-f','s16le','-'])
def probe(path):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
def fingerprint(text,voice):return hashlib.sha256((text+voice+'-5%').encode()).hexdigest()
def normalized(text):return re.sub(r'\s+','',html.unescape(text))
def validate_audio(pcm,bounds,narration):
 if not bounds:raise ValueError('No sentence timing metadata')
 if normalized(''.join(b['text'] for b in bounds))!=normalized(narration):raise ValueError('Incomplete narration text coverage')
 length=len(pcm)/(RATE*2)
 if max(b['start']+b['duration'] for b in bounds)>length+.18:raise ValueError('Audio ends before final spoken sentence')
 if any(b['start']<0 or b['duration']<=0 for b in bounds):raise ValueError('Invalid sentence timing')
 if any(bounds[i]['start']>bounds[i+1]['start'] for i in range(len(bounds)-1)):raise ValueError('Out-of-order sentence timings')
 return length

def timestamp(t):
 ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
def wrap(draw,text,font,width):
 lines=[];line=''
 for ch in text:
  if draw.textlength(line+ch,font=font)>width and line:lines.append(line);line=''
  line+=ch
 if line:lines.append(line)
 return lines

ALIASES={'ssh':'에스에스에이치','iam':'아이엠','vpc':'브이피씨','subnet':'서브넷','db':'데이터베이스','ip':'아이피','rds':'알디에스','s3':'에스쓰리','nginx':'엔진엑스','ec2':'이씨투','cpu':'씨피유','public':'퍼블릭','private':'프라이빗','floating':'플로팅'}
STOP={'확인','기록','사용','직접','필요','다음','예시','먼저','전체','실제','준비','각각','같은','결과','따로','대한','같이'}
def topic_tokens(text):
 text=text.lower()
 for a,b in sorted(ALIASES.items(),key=lambda x:-len(x[0])):text=re.sub(r'\b'+a+r'\b',b,text)
 tokens=re.findall(r'[가-힣a-z0-9]+',text)
 result=[]
 for t in tokens:
  t=re.sub(r'(에서는|으로|에서|부터|까지|에게|이면|에는|의|을|를|은|는|이|가)$','',t)
  if len(t)>=2 and t not in STOP:result.append(t)
 return result

def focus_for(sentence,bullets):
 spoken=' '.join(topic_tokens(sentence));scores=[]
 for bullet in bullets:
  terms=topic_tokens(bullet);score=sum(min(5,len(t)) for t in terms if t in spoken)
  scores.append(score)
 if not scores or max(scores)<3:return None
 best=max(scores)
 return scores.index(best) if scores.count(best)==1 else None

async def get_audio(scene,index,out,cache,voice,allow_external_tts=False):
 mp3=out/f'scene-{index:02}.mp3';meta=out/f'scene-{index:02}.json';key=fingerprint(scene['narration'],voice)
 candidates=[(mp3,meta),(cache/f'scene-{index:02}.mp3',cache/f'scene-{index:02}.json')]
 for ap,mp in candidates:
  try:
   data=json.loads(mp.read_text());bounds=data['boundaries'] if isinstance(data,dict) else data
   if isinstance(data,dict) and data.get('fingerprint')!=key:continue
   contents=ap.read_bytes();digest=hashlib.sha256(contents).hexdigest()
   if isinstance(data,dict) and data.get('sha256') and data['sha256']!=digest:continue
   pcm=decode(ap);length=validate_audio(pcm,bounds,scene['narration'])
   if ap!=mp3:mp3.write_bytes(contents)
   meta.write_text(json.dumps({'fingerprint':key,'sha256':digest,'decodedSamples':len(pcm)//2,'boundaries':bounds},ensure_ascii=False))
   return pcm,bounds,length,'verified-cache'
  except (OSError,ValueError,KeyError,subprocess.CalledProcessError):pass
 if not allow_external_tts:raise RuntimeError(f'Scene {index+1} requires complete audio resynthesis; external TTS is disabled until explicitly authorized')
 for attempt in range(3):
  partial=out/f'scene-{index:02}.part.mp3';bounds=[]
  try:
   with partial.open('wb') as f:
    async for c in edge_tts.Communicate(scene['narration'],voice,rate='-5%',boundary='SentenceBoundary').stream():
     if c['type']=='audio':f.write(c['data'])
     elif c['type'] in ['SentenceBoundary','WordBoundary']:bounds.append({'start':c['offset']/1e7,'duration':c['duration']/1e7,'text':c['text']})
    f.flush();os.fsync(f.fileno())
   pcm=decode(partial);length=validate_audio(pcm,bounds,scene['narration']);digest=hashlib.sha256(partial.read_bytes()).hexdigest();os.replace(partial,mp3)
   meta.write_text(json.dumps({'fingerprint':key,'sha256':digest,'decodedSamples':len(pcm)//2,'boundaries':bounds},ensure_ascii=False));return pcm,bounds,length,'regenerated'
  except Exception as e:
   partial.unlink(missing_ok=True)
   if attempt==2:raise RuntimeError(f'Audio validation failed for scene {index+1}: {e}') from e
 raise RuntimeError('unreachable')

async def main():
 parser=argparse.ArgumentParser();parser.add_argument('lesson');parser.add_argument('output');parser.add_argument('--font',required=True);parser.add_argument('--audio-cache');parser.add_argument('--voice',default='ko-KR-SunHiNeural');parser.add_argument('--allow-external-tts',action='store_true',help='Use only after explicit approval to send narration to the external speech service');args=parser.parse_args()
 if os.environ.get('SSL_CERT_FILE'):
  from edge_tts import communicate as mod
  mod._SSL_CTX.load_verify_locations(cafile=os.environ['SSL_CERT_FILE'])
 lesson=json.loads(Path(args.lesson).read_text());out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True);cache=Path(args.audio_cache).resolve() if args.audio_cache else out
 fonts={n:ImageFont.truetype(args.font,n) for n in [22,26,30,34,40,54,68]};concat=[];cues=[];timeline=[];all_pcm=bytearray();global_frame=0
 for i,scene in enumerate(lesson['scenes']):
  pcm,bounds,voice_length,source=await get_audio(scene,i,out,cache,args.voice,args.allow_external_tts)
  scene_frames=math.ceil((len(pcm)//2)/SAMPLES_PER_FRAME)+HOLD_FRAMES
  padded=pcm+b'\0'*(scene_frames*SAMPLES_PER_FRAME*2-len(pcm));all_pcm.extend(padded)
  with wave.open(str(out/f'scene-{i:02}.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(padded)
  timing={'scene':i+1,'title':scene['title'],'startFrame':global_frame,'endFrame':global_frame+scene_frames,'start':global_frame/FPS,'duration':scene_frames/FPS,'voiceDuration':voice_length,'audioSource':source,'sentences':[]}
  boundaries=[0]+[min(scene_frames-1,max(0,round(b['start']*FPS))) for b in bounds[1:]]+[scene_frames]
  for j,b in enumerate(bounds):
   start_frame=boundaries[j];end_frame=boundaries[j+1]
   if end_frame<=start_frame:raise ValueError('A spoken sentence would have no screen time')
   scene['_focus']=focus_for(b['text'],scene['bullets']);scene['_caption']=b['text'];scene['_revealed']=any('정답은' in x['text'] for x in bounds[:j+1])
   image=Image.new('RGB',(1920,1080),'#f3f6f1');d=ImageDraw.Draw(image)
   d.rectangle((0,0,1920,10),fill='#247156');d.text((100,55),'GJU / CLOUD CAMPUS',font=fonts[26],fill='#204b3d');d.text((1520,55),f'{lesson["id"].upper()}  {i+1:02} / {len(lesson["scenes"]):02}',font=fonts[22],fill='#64796b');d.text((100,160),scene['kicker'],font=fonts[26],fill='#b56b16')
   title_lines=wrap(d,scene['title'],fonts[68],1700)
   if len(title_lines)>1:raise ValueError('Title needs a shorter layout')
   d.text((100,220),scene['title'],font=fonts[68],fill='#153a2d')
   if scene.get('visual'):draw_visual(d,scene,fonts,j,len(bounds))
   else:
    for k,bullet in enumerate(scene['bullets']):
     y=405+k*100;d.rounded_rectangle((100,y+8,112,y+48),radius=5,fill='#da9c3d');d.text((145,y),bullet,font=fonts[40],fill='#294b3b')
   d.rounded_rectangle((70,835,1850,1015),radius=18,fill='#193c30');caption=wrap(d,display_caption(b['text']),fonts[34],1670)
   if len(caption)>3:raise ValueError('Caption overflow')
   for k,line in enumerate(caption):d.text((115,860+k*48),line,font=fonts[34],fill='white')
   d.text((100,1032),'광주대학교 멀티클라우드 운영 · 자체 제작 학습자료 / 검수용',font=fonts[22],fill='#6b7e70')
   frame=out/f'frame-{i:02}-{j:03}.png';image.save(frame)
   concat.append(f"file '{frame}'\noption framerate {FPS}\nduration {(end_frame-start_frame)/FPS:.12f}\n")
   cue_start=(global_frame+start_frame)/FPS;cue_end=(global_frame+end_frame)/FPS
   cues.append((cue_start,cue_end,display_caption(b['text'])));timing['sentences'].append({'startFrame':global_frame+start_frame,'endFrame':global_frame+end_frame,'text':display_caption(b['text']),'spokenText':b['text'],'focus':scene['_focus']})
  timeline.append(timing);global_frame+=scene_frames;print(f'SCENE {i+1}/{len(lesson["scenes"])} {source} voice={voice_length:.3f}s page={scene_frames/FPS:.3f}s',flush=True)
 concat.append(f"file '{frame}'\noption framerate {FPS}\n");(out/'frames.txt').write_text(''.join(concat))
 wav=out/'narration.wav'
 with wave.open(str(wav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(all_pcm)
 tmp=out/f'{lesson["id"]}.rendering.mp4';target=out/f'{lesson["id"]}.mp4'
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(out/'frames.txt'),'-i',str(wav),'-vf',f'fps={FPS},format=yuv420p','-frames:v',str(global_frame),'-c:v','libx264','-preset','ultrafast','-threads','2','-crf','24','-c:a','aac','-b:a','128k','-movflags','+faststart',str(tmp)],check=True)
 info=probe(tmp);video=next(x for x in info['streams'] if x['codec_type']=='video');audio=next(x for x in info['streams'] if x['codec_type']=='audio')
 if int(video['nb_frames'])!=global_frame:raise ValueError('Encoded frame count mismatch')
 if abs(float(audio['duration'])-global_frame/FPS)>.1:raise ValueError('Encoded audio/video duration mismatch')
 (out/f'{lesson["id"]}.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{timestamp(a)} --> {timestamp(b)}\n{t}' for a,b,t in cues))
 (out/'timeline.json').write_text(json.dumps({'duration':global_frame/FPS,'fps':FPS,'totalFrames':global_frame,'totalSamples':len(all_pcm)//2,'scenes':timeline,'voice':args.voice,'timingMethod':'PCM-sample-and-video-frame-locked','audioReview':'technical-sync-checked; final listening pending'},ensure_ascii=False,indent=2))
 os.replace(tmp,target);print(f'VIDEO_READY {target}',flush=True)

if __name__=='__main__':asyncio.run(main())
