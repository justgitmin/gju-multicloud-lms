# LMS attendance evidence without restarting lectures

Apply `install.sql` once with the PostgreSQL owner. It adds a separate evidence table and insert/update triggers; existing User/Session/Playback data is preserved. Login records use database clock time at actual Session insertion. Learning activity records are deduplicated per user and KST minute. Existing logins are not falsely reconstructed as actual events.

Run `compose.attendance.yaml` separately. The service uses a dedicated PostgreSQL SELECT-only role through `ATTENDANCE_DATABASE_URL` in server-only attendance.env (mode 0600). It reads existing Ops sessions through a SQLite mode=ro connection (volume is writable only to support SQLite WAL shared-memory coordination) and requires ADMIN. Caddy routes `/attendance*` to attendance:8781 on the existing Ops hostname. CSV distinguishes actual events from manual attendance, includes registrar, recorded time and notes. No session token, token hash, password or API credential is exported.

Manually registering a past attendance time requires a named operator request and a documented supporting basis. The attributed attendance time must stay separate from actual event and insertion timestamps. Do not mark all enrolled students present automatically.

This table is managed by install.sql. Do not run destructive Prisma db push or remove unknown tables. For upgrades use Prisma migrate deploy. Keep PostgreSQL backups; attendance evidence is included. Database restart, LMS web deployment and Ops worker restart are not required. Rollback disables the triggers; preserve evidence table and exported reports.

Production installation: `python3 ops-platform/attendance/install.py`, then build/start only `docker compose -f compose.attendance.yaml up -d --build attendance`. The installer takes a live backup, preserves its original backfill snapshot on rerun, and creates 17:30 manual records only for saved roster students with same-day valid sessions or learning activity. It never prints viewer credentials.
