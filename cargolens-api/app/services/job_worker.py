import asyncio
import time
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any
from uuid import UUID
from sqlalchemy import select, update, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.models.document import Document, DocumentProcessingStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.extraction import (
    DocumentExtraction,
    DocumentExtractionPage,
    ExtractionStatus,
)
from app.services.ocr.pipeline import OcrPipeline, ExtractionPipelineResult
from app.storage import get_storage_service
from app.config import settings

logger = logging.getLogger("cargolens.worker")


class JobLeaseLostError(Exception):
    """Raised when an attempt is made to renew, complete, or persist a job whose lease was lost or reclaimed."""
    pass


class JobWorkerService:
    """
    PostgreSQL-backed job queue worker service with distributed lease management.
    - Atomically claims pending jobs using SELECT ... FOR UPDATE SKIP LOCKED.
    - Issues time-bounded leases (lease_expires_at + lease_token).
    - Renews leases periodically during long-running OCR execution.
    - Recovers expired leases concurrently without race conditions using row locks.
    - Prevents stale or reclaimed workers from overwriting new results.
    - Keeps long-running OCR execution completely outside database transactions.
    """

    @staticmethod
    async def claim_next_job(
        session: AsyncSession,
        lease_duration_seconds: Optional[int] = None,
    ) -> Optional[ProcessingJob]:
        """
        Atomically claims the next pending job using PostgreSQL SKIP LOCKED.
        Generates a unique lease_token and sets lease_expires_at.
        Immediately commits the PROCESSING status so that no row locks are held
        during downstream file I/O or OCR operations.
        """
        duration = lease_duration_seconds or settings.WORKER_LEASE_SECONDS
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.status == JobStatus.PENDING,
                ProcessingJob.attempt_count < ProcessingJob.max_attempts,
            )
            .order_by(ProcessingJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return None

        lease_token = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Transition job state to PROCESSING with active lease
        job.status = JobStatus.PROCESSING
        job.started_at = now
        job.attempt_count += 1
        job.lease_token = lease_token
        job.lease_expires_at = now + timedelta(seconds=duration)

        # Also update parent document processing status
        doc_stmt = (
            update(Document)
            .where(Document.id == job.document_id)
            .values(processing_status=DocumentProcessingStatus.PROCESSING)
        )
        await session.execute(doc_stmt)

        await session.commit()
        await session.refresh(job)
        return job

    @staticmethod
    async def renew_lease(
        session: AsyncSession,
        job_id: UUID,
        lease_token: UUID,
        lease_duration_seconds: Optional[int] = None,
    ) -> bool:
        """
        Extends the lease for an actively processing job.
        Returns True if renewed, False if the job was reclaimed or token mismatch.
        """
        duration = lease_duration_seconds or settings.WORKER_LEASE_SECONDS
        new_expiry = datetime.now(timezone.utc) + timedelta(seconds=duration)
        stmt = (
            update(ProcessingJob)
            .where(
                ProcessingJob.id == job_id,
                ProcessingJob.lease_token == lease_token,
                ProcessingJob.status == JobStatus.PROCESSING,
            )
            .values(lease_expires_at=new_expiry)
        )
        res = await session.execute(stmt)
        await session.commit()
        return res.rowcount > 0

    @staticmethod
    async def complete_job(
        session: AsyncSession,
        job_id: UUID,
        lease_token: Optional[UUID] = None,
        doc_status: DocumentProcessingStatus = DocumentProcessingStatus.COMPLETED,
    ) -> Optional[ProcessingJob]:
        """
        Marks claimed job as COMPLETED and updates document processing status.
        If lease_token is provided, validates that the lease has not been lost or reclaimed.
        """
        stmt = select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return None

        # Fencing check: verify lease token if provided
        if lease_token is not None:
            if job.status != JobStatus.PROCESSING or job.lease_token != lease_token:
                raise JobLeaseLostError(
                    f"Cannot complete job {job_id}: lease token mismatch or job was already reclaimed."
                )

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.lease_token = None
        job.lease_expires_at = None

        # Update document status
        doc_stmt = (
            update(Document)
            .where(Document.id == job.document_id)
            .values(processing_status=doc_status)
        )
        await session.execute(doc_stmt)

        await session.commit()
        await session.refresh(job)
        return job

    @staticmethod
    async def fail_job(
        session: AsyncSession,
        job_id: UUID,
        error_message: str,
        lease_token: Optional[UUID] = None,
    ) -> Optional[ProcessingJob]:
        """
        Handles job failure. If attempts reach max_attempts, marks FAILED.
        Otherwise requeues as PENDING for future retry.
        If lease_token is provided, ensures only the current leaseholder can record failure.
        """
        stmt = select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return None

        # Fencing check
        if lease_token is not None:
            if job.status != JobStatus.PROCESSING or job.lease_token != lease_token:
                raise JobLeaseLostError(
                    f"Cannot fail job {job_id}: lease token mismatch or job was already reclaimed."
                )

        # Sanitize error message (prevent credential or payload leak)
        safe_error = (error_message or "Unknown processing error")[:1000]
        job.error_message = safe_error
        job.lease_token = None
        job.lease_expires_at = None

        if job.attempt_count >= job.max_attempts:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            doc_stmt = (
                update(Document)
                .where(Document.id == job.document_id)
                .values(processing_status=DocumentProcessingStatus.FAILED)
            )
            await session.execute(doc_stmt)
        else:
            # Requeue for retry
            job.status = JobStatus.PENDING
            doc_stmt = (
                update(Document)
                .where(Document.id == job.document_id)
                .values(processing_status=DocumentProcessingStatus.PENDING)
            )
            await session.execute(doc_stmt)

        await session.commit()
        await session.refresh(job)
        return job

    @staticmethod
    async def persist_extraction(
        session: AsyncSession,
        document_id: UUID,
        result: ExtractionPipelineResult,
        lease_token: Optional[UUID] = None,
    ) -> DocumentExtraction:
        """
        Persists a DocumentExtraction attempt and its associated page-level records.
        Preserves previous extraction attempts by allocating sequential attempt numbers.
        If lease_token is provided, validates that the job lease is still valid before persisting.
        """
        if lease_token is not None:
            job_check_stmt = select(ProcessingJob.id).where(
                ProcessingJob.document_id == document_id,
                ProcessingJob.lease_token == lease_token,
                ProcessingJob.status == JobStatus.PROCESSING,
            )
            check_res = await session.execute(job_check_stmt)
            if not check_res.scalar_one_or_none():
                raise JobLeaseLostError(
                    f"Cannot persist extraction for document {document_id}: job lease lost or reclaimed."
                )

        # Determine next attempt number for this document
        attempt_stmt = select(
            func.coalesce(func.max(DocumentExtraction.attempt_number), 0)
        ).where(DocumentExtraction.document_id == document_id)
        max_attempt_res = await session.execute(attempt_stmt)
        current_max_attempt = max_attempt_res.scalar() or 0
        next_attempt = current_max_attempt + 1

        extraction = DocumentExtraction(
            document_id=document_id,
            attempt_number=next_attempt,
            status=result.status,
            extraction_method=result.extraction_method,
            raw_text=result.raw_text,
            page_count=result.page_count,
            processed_page_count=result.processed_page_count,
            failed_page_count=result.failed_page_count,
            avg_confidence=result.avg_confidence,
            character_count=result.character_count,
            quality_status=result.quality_status,
            error_summary=result.error_summary,
            started_at=result.started_at,
            completed_at=result.completed_at,
        )
        session.add(extraction)
        await session.flush()  # Obtain extraction.id

        # Persist individual page results
        for page_result in result.pages:
            page_row = DocumentExtractionPage(
                extraction_id=extraction.id,
                page_number=page_result.page_number,
                extraction_method=page_result.extraction_method,
                raw_text=page_result.raw_text,
                ocr_confidence=page_result.ocr_confidence,
                character_count=page_result.character_count,
                processing_status=page_result.processing_status,
                error_message=page_result.error_message,
            )
            session.add(page_row)

        await session.flush()
        return extraction

    @classmethod
    async def recover_stale_jobs(
        cls,
        session: AsyncSession,
        stale_timeout_seconds: Optional[int] = None,
    ) -> List[UUID]:
        """
        Recovers jobs stuck in PROCESSING where lease_expires_at has expired.
        Uses SELECT ... FOR UPDATE SKIP LOCKED to ensure multiple concurrent
        recovery workers do not process the same stale jobs.
        If max attempts reached, marks FAILED; otherwise requeues as PENDING.
        """
        now = datetime.now(timezone.utc)
        fallback_timeout = stale_timeout_seconds or settings.STALE_JOB_TIMEOUT_SECONDS
        cutoff = now - timedelta(seconds=fallback_timeout)

        # Condition: lease_expires_at expired, or legacy null lease past cutoff
        condition = or_(
            and_(ProcessingJob.lease_expires_at.is_not(None), ProcessingJob.lease_expires_at <= now),
            and_(ProcessingJob.lease_expires_at.is_(None), ProcessingJob.started_at <= cutoff),
        )

        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.status == JobStatus.PROCESSING,
                condition,
            )
            .with_for_update(skip_locked=True)
        )
        res = await session.execute(stmt)
        stale_jobs = res.scalars().all()

        recovered_ids: List[UUID] = []
        for job in stale_jobs:
            job.lease_token = None
            job.lease_expires_at = None

            if job.attempt_count >= job.max_attempts:
                job.status = JobStatus.FAILED
                job.completed_at = now
                job.error_message = (
                    f"Job lease expired in PROCESSING state (worker crash or timeout)."
                )
                await session.execute(
                    update(Document)
                    .where(Document.id == job.document_id)
                    .values(processing_status=DocumentProcessingStatus.FAILED)
                )
            else:
                job.status = JobStatus.PENDING
                job.error_message = "Job lease expired. Requeued for retry."
                await session.execute(
                    update(Document)
                    .where(Document.id == job.document_id)
                    .values(processing_status=DocumentProcessingStatus.PENDING)
                )
            recovered_ids.append(job.id)

        if recovered_ids:
            await session.commit()
            logger.info(f"Recovered {len(recovered_ids)} stale processing jobs: {recovered_ids}")

        return recovered_ids

    @classmethod
    async def process_single_job(
        cls,
        session: AsyncSession,
        ocr_pipeline: Optional[OcrPipeline] = None,
        structured_service: Optional[Any] = None,
        renew_interval_seconds: Optional[float] = None,
    ) -> Optional[ProcessingJob]:
        """
        Claims and executes one job lifecycle end-to-end:
        1. Atomically claims job via SKIP LOCKED, acquires lease, and commits PROCESSING status.
        2. Starts background lease renewal heartbeat while processing.
        3. Executes OCR pipeline or AI structured extraction without holding database locks.
        4. Validates lease fencing before persisting extractions.
        5. Completes job and updates document processing status.
        6. Handles worker lease loss, errors, and retries cleanly.
        """
        job = await cls.claim_next_job(session)
        if not job:
            return None

        lease_token = job.lease_token
        job_id = job.id
        pipeline = ocr_pipeline or OcrPipeline()

        # Background lease renewer heartbeat
        renew_interval = renew_interval_seconds or settings.WORKER_LEASE_RENEW_INTERVAL_SECONDS
        renew_stop_event = asyncio.Event()

        async def _lease_heartbeat():
            while not renew_stop_event.is_set():
                try:
                    await asyncio.wait_for(renew_stop_event.wait(), timeout=renew_interval)
                except asyncio.TimeoutError:
                    try:
                        async with AsyncSessionFactory() as s:
                            renewed = await JobWorkerService.renew_lease(s, job_id, lease_token)
                            if not renewed:
                                logger.warning(
                                    f"Failed to renew lease for job {job_id} (token {lease_token}). "
                                    f"Lease was reclaimed or lost."
                                )
                                break
                    except Exception as renew_err:
                        logger.warning(f"Error during lease renewal heartbeat for job {job_id}: {renew_err}")

        heartbeat_task = asyncio.create_task(_lease_heartbeat())

        try:
            # 1. Fetch document metadata
            doc_res = await session.execute(
                select(Document).where(Document.id == job.document_id)
            )
            doc = doc_res.scalar_one_or_none()
            if not doc:
                raise ValueError(f"Referenced document {job.document_id} does not exist.")

            if job.job_type == "STRUCTURED_EXTRACTION":
                from app.services.ai.service import StructuredExtractionService
                ai_service = structured_service or StructuredExtractionService()
                structured_rec = await ai_service.execute_extraction(session, doc)
                doc_status = (
                    DocumentProcessingStatus.FAILED
                    if structured_rec.status == ExtractionStatus.FAILED
                    else DocumentProcessingStatus.COMPLETED
                )
                return await cls.complete_job(
                    session, job_id, lease_token=lease_token, doc_status=doc_status
                )

            # 2. Read file bytes from storage service
            storage = get_storage_service()
            chunks = []
            async for chunk in storage.get_file_stream(doc.storage_key):
                chunks.append(chunk)
            file_bytes = b"".join(chunks)

            # 3. Execute OCR Pipeline (runs in-memory, no DB locks held)
            extraction_result = await pipeline.process_document(
                file_bytes=file_bytes,
                file_extension=doc.file_extension,
                document_id=doc.id,
            )

        except Exception as e:
            logger.error(f"Job {job_id} processing failed: {e}", exc_info=True)
            try:
                return await cls.fail_job(session, job_id, str(e), lease_token=lease_token)
            except JobLeaseLostError:
                logger.warning(f"Job {job_id} lease was lost while handling failure.")
                return None
        finally:
            renew_stop_event.set()
            try:
                await heartbeat_task
            except Exception:
                pass

        # 4. Persist extraction and complete job with lease fencing check
        try:
            await cls.persist_extraction(
                session, doc.id, extraction_result, lease_token=lease_token
            )

            # 5. Determine document final status
            doc_status = (
                DocumentProcessingStatus.FAILED
                if extraction_result.status == ExtractionStatus.FAILED
                else DocumentProcessingStatus.COMPLETED
            )

            # 6. Complete job
            return await cls.complete_job(
                session, job_id, lease_token=lease_token, doc_status=doc_status
            )
        except JobLeaseLostError as lease_lost:
            logger.warning(
                f"Aborting completion for job {job_id}: {lease_lost}. "
                f"Job was reclaimed by another worker or lease expired. Results discarded."
            )
            await session.rollback()
            return None


async def run_worker_loop(
    stop_event: asyncio.Event,
    poll_interval: float = 2.0,
    stale_check_interval: float = 60.0,
):
    """
    Dedicated background worker loop.
    Claims pending jobs, runs stale job recovery periodically,
    and terminates gracefully when stop_event is set.
    """
    logger.info("Starting CargoLens background job worker loop...")
    last_stale_check = time.monotonic()

    while not stop_event.is_set():
        try:
            # Periodically recover stale jobs
            now = time.monotonic()
            if now - last_stale_check >= stale_check_interval:
                async with AsyncSessionFactory() as session:
                    await JobWorkerService.recover_stale_jobs(session)
                last_stale_check = now

            # Process single pending job
            async with AsyncSessionFactory() as session:
                job = await JobWorkerService.process_single_job(session)
                if not job:
                    await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker exception: {e}", exc_info=True)
            await asyncio.sleep(poll_interval)

    logger.info("CargoLens background job worker loop stopped.")
