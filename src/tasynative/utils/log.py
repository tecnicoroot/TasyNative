import logging
import os
from datetime import datetime
from pathlib import Path

FORMATO = "%(asctime)s | %(levelname)-7s | %(message)s"
DATA = "%H:%M:%S"


class FormatterColorido(logging.Formatter):
    CORES = {
        logging.DEBUG: "\033[90m",     # cinza
        logging.INFO: "\033[36m",      # ciano
        logging.WARNING: "\033[33m",   # amarelo
        logging.ERROR: "\033[31m",     # vermelho
        logging.CRITICAL: "\033[41m",  # fundo vermelho
    }
    RESET = "\033[0m"

    def format(self, record):
        texto = super().format(record)
        cor = self.CORES.get(record.levelno, "")
        return f"{cor}{texto}{self.RESET}"


def configurar_log():
    os.system("")  # ativa cores ANSI no console antigo do Windows

    pasta = Path("logs")
    pasta.mkdir(exist_ok=True)

    terminal = logging.StreamHandler()
    terminal.setFormatter(FormatterColorido(FORMATO, DATA))

    arquivo = logging.FileHandler(pasta / f"robo_{datetime.now():%Y-%m-%d}.log", encoding="utf-8")
    arquivo.setFormatter(logging.Formatter(FORMATO, "%d/%m/%Y %H:%M:%S"))

    logging.basicConfig(level=logging.INFO, handlers=[terminal, arquivo])