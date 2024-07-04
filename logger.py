import logging
import os

logger: logging.Logger


class ConsoleHandler(logging.StreamHandler):
    # https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    BLUE = "34"
    GRAY7 = "38;5;7"
    ORANGE = "33"
    RED = "31"
    DARK_RED_BOLD = "1;38;5;124"
    WHITE = "0"

    def emit(self, record):
        # Don't use white for any logging, to help distinguish from user print statements
        level_color_map = {
            logging.DEBUG: self.BLUE,
            logging.INFO: self.GRAY7,
            logging.WARNING: self.ORANGE,
            logging.ERROR: self.RED,
            logging.CRITICAL: self.DARK_RED_BOLD
        }

        csi = f"{chr(27)}["  # control sequence introducer
        color = level_color_map.get(record.levelno, self.WHITE)

        print(f"{csi}{color}m{record.msg}{csi}m")


def create_logger() -> logging.Logger:
    new_logger = logging.getLogger('main_logger')

    logging_level_str = os.getenv('LOGGING_LEVEL', 'INFO')
    logging_level = logging.getLevelNamesMapping().get(logging_level_str.upper())
    console_logging_level_str = os.getenv('CONSOLE_LOGGING_LEVEL', logging_level_str)
    console_logging_level = logging.getLevelNamesMapping().get(console_logging_level_str.upper())

    new_logger.setLevel(logging_level)

    # Create handlers
    console_handler: logging.StreamHandler = ConsoleHandler()
    file_handler: logging.FileHandler = logging.FileHandler(os.getenv('LOG_FILE', 'app.log'))

    # Set level for handlers
    console_handler.setLevel(console_logging_level)
    file_handler.setLevel(logging_level)

    # Create formatters and add them to handlers
    default_format_string: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter: logging.Formatter = logging.Formatter(default_format_string)

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to the logger
    new_logger.addHandler(console_handler)
    new_logger.addHandler(file_handler)

    return new_logger


def init_logger() -> None:
    global logger
    logger = create_logger()
