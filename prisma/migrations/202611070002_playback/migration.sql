CREATE TABLE "Playback" (
 "id" TEXT NOT NULL,
 "enrollmentId" TEXT NOT NULL,
 "lessonId" TEXT NOT NULL,
 "version" INTEGER NOT NULL,
 "lastPosition" DOUBLE PRECISION NOT NULL,
 "lastAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
 "revision" INTEGER NOT NULL DEFAULT 0,
 CONSTRAINT "Playback_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "Playback_enrollmentId_lessonId_key" ON "Playback"("enrollmentId", "lessonId");
