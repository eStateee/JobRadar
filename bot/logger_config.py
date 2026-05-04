import logging
import sys
from bot.config import config

class SecretsFilter(logging.Filter):
    """Фильтр для маскировки чувствительных данных в логах."""
    def __init__(self):
        super().__init__()
        self.secrets = []
        if config.bot_token:
            self.secrets.append(config.bot_token)
        if config.llm_api_key:
            self.secrets.append(config.llm_api_key)

    def _mask(self, obj):
        """Рекурсивно (поверхностно) маскирует секреты в объекте."""
        if isinstance(obj, str):
            for secret in self.secrets:
                if secret and secret in obj:
                    obj = obj.replace(secret, "***")
            return obj
        elif isinstance(obj, dict):
            return {k: self._mask(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return type(obj)(self._mask(i) for i in obj)
        return obj

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.secrets:
            return True
            
        # Маскируем секреты в самом сообщении
        record.msg = self._mask(record.msg)
                    
        # Маскируем в аргументах, если они есть
        if record.args:
            # record.args может быть либо кортежем (позиционные), либо словарем (именованные)
            if isinstance(record.args, dict):
                record.args = self._mask(record.args)
            else:
                # Сохраняем структуру кортежа
                record.args = tuple(self._mask(arg) for arg in record.args)
            
        return True

def setup_logging():
    """Инициализация и настройка системы логгирования."""
    # Базовый формат
    log_format = "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # 1. StreamHandler (Консоль) - INFO
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(SecretsFilter())

    # 2. FileHandler (debug.log) - DEBUG
    file_handler = logging.FileHandler("debug.log", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretsFilter())

    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Очищаем старые хендлеры, если они были
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # Подавление избыточных логов сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
