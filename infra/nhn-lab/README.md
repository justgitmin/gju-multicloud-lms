# NHN 학생 역할 일괄 변경 (Windows / Python 3)

공식 Framework API와 User Access Key Opaque 토큰을 사용합니다. 추가 설치 패키지는 없습니다. AWS 관리 도구와 별도의 운영자 CLI입니다. 이 기능은 기존 프로젝트/IAM 역할 변경만 수행하며 프로젝트·계정·서버·DB를 생성하거나 삭제하지 않습니다.

## 현재 기본 대상

- 조직: `TBIT_Edu01` (`8NQqYpYUnlEnixaG`)
- 기준 프로젝트: `TBIT_Edu01_Pro01` (`srwJJxcH`)
- 대상: `TBIT_Edu01_Pro01`~`TBIT_Edu01_Pro10` / `educity01`~`educity10`
- 보호 대상: NHN Cloud 계정 `web@tbit.co.kr`의 프로젝트 ADMIN
- 학생의 기존 프로젝트 역할 전체를 다음 4개로 교체:
  - Infrastructure VIEWER
  - Object Storage Object READER
  - Object Storage Object WRITER
  - RDS for MySQL VIEWER

**Infrastructure VIEWER는 엄격한 읽기 전용이 아닙니다.** 콘솔 설명의 Key Pair, Direct Connect, NAS(Offline) 생성/변경/삭제 예외 권한을 그대로 포함합니다. 본 도구는 역할을 조합할 뿐, 이 예외 권한을 없애거나 과금 상한을 설정하지 않습니다. 프로젝트별 격리는 역할을 변경하는 조직의 STABLE 프로젝트 멤버 목록에서 검사합니다. 다른 조직의 접근, 조직에서 상속한 권한까지 제한했다는 의미는 아닙니다.

## Windows 실행

Windows PowerShell 콘솔 또는 Windows Terminal에서 실행하세요. LMS 서버가 아닌 운영자 PC입니다.

```powershell
cd "$HOME\gju-lab-manager"
git pull --ff-only origin main
py -3 infra/nhn-lab/roles.py plan
```

User Access Key와 Secret Access Key는 실행 중 숨김 입력합니다. 붙여넣어도 화면에는 표시되지 않습니다. 키를 명령 인자·소스·.env·채팅에 넣지 마세요. 자동 입력이나 PowerShell ISE 등 숨김 입력이 불가능한 환경에서는 중지합니다. 운영자 키는 메모리에서 인증에만 사용하며 계획/로그 파일에는 포함하지 않습니다. 발급한 Opaque 토큰은 종료할 때 만료를 요청합니다. 원래 User Access Key 자체는 폐기하지 않습니다.

`plan`은 인증/조회만 수행합니다. 다음을 확인하고 `.nhn-lab-state/roles-01-10.plan.json`에 변경 전 역할·조건과 변경 예정 역할 ID를 저장합니다.

1. 조직과 Pro01 기준 ID가 맞고 모든 대상 프로젝트가 존재하는지
2. IAM ID/UUID가 각 프로젝트에 정확히 대응하는지
3. 대상 학생이 같은 조직의 다른 STABLE 프로젝트에도 배정됐는지 (발견 시 중지, 자동 제거하지 않음)
4. 각 프로젝트에서 보호할 NHN Cloud 운영자 계정과 직접 ADMIN 역할을 확인할 수 있는지
5. 프로젝트 역할 목록에서 정확한 이름의 서비스 역할 4개를 고를 수 있는지 (이름 추측이나 광범위 역할 대체 금지)

마스킹만 된 운영자 이메일, 예상과 다른 API 스키마/역할명, 권한 부족, 중복/누락이 있으면 중지합니다. 실환경 인증 정보로 실행한 검증은 별도로 필요합니다. 계획 파일은 기존 파일을 덮어쓰지 않습니다. 재조회하려면 `--plan .nhn-lab-state/review-2.json`처럼 다른 경로를 사용하세요.

## 적용 (계획 확인 후)

```powershell
py -3 infra/nhn-lab/roles.py apply
```

다시 키를 숨김 입력하고, 표시된 대상이 맞으면 `TBIT_Edu01_Pro01-10`을 정확히 입력합니다. 입력 직후 모든 대상을 다시 조회해 계획과 동일한지 검사합니다. 변경 중 각 대상의 IAM UUID/원래 역할/운영자 역할도 재확인하며, 성공 여부는 API 응답뿐 아니라 다시 조회한 역할로 확인합니다. 운영자의 역할, 학생 비밀번호, LMS 기록은 수정하지 않습니다.

실행 전 완전한 변경 전 스냅샷을 포함한 `apply-<UTC시각>.json`을 생성하고, 각 작업 전후 상태를 기록합니다. 백업에 실패하면 수정하지 않습니다. 서버가 응답을 잃어도 쓰기를 자동 재시도하지 않습니다. 실패 시 이후 작업을 중단하고 성공한 이전 프로젝트는 변경 상태로 남습니다. 여러 API 요청이므로 전체 원자적 작업은 아닙니다.

중단 시 결과 파일과 콘솔의 실제 역할을 대조하세요. `STOPPED_CHECK_LIVE_STATE` 또는 `WRITE_REQUESTED`는 변경 여부를 확인해야 하는 상태입니다. 복구가 필요하면 백업의 프로젝트/IAM/기존 역할과 조건을 확인한 뒤 운영자 콘솔에서 해당 학생만 복원하세요. 자동 롤백으로 ADMIN을 다시 부여하지 않습니다. 재적용은 현재 상태를 새 계획 파일로 조회한 뒤 진행하세요.

## 다른 범위/환경

기존 11~20까지 모두 준비된 뒤 `--start 1 --end 20 --plan .nhn-lab-state/roles-01-20.json`으로 새 계획을 만들 수 있습니다. 없는 프로젝트/학생은 자동 생성하지 않습니다. 다른 조직에서는 조직 ID, 프로젝트 접두사, 학생 접두사, Pro01 기준 ID, 보호할 운영자 이메일을 모두 해당 환경에 맞춰 지정하세요. `--help` 참조. apply는 저장된 계획의 설정만 사용합니다.

## 테스트

```text
python -m unittest discover -s infra/nhn-lab -p 'test_*.py' -v
```

테스트는 가짜 API 응답으로 실행되며 실제 NHN 호출/변경이 없습니다. 인증 요청 형식, 페이지 누락·중복, 대상 연결/조직/관리자 보호, 잘못된 역할, 기존 조건 보존, 변경 전 백업, 오래된 계획, 부분 실패, 재조회 불일치, 이미 적용된 상태를 검증합니다.

공식 근거:
- https://docs.nhncloud.com/ko/nhncloud/ko/public-api/framework-api/
- https://docs.nhncloud.com/ko/nhncloud/ko/public-api/user-access-key-token/
