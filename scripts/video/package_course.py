"""Package only fully verified videos and update manifests; keep S3 object paths."""
import argparse,json,hashlib,zipfile,shutil,re,os
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--video-root',required=True);p.add_argument('--output',required=True);args=p.parse_args()
 repo=Path(__file__).resolve().parents[2];videos=Path(args.video_root).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
 report=json.loads((repo/'docs/video-sync-verification.json').read_text());assert report['verifiedVideos']==16 and all(r['status']=='passed' for r in report['results'])
 manifest=json.loads((repo/'content/media-manifest.json').read_text());assert len(manifest)==16
 for item in manifest:
  id=item['id'];folder=videos/id;mp4=folder/f'{id}.mp4';timeline=json.loads((folder/'timeline.json').read_text());digest=hashlib.sha256(mp4.read_bytes()).hexdigest()
  item.update({'durationSeconds':timeline['duration'],'bytes':mp4.stat().st_size,'sha256':digest,'syncRevision':2,'syncCheck':'PCM/frame/encoded-speech/page-boundary passed','status':'technically-verified; final listening pending','serverUploaded':False})
  for name in [f'{id}.vtt','timeline.json']:shutil.copyfile(folder/name,repo/'content'/id/name)
  (repo/'content'/id/'video-manifest.json').write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n')
 (repo/'content/media-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 curriculum=repo/'lib/curriculum.ts';text=curriculum.read_text();groups=iter(['aws','nhn'])
 def durations(match):
  group=next(groups);entries=[e for e in manifest if e['id'].startswith(group)]
  return 'minutes:'+json.dumps([round(e['durationSeconds']/60,1) for e in entries])+',durationSeconds:'+json.dumps([round(e['durationSeconds']) for e in entries])
 text=re.sub(r'minutes:\[[^\]]*\],durationSeconds:\[[^\]]*\]',durations,text);curriculum.write_text(text)
 rows=['# 영상 목록 — 싱크 수정본','', '전체 16편의 음성·화면·자막을 PCM 샘플과 영상 프레임 기준으로 다시 맞췄습니다.','', '| ID | 제목 | 실제 길이 | S3 키 |','|---|---|---|---|']
 for e in manifest:
  sec=round(e['durationSeconds']);rows.append(f"| {e['id']} | {e['title']} | {sec//60}:{sec%60:02} | `{e['s3Key']}` |")
 rows+=['','## 온라인 차시 시간 배분','']
 for group in ['aws','nhn']:
  minutes=sum(e['durationSeconds'] for e in manifest if e['id'].startswith(group))/60;rows.append(f'- {group.upper()}: 영상 {minutes:.1f}분 + 직접 실습 {160-minutes:.1f}분 + 평가 20분 = 180분 (학교 인정 기준 별도 확인).')
 (repo/'docs/CONTENT_INDEX.md').write_text('\n'.join(rows)+'\n')
 notice='싱크 수정본입니다. 압축을 풀고 버킷 최상위에서 courses 폴더의 MP4와 captions-ko.vtt를 함께 교체하세요. 비공개 설정 유지. 기존 S3 키는 같습니다. LMS에 이미 등록했다면 media:register-course를 다시 실행하여 길이·해시·콘텐츠 버전을 갱신하세요. 음성·자막·화면 기술 검증을 완료했으며 최종 전 구간 청취·발음 검수와 실제 S3 재생 확인은 별도입니다.\n'
 for group in ['aws','nhn']:
  target=out/f'GJU_{group.upper()}_Videos_01-08.zip';temporary=target.with_suffix('.part.zip')
  with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_STORED) as z:
   for e in manifest:
    if not e['id'].startswith(group):continue
    z.write(videos/e['id']/f"{e['id']}.mp4",e['s3Key']);z.write(videos/e['id']/f"{e['id']}.vtt",e['captionKey'])
   z.writestr('SYNC_FIX_README.txt',notice)
  with zipfile.ZipFile(temporary) as z:assert z.testzip() is None;assert len(z.namelist())==17
  os.replace(temporary,target);print('PACKAGED',target,target.stat().st_size,flush=True)
 target=out/'GJU_Lab_and_Production_Materials.zip';temporary=target.with_suffix('.part.zip')
 with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for directory,label in [('content','sources'),('examples/demo-app','demo-app'),('scripts/video','video-tools')]:
   for file in sorted((repo/directory).rglob('*')):
    if file.is_file() and '__pycache__' not in file.parts:z.write(file,str(Path(label)/file.relative_to(repo/directory)))
  for name in ['STUDENT_LAB_GUIDE.md','CONTENT_INDEX.md','DEPLOYMENT.md','VIDEO_SYNC_REPAIR.md','video-sync-verification.json']:z.write(repo/'docs'/name,name)
 with zipfile.ZipFile(temporary) as z:assert z.testzip() is None
 os.replace(temporary,target)
 shutil.copyfile(videos/'nhn-01/nhn-01.mp4',out/'NHN_01_Sync_Fixed.mp4')
 print('PACKAGE_CHECKS_PASSED',sum(e['durationSeconds'] for e in manifest)/60,flush=True)
if __name__=='__main__':main()
