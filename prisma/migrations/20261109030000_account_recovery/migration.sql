ALTER TABLE "User" ADD COLUMN "passwordVersion" INTEGER NOT NULL DEFAULT 0,
 ADD COLUMN "mustChangePassword" BOOLEAN NOT NULL DEFAULT false,
 ADD COLUMN "temporaryPasswordExpiresAt" TIMESTAMP(3);
ALTER TABLE "Session" ADD COLUMN "passwordVersion" INTEGER NOT NULL DEFAULT 0;
CREATE TABLE "AccountAudit" (
 "id" TEXT NOT NULL,
 "actorId" TEXT NOT NULL,
 "targetUserId" TEXT NOT NULL,
 "event" TEXT NOT NULL,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "AccountAudit_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "AccountAudit_targetUserId_createdAt_idx" ON "AccountAudit"("targetUserId", "createdAt");
