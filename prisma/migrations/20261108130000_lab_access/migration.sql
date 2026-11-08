CREATE TABLE "LabAccess" (
 "id" TEXT NOT NULL,
 "enrollmentId" TEXT NOT NULL,
 "labId" TEXT NOT NULL,
 "studentCode" TEXT NOT NULL,
 "accountId" TEXT NOT NULL,
 "publicData" JSONB NOT NULL,
 "secretData" TEXT NOT NULL,
 "active" BOOLEAN NOT NULL DEFAULT true,
 "updatedAt" TIMESTAMP(3) NOT NULL,
 CONSTRAINT "LabAccess_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "LabAccess_enrollmentId_key" ON "LabAccess"("enrollmentId");
CREATE UNIQUE INDEX "LabAccess_accountId_labId_studentCode_key" ON "LabAccess"("accountId","labId","studentCode");
ALTER TABLE "LabAccess" ADD CONSTRAINT "LabAccess_enrollmentId_fkey" FOREIGN KEY ("enrollmentId") REFERENCES "Enrollment"("id") ON DELETE CASCADE ON UPDATE CASCADE;
CREATE TABLE "LabTransferToken" (
 "id" TEXT NOT NULL,
 "tokenHash" TEXT NOT NULL,
 "adminId" TEXT NOT NULL,
 "expiresAt" TIMESTAMP(3) NOT NULL,
 "consumedAt" TIMESTAMP(3),
 CONSTRAINT "LabTransferToken_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "LabTransferToken_tokenHash_key" ON "LabTransferToken"("tokenHash");
CREATE INDEX "LabTransferToken_expiresAt_idx" ON "LabTransferToken"("expiresAt");
CREATE TABLE "LabAccessAudit" (
 "id" TEXT NOT NULL,
 "actorId" TEXT NOT NULL,
 "event" TEXT NOT NULL,
 "assignmentId" TEXT,
 "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT "LabAccessAudit_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "LabAccessAudit_createdAt_idx" ON "LabAccessAudit"("createdAt");
