import asyncio
from celery import Celery
from datetime import time as Time
from celery.schedules import crontab
from celery.beat import Scheduler
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.config.settings import settings
from app.core.database import db_manager, redis_manager
from app.models.bot_worker import BotWorker
from app.models.bot import Bot
from app.models.visitor import Visitor
from app.models.user import User, UserRole
from app.common.enums import ScheduleType, Frequency, NotificationType
from app.services.visitor import VisitorService
from app.services.bot import BotService
from app.services.notification import NotificationService
from app.utils.email_queue import queue_email
from app.utils.datetime_utils import now
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ============================================================================
# CELERY APP
# ============================================================================

celery_app = Celery(
    "bot_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_time_limit=3600,
    task_acks_late=True,
    result_expires=3600,
    beat_max_loop_interval=60,
)

# ============================================================================
# WORKER FUNCTIONS
# ============================================================================

async def execute_crawl_worker(worker: BotWorker, db: AsyncSession, redis: Redis):
    """Execute crawl worker - trigger origin recrawl"""
    try:
        bot_service = BotService(db, redis)
        result = await bot_service.recrawl_origin(str(worker.bot_id))
        
        logger.info(f"Crawl worker: bot {worker.bot_id}, job_id={result.get('job_id')}")
    except Exception as e:
        logger.error(f"Failed to execute crawl worker for bot {worker.bot_id}: {e}", exc_info=True)
        raise

async def execute_grading_worker(worker: BotWorker, db: AsyncSession):
    """Execute grading worker - batch assess visitors"""
    try:
        result = await db.execute(
            select(Visitor).where(
                Visitor.bot_id == worker.bot_id,
                Visitor.assessed_at.is_(None),
                Visitor.is_new == False,
                or_(Visitor.email.isnot(None), Visitor.phone.isnot(None))
            ).limit(50)
        )
        visitors = result.scalars().all()
        
        if not visitors:
            logger.info(f"No visitors to assess for bot {worker.bot_id}")
            return
        
        visitor_service = VisitorService(db)

        for visitor in visitors:
            try:
                latest_session = await visitor_service.get_latest_session_for_visitor(str(visitor.id))
                
                if latest_session:
                    await visitor_service.trigger_visitor_assessment(
                        visitor_id=str(visitor.id),
                        bot_id=str(visitor.bot_id),
                        session_id=str(latest_session.id),
                        force=False
                    )
                    logger.info(f"Triggered assessment for visitor {visitor.id}")
            except Exception as e:
                logger.error(f"Failed to assess visitor {visitor.id}: {e}")
        
        logger.info(f"Grading worker: bot {worker.bot_id}, processed {len(visitors)} visitors")
        
    except Exception as e:
        logger.error(f"Failed to execute grading worker for bot {worker.bot_id}: {e}", exc_info=True)
        raise

async def execute_visitor_email_worker(worker: BotWorker, db: AsyncSession, redis: Redis):
    """Execute visitor email worker - send notifications for high-score visitors"""
    try:
        min_score = settings.VISITOR_HIGH_SCORE_THRESHOLD 
        result = await db.execute(
            select(Visitor).where(
                Visitor.bot_id == worker.bot_id,
                Visitor.lead_score >= min_score,
                Visitor.is_new == True,
                Visitor.assessed_at.is_not(None)
            )
        )
        visitors = result.scalars().all()
        
        if not visitors:
            logger.info(f"No high-score visitors for bot {worker.bot_id}")
            return
        
        bot_result = await db.execute(select(Bot).where(Bot.id == worker.bot_id))
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            logger.error(f"Bot {worker.bot_id} not found")
            return
        
        visitor_data = [
            {
                "name": v.name or "Unknown",
                "email": v.email or "N/A",
                "phone": v.phone or "N/A",
                "lead_score": v.lead_score,
                "assessed_at": v.assessed_at.isoformat() if v.assessed_at else None,
                "assessed_at_formatted": v.assessed_at.strftime("%d/%m/%Y %H:%M") if v.assessed_at else None
            }
            for v in visitors
        ]
        
        admin_result = await db.execute(
            select(User).where(
                User.role == UserRole.ADMIN,
                User.is_active == True,
                User.is_deleted == False
            )
        )
        admins = admin_result.scalars().all()
        
        if not admins:
            logger.warning("No admin users found")
        else:
            notification_service = NotificationService(db, redis)
            
            for admin in admins:
                await notification_service.create_notification(
                    user_id=str(admin.id),
                    title=f"High Score Visitors - {bot.name}",
                    message=f"Found {len(visitors)} high-score visitors (≥{min_score} points)",
                    notification_type=NotificationType.LEAD_SCORED,
                    extra_data={
                        "bot_id": str(worker.bot_id),
                        "bot_name": bot.name,
                        "visitor_count": len(visitors),
                        "threshold": min_score,
                        "visitors": visitor_data[:5]
                    }
                )
            
            logger.info(f"Created notifications for {len(admins)} admins")
            
            for admin in admins:
                try:
                    await queue_email(
                        template_name="high_score_visitors.html",
                        recipient_email=admin.email,
                        subject=f"{len(visitors)} Khách hàng Tiềm năng Mới - {bot.name}",
                        context={
                            "bot_name": bot.name,
                            "total_count": len(visitors),
                            "threshold": min_score,
                            "visitors": visitor_data,
                            "frontend_url": settings.FRONTEND_URL 
                        },
                        priority=8
                    )
                except Exception as email_error:
                    logger.error(f"Failed to queue email for {admin.email}: {email_error}")
            
            logger.info(f"Queued {len(admins)} emails for high-score visitors")
        
        logger.info(f"Email worker: bot {worker.bot_id}, notified {len(visitors)} visitors")
        
    except Exception as e:
        logger.error(f"Failed to execute email worker for bot {worker.bot_id}: {e}", exc_info=True)
        raise

# ============================================================================
# CELERY TASKS
# ============================================================================

@celery_app.task(name="bot_worker.crawl", bind=True)
def crawl_worker_task(self, worker_id: str):
    """Celery task for crawl worker"""
    async def run():
        db_manager.engine = None
        db_manager.session_factory = None
        redis_manager.redis = None
        redis_manager.pool = None
        
        await db_manager.connect()
        await redis_manager.connect()
        
        async with db_manager.session() as db:
            redis = redis_manager.get_redis()
            result = await db.execute(
                select(BotWorker).where(BotWorker.id == worker_id)
            )
            worker = result.scalar_one_or_none()
            
            if not worker or not worker.auto:
                logger.warning(f"Worker {worker_id} not found or not active")
                return
            
            await execute_crawl_worker(worker, db, redis)
    
    asyncio.run(run())
    return {"status": "completed", "worker_id": worker_id}

@celery_app.task(name="bot_worker.grading", bind=True)
def grading_worker_task(self, worker_id: str):
    """Celery task for grading worker"""
    async def run():
        db_manager.engine = None
        db_manager.session_factory = None
        redis_manager.redis = None
        redis_manager.pool = None
        
        await db_manager.connect()
        await redis_manager.connect()
        
        async with db_manager.session() as db:
            result = await db.execute(
                select(BotWorker).where(BotWorker.id == worker_id)
            )
            worker = result.scalar_one_or_none()
            
            if not worker or not worker.auto:
                logger.warning(f"Worker {worker_id} not found or not active")
                return
            
            await execute_grading_worker(worker, db)
    
    asyncio.run(run())
    return {"status": "completed", "worker_id": worker_id}

@celery_app.task(name="bot_worker.visitor_email", bind=True)
def visitor_email_worker_task(self, worker_id: str):
    """Celery task for visitor email worker"""
    async def run():
        db_manager.engine = None
        db_manager.session_factory = None
        redis_manager.redis = None
        redis_manager.pool = None
        
        await db_manager.connect()
        await redis_manager.connect()
        
        async with db_manager.session() as db:
            redis = redis_manager.get_redis()
            result = await db.execute(
                select(BotWorker).where(BotWorker.id == worker_id)
            )
            worker = result.scalar_one_or_none()
            
            if not worker or not worker.auto:
                logger.warning(f"Worker {worker_id} not found or not active")
                return
            
            await execute_visitor_email_worker(worker, db, redis)
    
    asyncio.run(run())
    return {"status": "completed", "worker_id": worker_id}

# ============================================================================
# DYNAMIC SCHEDULER
# ============================================================================

def frequency_to_crontab(frequency: Frequency, schedule_time: Time) -> crontab:
    """Convert frequency and time to Celery crontab"""
    hour = schedule_time.hour
    minute = schedule_time.minute
    
    if frequency == Frequency.DAILY:
        return crontab(hour=hour, minute=minute)
    elif frequency == Frequency.WEEKLY:
        return crontab(hour=hour, minute=minute, day_of_week=1)
    elif frequency == Frequency.MONTHLY:
        return crontab(hour=hour, minute=minute, day_of_month=1)
    elif frequency == Frequency.YEARLY:
        return crontab(hour=hour, minute=minute, day_of_month=1, month_of_year=1)
    else:
        return crontab(hour=hour, minute=minute)

class DatabaseScheduler(Scheduler):
    """Celery Beat scheduler đọc schedule từ database"""
    
    def __init__(self, *args, **kwargs):
        import asyncio
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        if not db_manager.engine:
            self.loop.run_until_complete(db_manager.connect())
            logger.info("DatabaseScheduler: Database connection initialized")
        
        super().__init__(*args, **kwargs)
        self.last_sync = None
        self.sync_interval = 60
        
    def sync_schedule_from_db(self):
        """Sync schedule từ database"""
        async def _sync():
            async with db_manager.session() as db:
                result = await db.execute(
                    select(BotWorker).where(BotWorker.auto == True)
                )
                workers = result.scalars().all()
                
                new_schedule = {}
                
                for worker in workers:
                    task_name = None
                    
                    if worker.schedule_type == ScheduleType.CRAWL:
                        task_name = "bot_worker.crawl"
                    elif worker.schedule_type == ScheduleType.GRADING:
                        task_name = "bot_worker.grading"
                    elif worker.schedule_type == ScheduleType.VISITOR_EMAIL:
                        task_name = "bot_worker.visitor_email"
                    
                    if task_name:
                        schedule_key = f"worker_{worker.id}"
                        new_schedule[schedule_key] = {
                            "task": task_name,
                            "schedule": frequency_to_crontab(worker.frequency, worker.schedule_time),
                            "args": (str(worker.id),),
                            "options": {"expires": 3600}
                        }
                
                return new_schedule
        
        try:
            new_schedule = self.loop.run_until_complete(_sync())
            
            for key in list(self.schedule.keys()):
                if key and isinstance(key, str) and key.startswith("worker_"):
                    del self.schedule[key]
            
            for key, value in new_schedule.items():
                self.schedule[key] = self.Entry(**value, app=self.app)
            
            logger.info(f"Synced {len(new_schedule)} workers to schedule")
            self.last_sync = now()
            
        except Exception as e:
            logger.error(f"Failed to sync schedule: {e}", exc_info=True)
    
    def tick(self, *args, **kwargs):
        """Override tick để sync từ DB"""
        if (self.last_sync is None or 
            (now() - self.last_sync).total_seconds() >= self.sync_interval):
            logger.info("Syncing schedule from DB...")
            self.sync_schedule_from_db()
        
        return super().tick(*args, **kwargs)

# ============================================================================
# MANUAL RUN (deprecated)
# ============================================================================

if __name__ == "__main__":
    logger.warning("  celery -A app.workers.bot_worker_scheduler worker --loglevel=info")
    logger.warning("  celery -A app.workers.bot_worker_scheduler beat --loglevel=info")
