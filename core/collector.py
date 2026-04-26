import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Channel, Vacancy, VacancyStatus

logger = logging.getLogger(__name__)

class TelegramCollector:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.base_url = "https://t.me/s/"
        self.client = httpx.AsyncClient(timeout=15.0)
        self.batch_size = 50
        self.max_backfill_days = 14

    async def _fetch_page(self, url: str) -> str:
        # Sleep to avoid 429 Too Many Requests
        await asyncio.sleep(random.uniform(1.0, 3.0))
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limited on {url}. Waiting 10s...")
                await asyncio.sleep(10)
                return await self._fetch_page(url)
            logger.error(f"HTTP error for {url}: {e}")
            return ""
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return ""

    def _parse_html(self, html: str, channel_username: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        posts = soup.find_all('div', class_='tgme_widget_message')
        parsed_data = []

        for post in posts:
            try:
                # Get message_id
                data_post = post.get('data-post', '')
                if not data_post:
                    continue
                # Format is "username/message_id"
                message_id = int(data_post.split('/')[-1])

                # Get text
                text_div = post.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue
                raw_text = text_div.get_text(separator='\n', strip=True)

                # Get date
                time_wrap = post.find('time', class_='time')
                posted_at = datetime.utcnow()
                if time_wrap and time_wrap.has_attr('datetime'):
                    # 2024-03-10T15:20:00+00:00 -> remove timezone info for naive datetime if needed
                    dt_str = time_wrap['datetime']
                    dt_obj = datetime.fromisoformat(dt_str)
                    posted_at = dt_obj.astimezone(timezone.utc).replace(tzinfo=None)

                post_url = f"https://t.me/{channel_username}/{message_id}"

                parsed_data.append({
                    "message_id": message_id,
                    "raw_text": raw_text,
                    "posted_at": posted_at,
                    "post_url": post_url
                })
            except Exception as e:
                logger.error(f"Error parsing post in {channel_username}: {e}")
                continue

        return parsed_data

    async def collect_incremental(self, channel: Channel) -> int:
        """Fetch only new messages since last_collected_message_id"""
        logger.info(f"Starting incremental collect for {channel.username}")
        url = f"{self.base_url}{channel.username}"
        html = await self._fetch_page(url)
        if not html:
            return 0

        posts = self._parse_html(html, channel.username)
        new_posts_count = 0

        max_msg_id = channel.last_collected_message_id or 0

        for p in posts:
            if p['message_id'] <= (channel.last_collected_message_id or 0):
                continue

            max_msg_id = max(max_msg_id, p['message_id'])

            # Check for duplication (post_url unique constraint)
            existing = await self.session.execute(
                select(Vacancy).where(Vacancy.post_url == p['post_url'])
            )
            if existing.scalar_one_or_none():
                continue

            vacancy = Vacancy(
                channel_id=channel.id,
                message_id=p['message_id'],
                post_url=p['post_url'],
                raw_text=p['raw_text'],
                posted_at=p['posted_at'],
                status=VacancyStatus.raw
            )
            self.session.add(vacancy)
            new_posts_count += 1

        if max_msg_id > (channel.last_collected_message_id or 0):
            channel.last_collected_message_id = max_msg_id
        
        await self.session.commit()
        return new_posts_count

    async def collect_backfill(self, channel: Channel) -> int:
        """Fetch history backwards for up to 14 days"""
        logger.info(f"Starting backfill for {channel.username}")
        limit_date = datetime.utcnow() - timedelta(days=self.max_backfill_days)
        new_posts_count = 0
        
        # Start from the current latest page to find initial before_id if not set
        url = f"{self.base_url}{channel.username}"
        html = await self._fetch_page(url)
        if not html:
            return 0
            
        posts = self._parse_html(html, channel.username)
        if not posts:
            channel.backfill_completed = True
            await self.session.commit()
            return 0
            
        # Get the oldest message id from this page
        current_before_id = min([p['message_id'] for p in posts])
        
        # We also need to process the initial page
        for p in posts:
            if p['posted_at'] < limit_date:
                channel.backfill_completed = True
                break
                
            existing = await self.session.execute(select(Vacancy).where(Vacancy.post_url == p['post_url']))
            if existing.scalar_one_or_none():
                continue
                
            self.session.add(Vacancy(
                channel_id=channel.id, message_id=p['message_id'],
                post_url=p['post_url'], raw_text=p['raw_text'],
                posted_at=p['posted_at'], status=VacancyStatus.raw
            ))
            new_posts_count += 1
            
        if channel.last_collected_message_id is None:
             channel.last_collected_message_id = max([p['message_id'] for p in posts])
        await self.session.commit()

        # Iterate backwards
        while not channel.backfill_completed:
            url = f"{self.base_url}{channel.username}?before={current_before_id}"
            html = await self._fetch_page(url)
            if not html:
                break
                
            posts = self._parse_html(html, channel.username)
            if not posts:
                channel.backfill_completed = True
                break
                
            batch_oldest_date = max([p['posted_at'] for p in posts]) # initialize with max to avoid unbound
            
            for p in posts:
                batch_oldest_date = min(batch_oldest_date, p['posted_at'])
                if p['posted_at'] < limit_date:
                    channel.backfill_completed = True
                    break
                    
                existing = await self.session.execute(select(Vacancy).where(Vacancy.post_url == p['post_url']))
                if existing.scalar_one_or_none():
                    continue
                    
                self.session.add(Vacancy(
                    channel_id=channel.id, message_id=p['message_id'],
                    post_url=p['post_url'], raw_text=p['raw_text'],
                    posted_at=p['posted_at'], status=VacancyStatus.raw
                ))
                new_posts_count += 1
                
            current_before_id = min([p['message_id'] for p in posts])
            await self.session.commit()
            
            if batch_oldest_date < limit_date:
                channel.backfill_completed = True
                await self.session.commit()
                break

        return new_posts_count

    async def run(self):
        async with self.session.begin():
            channels = await self.session.execute(select(Channel).where(Channel.is_active == True))
            active_channels = channels.scalars().all()
            
        total_new = 0
        for ch in active_channels:
            if not ch.backfill_completed:
                total_new += await self.collect_backfill(ch)
            else:
                total_new += await self.collect_incremental(ch)
                
        await self.client.aclose()
        return total_new
