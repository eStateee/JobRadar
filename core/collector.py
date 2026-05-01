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

# Заголовки, имитирующие реальный браузер (обход заглушки Telegram)
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}

# Максимальное количество повторных попыток при 429 Too Many Requests
_MAX_RETRY_429 = 3


class TelegramCollector:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.base_url = "https://t.me/s/"
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers=_BROWSER_HEADERS,
            follow_redirects=True,
        )
        self.batch_size = 50
        self.max_backfill_days = 14

    async def _fetch_page(self, url: str, _retry: int = 0) -> str:
        """Загрузка страницы с задержкой и ограниченным retry при 429."""
        await asyncio.sleep(random.uniform(1.0, 3.0))
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and _retry < _MAX_RETRY_429:
                wait = 10 * (_retry + 1)
                logger.warning(f"Rate limited on {url}. Waiting {wait}s (attempt {_retry + 1}/{_MAX_RETRY_429})...")
                await asyncio.sleep(wait)
                return await self._fetch_page(url, _retry=_retry + 1)
            logger.error(f"HTTP error for {url}: {e}")
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise

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
        """Сбор истории канала за последние max_backfill_days дней.

        Посты на странице t.me/s/ идут сверху вниз (от старых к новым),
        поэтому итерируем reversed(posts) — от новых к старым.
        Это гарантирует, что break сработает только когда все свежие
        посты уже обработаны.
        """
        logger.info(f"Starting backfill for {channel.username}")
        limit_date = datetime.utcnow() - timedelta(days=self.max_backfill_days)
        new_posts_count = 0

        # --- Первая страница (самая свежая) ---
        url = f"{self.base_url}{channel.username}"
        html = await self._fetch_page(url)
        if not html:
            return 0

        posts = self._parse_html(html, channel.username)
        if not posts:
            logger.warning(f"No posts found for {channel.username} — возможно, Telegram вернул заглушку")
            channel.backfill_completed = True
            await self.session.commit()
            return 0

        logger.info(f"{channel.username}: parsed {len(posts)} posts from first page")

        # Устанавливаем last_collected_message_id ДО цикла,
        # чтобы break не помешал обновлению
        page_max_id = max(p['message_id'] for p in posts)
        if channel.last_collected_message_id is None or page_max_id > channel.last_collected_message_id:
            channel.last_collected_message_id = page_max_id

        current_before_id = min(p['message_id'] for p in posts)

        # Обходим от новых к старым
        for p in reversed(posts):
            if p['posted_at'] < limit_date:
                channel.backfill_completed = True
                break

            existing = await self.session.execute(
                select(Vacancy).where(Vacancy.post_url == p['post_url'])
            )
            if existing.scalar_one_or_none():
                continue

            self.session.add(Vacancy(
                channel_id=channel.id, message_id=p['message_id'],
                post_url=p['post_url'], raw_text=p['raw_text'],
                posted_at=p['posted_at'], status=VacancyStatus.raw,
            ))
            new_posts_count += 1

        await self.session.commit()

        # --- Пагинация назад ---
        while not channel.backfill_completed:
            url = f"{self.base_url}{channel.username}?before={current_before_id}"
            html = await self._fetch_page(url)
            if not html:
                break

            posts = self._parse_html(html, channel.username)
            if not posts:
                channel.backfill_completed = True
                break

            logger.info(
                f"{channel.username}: parsed {len(posts)} posts (before={current_before_id})"
            )

            # Обходим от новых к старым
            for p in reversed(posts):
                if p['posted_at'] < limit_date:
                    channel.backfill_completed = True
                    break

                existing = await self.session.execute(
                    select(Vacancy).where(Vacancy.post_url == p['post_url'])
                )
                if existing.scalar_one_or_none():
                    continue

                self.session.add(Vacancy(
                    channel_id=channel.id, message_id=p['message_id'],
                    post_url=p['post_url'], raw_text=p['raw_text'],
                    posted_at=p['posted_at'], status=VacancyStatus.raw,
                ))
                new_posts_count += 1

            current_before_id = min(p['message_id'] for p in posts)
            await self.session.commit()

        logger.info(f"{channel.username}: backfill done, collected {new_posts_count} posts")
        await self.session.commit()
        return new_posts_count

    async def run(self):
        """Запуск сбора: backfill для новых каналов, incremental для остальных."""
        result = await self.session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        active_channels = result.scalars().all()

        if not active_channels:
            logger.warning("No active channels found")
            return 0

        total_new = 0
        for ch in active_channels:
            try:
                if not ch.backfill_completed:
                    total_new += await self.collect_backfill(ch)
                else:
                    total_new += await self.collect_incremental(ch)
            except Exception as e:
                logger.error(f"Error collecting {ch.username}: {e}")
                continue

        await self.client.aclose()
        logger.info(f"Collection finished: {total_new} new posts from {len(active_channels)} channels")
        return total_new
