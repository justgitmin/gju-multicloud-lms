# Student accounts and mypage

- `/mypage`: own email and student number (read only), editable name, own enrollment/learning status, password-change link. Email/number changes require operator contact because they identify the lab recipient.
- `/mypage/password`: verify current password, new 12–128 character password and confirmation. On success all sessions are revoked; log in again. Registration credentials and AWS credentials are separate.
- `/forgot-password`: operator-assisted recovery instructions, no implied email delivery.
- `/admin/users`: search students by name/email/number, including users without enrollments. Administrator reauthentication and target confirmation precede issuing a random temporary password, valid for 24 hours. The response is no-store and the secret is only retained in the active browser component. Only students can be reset. Close the result after privately handing it to the verified student.

A temporary login is redirected to password change. Generic protected pages and direct API guards deny temporary sessions. Changing/resetting a password advances a credential version; stale concurrent sessions cannot be reused. Password hashes, flags and session revocation are transactional. Audit rows record actor, target, event and time; never temporary passwords or admin passwords. Reset does not change enrollment, learning progress or cloud assignments.

## Deploy on the LMS server

Back up the existing PostgreSQL database with `bash scripts/backup.sh` before the migration. Pull main, build web and tools, run the migration through tools, recreate web. The migration adds fields with defaults for existing users/sessions plus the account audit table. Existing accounts do not require a password change until an operator resets them. Do not use `prisma db push` or reset the database.

## Validation

Account auth unit tests cover credential-version mismatch, forced-change guards and expiration. Dedicated PostgreSQL HTTP integration covers own-profile access, role/origin/reauth restrictions, temporary reset/login/expiration/reissue/change, session revocation, assignment preservation and audit events. Run `npm run test:account-integration` only against a dedicated test DB with `LMS_INTEGRATION_TEST=true` after migration and build.
