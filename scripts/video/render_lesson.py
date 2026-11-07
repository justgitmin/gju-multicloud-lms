"""Render original lesson JSON to narrated MP4 and WebVTT.
Requires Python pillow, edge-tts; ffmpeg/ffprobe; a Korean font path.
Network TTS is used only for author-written narration. No account/student data.
"""
import argparse,asyncio,json,os,re,subprocess,ssl,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import edge_tts
from visuals import draw_visual

def duration(p):
 return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True))
def timestamp(t):
 ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
def wrap(draw,text,font,width):
 lines=[];line=''
 for ch in text:
  if draw.textlength(line+ch,font=font)>width and line:lines.append(line);line=''
  line+=ch
 if line:lines.append(line)
 return lines
async def main():
 p=argparse.ArgumentParser();p.add_argument('lesson');p.add_argument('output');p.add_argument('--font',required=True);p.add_argument('--voice',default='ko-KR-SunHiNeural');a=p.parse_args()
 # Trust the host-managed CA store in managed corporate environments; TLS verification stays enabled.
 if os.environ.get('SSL_CERT_FILE'):
  from edge_tts import communicate as communicate_module
  communicate_module._SSL_CTX.load_verify_locations(cafile=os.environ['SSL_CERT_FILE'])
 lesson=json.loads(Path(a.lesson).read_text());out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
 fonts={size:ImageFont.truetype(a.font,size) for size in [22,26,30,34,40,54,68]}
 cues=[];offset=0;concat=[];audio=[];timeline=[]
 for i,scene in enumerate(lesson['scenes']):
  mp3=out/f'scene-{i:02}.mp3';meta=out/f'scene-{i:02}.json';bounds=[]
  fingerprint=hashlib.sha256((scene['narration']+a.voice+'-5%').encode()).hexdigest()
  cache=json.loads(meta.read_text()) if meta.exists() else None
  if mp3.exists() and isinstance(cache,dict) and cache.get('fingerprint')==fingerprint:bounds=cache['boundaries']
  else:
   communicate=edge_tts.Communicate(scene['narration'],a.voice,rate='-5%',boundary='SentenceBoundary')
   with mp3.open('wb') as f:
    async for chunk in communicate.stream():
     if chunk['type']=='audio':f.write(chunk['data'])
     elif chunk['type'] in ['SentenceBoundary','WordBoundary']:bounds.append({'start':chunk['offset']/10000000,'duration':chunk['duration']/10000000,'text':chunk['text']})
   meta.write_text(json.dumps({'fingerprint':fingerprint,'boundaries':bounds},ensure_ascii=False))
  length=duration(mp3);audio.append(mp3);timeline.append({'scene':i+1,'title':scene['title'],'start':offset,'duration':length})
  if not bounds:bounds=[{'start':0,'duration':length,'text':scene['narration']}]
  for c in bounds:cues.append((offset+c['start'],min(offset+length,offset+c['start']+c['duration']),c['text']))
  # Exact sentence boundaries create both readable caption frames and the optional VTT track.
  segments=[]
  for j,c in enumerate(bounds):
   start=0 if j==0 else c['start'];end=bounds[j+1]['start'] if j+1<len(bounds) else length
   if end<=start:continue
   image=Image.new('RGB',(1920,1080),'#f3f6f1');d=ImageDraw.Draw(image)
   d.rectangle((0,0,1920,10),fill='#247156');d.text((100,55),'GJU / CLOUD CAMPUS',font=fonts[26],fill='#204b3d')
   d.text((1520,55),f'AWS ONLINE  {i+1:02} / {len(lesson["scenes"]):02}',font=fonts[22],fill='#64796b')
   d.text((100,160),scene['kicker'],font=fonts[26],fill='#b56b16')
   for k,line in enumerate(wrap(d,scene['title'],fonts[68],1700)):d.text((100,220+k*95),line,font=fonts[68],fill='#153a2d')
   if scene.get('visual'):
    scene['_caption']=c['text'];scene['_revealed']=any('정답' in x['text'] for x in bounds[:j+1])
    draw_visual(d,scene,fonts,j,len(bounds))
   else:
    for k,bullet in enumerate(scene['bullets']):
     y=405+k*100;d.rounded_rectangle((100,y+8,112,y+48),radius=5,fill='#da9c3d')
     d.text((145,y),bullet,font=fonts[40],fill='#294b3b')
   d.rounded_rectangle((70,835,1850,1015),radius=18,fill='#193c30')
   lines=wrap(d,c['text'],fonts[34],1670)
   if len(lines)>3:raise ValueError('Caption too long; split narration sentences.')
   for k,line in enumerate(lines):d.text((115,860+k*48),line,font=fonts[34],fill='white')
   d.text((100,1032),'광주대학교 멀티클라우드 운영 · 자체 제작 학습자료 / 검수용',font=fonts[22],fill='#6b7e70')
   frame=out/f'frame-{i:02}-{j:03}.png';image.save(frame);concat.append(f"file '{frame}'\nduration {end-start:.6f}\n")
  offset+=length
  print(f'SCENE {i+1}/{len(lesson["scenes"])}: {length:.1f}s',flush=True)
 last=frame;concat.append(f"file '{last}'\n")
 (out/'frames.txt').write_text(''.join(concat));(out/'audio.txt').write_text(''.join(f"file '{p}'\n" for p in audio))
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(out/'audio.txt'),'-c:a','aac','-b:a','128k',str(out/'narration.m4a')],check=True)
 target=out/f"{lesson['id']}.mp4"
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(out/'frames.txt'),'-i',str(out/'narration.m4a'),'-vf','fps=15,format=yuv420p','-c:v','libx264','-preset','ultrafast','-threads','2','-crf','24','-c:a','copy','-t',str(offset),'-movflags','+faststart',str(target)],check=True)
 (out/f"{lesson['id']}.vtt").write_text('WEBVTT\n\n'+'\n\n'.join(f'{timestamp(s)} --> {timestamp(e)}\n{t}' for s,e,t in cues if e>s))
 (out/'timeline.json').write_text(json.dumps({'duration':duration(target),'scenes':timeline,'voice':a.voice,'audioReview':'pending'},ensure_ascii=False,indent=2))
 print(f'VIDEO_READY {target}',flush=True)
asyncio.run(main())
