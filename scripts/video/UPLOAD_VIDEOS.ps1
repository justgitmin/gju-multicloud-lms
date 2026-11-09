param([Parameter(Mandatory=$true)][string]$Bucket,[string]$Profile='gju-operator',[string]$Region='ap-northeast-2')
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$items=Get-Content -Raw -Encoding UTF8 './patch-manifest.json' | ConvertFrom-Json
if($items.Count -ne 7){throw 'Expected exactly seven revised videos'}
foreach($item in $items){
 if($item.s3Key -notmatch '^courses/2026-multicloud/(aws|nhn)/0[1-8]/v2/(aws|nhn)-0[1-8]\.mp4$'){throw 'Unexpected media key'}
 $video=Join-Path $PSScriptRoot $item.s3Key
 $caption=Join-Path $PSScriptRoot $item.captionKey
 if((Get-FileHash -Algorithm SHA256 $video).Hash.ToLower() -ne $item.sha256){throw "Hash mismatch: $video"}
 if((Get-Item $video).Length -ne $item.bytes -or !(Test-Path $caption)){throw 'Invalid media files'}
}
foreach($item in $items){
 aws s3 cp $item.s3Key "s3://$Bucket/$($item.s3Key)" --content-type video/mp4 --profile $Profile --region $Region
 if($LASTEXITCODE -ne 0){throw 'Video upload failed; do not register yet'}
 aws s3 cp $item.captionKey "s3://$Bucket/$($item.captionKey)" --content-type text/vtt --profile $Profile --region $Region
 if($LASTEXITCODE -ne 0){throw 'Caption upload failed; do not register yet'}
}
Write-Output 'UPLOAD_OK: seven videos and seven captions. Run LMS media:register-course after pulling the revised code.'
