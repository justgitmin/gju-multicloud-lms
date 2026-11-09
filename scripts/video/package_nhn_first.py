"""Package only the seven NHN-first revisions after offline AV verification."""
import argparse,hashlib,json,re,shutil,zipfile
from pathlib import Path
from verify_av_sync import verify
from render_lesson import fingerprint

def main():
 p=argparse.ArgumentParser();p.add_argument('--video-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 repo=Path(__file__).resolve().parents[2];videos=Path(a.video_root);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 ids=['nhn-01','nhn-02','nhn-03','nhn-04','nhn-05','nhn-08','aws-08'];manifest_path=repo/'content/media-manifest.json';entries=json.loads(manifest_path.read_text());assert len(entries)==16
 unchanged={e['id']:dict(e) for e in entries if e['id'] not in ids};checks=[verify(videos/id) for id in ids]
 patch=[]
 for id in ids:
  lesson=json.loads((repo/'content'/id/'lesson.json').read_text());timeline=json.loads((videos/id/'timeline.json').read_text())
  for index,scene in enumerate(lesson['scenes']):
   audio=json.loads((videos/id/f'scene-{index:02}.json').read_text())
   assert audio['fingerprint']==fingerprint(scene['narration'],timeline['voice']), f'Stale narration: {id} scene {index+1}'
 for item in entries:
  if item['id'] not in ids:continue
  id=item['id'];folder=videos/id;video=folder/f'{id}.mp4';timing=json.loads((folder/'timeline.json').read_text())
  item.update(durationSeconds=timing['duration'],bytes=video.stat().st_size,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),s3Key=re.sub(r'/v\d+/', '/v2/',item['s3Key']),captionKey=re.sub(r'/v\d+/', '/v2/',item['captionKey']),status='nhn-first-revised; technically-verified; final listening pending',serverUploaded=False,syncRevision=4,captionRevision=2)
  for name in [f'{id}.vtt','timeline.json']:shutil.copyfile(folder/name,repo/'content'/id/name)
  (repo/'content'/id/'video-manifest.json').write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n');patch.append(dict(item))
 assert all(unchanged[e['id']]==e for e in entries if e['id'] in unchanged)
 manifest_path.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
 curriculum=repo/'lib/curriculum.ts';text=curriculum.read_text()
 for group in ['nhn','aws']:
  group_entries=sorted([e for e in entries if e['id'].startswith(group+'-')],key=lambda e:e['id'])
  lines=text.splitlines()
  for i,line in enumerate(lines):
   if "id:'"+group+"'" in line:lines[i]=re.sub(r'minutes:\[[^\]]*\],durationSeconds:\[[^\]]*\]','minutes:'+json.dumps([round(e['durationSeconds']/60,1) for e in group_entries])+',durationSeconds:'+json.dumps([round(e['durationSeconds']) for e in group_entries]),line)
  text='\n'.join(lines)+'\n'
 curriculum.write_text(text)
 report={'changedIds':ids,'unchangedIds':list(unchanged),'checks':checks,'unchangedMediaRecords':9,'audioReview':'Technical sentence coverage verified. Human pronunciation/listening review pending.','deployment':'v2 new object paths; existing v1 files retained. Register after all fourteen new objects are uploaded. Changed lesson versions increment; nine unchanged lessons retain versions.'}
 (repo/'docs/nhn-first-video-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 archive=out/'GJU_NHN_First_Changed_7_Videos.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
  for e in patch:z.write(videos/e['id']/f"{e['id']}.mp4",e['s3Key']);z.write(videos/e['id']/f"{e['id']}.vtt",e['captionKey'])
  z.writestr('patch-manifest.json',json.dumps(patch,ensure_ascii=False,indent=2))
  z.write(repo/'docs/nhn-first-video-verification.json','verification.json')
  for name in ['UPLOAD_VIDEOS.ps1','README_KO.txt']:
   source=repo/'scripts/video'/name
   if source.exists():z.write(source,name)
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None
 print('SELECTIVE_PACKAGE_OK',archive,archive.stat().st_size,flush=True)
if __name__=='__main__':main()
