# Resource operations console

The resource view is an operations table with cloud, type, event and student/name
filters. Default type is Server; DB, Object Storage and related resources are
separate choices. A single selection performs an individual operation; multiple
selections enqueue grouped work by connection. Selection, confirmation and result
are distinct. No resource action runs as part of deployment or page rendering.

## Supported scope

- Existing education-assigned AWS EC2, NHN Instance and NAVER VPC servers:
  start/stop and delete after stopping. The platform does not disable native
  termination protection or force shutdowns.
- NHN batch resources: server, private RDS MySQL, Object Storage container, DB
  security/parameter groups, and recorded VPC/subnet/Internet Gateway/security
  group/floating IP identifiers. Network resources and groups have no power
  operation. Only exact recorded resources are eligible for deletion; attached
  dependencies can cause an explicit API failure. Routes/attachments are not
  automatically detached to force a deletion. Root disk behavior follows the
  cloud server's delete-on-termination setting; disks/backups are not a separate
  inventory or cleanup target in this release.
- AWS environments created by this platform: CloudFormation-owned Web, Database
  and Bucket logical resources. Stack LabId/StudentId/ManagedBy tags and physical
  identifiers are checked again before each operation. Existing arbitrary AWS
  databases/buckets and NAVER databases/object storage are not imported here.
- Object Storage/S3 has no start or stop. Only empty, owned containers/buckets
  may be deleted. S3 versions/delete markers are checked; this screen never
  deletes student objects to empty a bucket.

## State and safety

Observation records are separate from generation plans and credentials. Unknown,
lookup failure, missing, and present are distinct. A recorded create intent
without a resource ID remains unknown, not uncreated. Cached observations enable
selection; workers always query actual state and revalidate ownership/identity
before writing. API errors are not interpreted as absence. No raw cloud replies,
operator keys, private keys, passwords or object contents appear in inventory.

Start/stop require an active ADMIN/OPERATOR and a writable connection. Delete
requires ADMIN, Ops password reauthentication and the literal confirmation
`삭제`. The UI explicitly explains DB deletion without a final backup and possible
root disk deletion. Server deletion requires a stopped state. Each request is
journaled before the API call and its acceptance/failure is recorded separately.
Successful API acceptance is not presented as confirmed final cloud state.
NHN deletions tombstone generation journals and disable old provisioning retries;
old credentials are never silently rotated or resources recreated.

All selected connection jobs are inserted in one SQLite transaction, so a busy
connection rejects the entire enqueue instead of partially submitting it. Runtime
cloud failures may still produce partial results; inspect per-resource history.
No batch rollback or automatic mutation retry is attempted.

Confirmed connections automatically query their tracked resource types on the
existing periodic worker schedule. Failed refreshes pause automatic polling until
an explicit successful refresh. UI polling announces refreshed state without
interrupting an in-progress selection/password form. Use Latest State or the
header refresh to load observations. Refresh is always a read-only operation.

## Navigation and layout

A persistent app bar and sidebar surround compact tables. Advanced identifiers
and settings are collapsed. Regions are cloud-specific dropdowns, default DB
specification/version is automatic, and available AWS accounts are selectable.
POST forms carry an allowlisted same-origin fragment return path. Metrics and
error pages return to it. Session storage restores cloud/type/event/search,
expanded details and scroll position; passwords and secrets are never stored.

Deployment updates only the Ops container. Schema additions are additive. Wait
until queued/running Ops jobs finish, back up the existing database, then replace
Ops. Do not restart LMS, PostgreSQL, Caddy or attendance containers.
