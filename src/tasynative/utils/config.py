"""Configurações do robô, lidas do arquivo .env ou das variáveis de ambiente."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

CAMINHO_PADRAO = r"C:\Program Files\Philips EMR\TasyNative\TasyNative.exe"


@dataclass(frozen=True)
class Config:
    usuario: str
    senha: str
    caminho: str = CAMINHO_PADRAO
    porta: int = 9222
    ambiente: str = "Produção"
    timeout: int = 60  # segundos


def carregar_config() -> Config:
    load_dotenv()

    usuario = os.getenv("TASY_USUARIO")
    senha = os.getenv("TASY_SENHA")
    if not usuario or not senha:
        raise RuntimeError(
            "Defina TASY_USUARIO e TASY_SENHA no arquivo .env ou nas variáveis de ambiente."
        )

    return Config(
        usuario=usuario,
        senha=senha,
        caminho=os.getenv("TASY_CAMINHO", CAMINHO_PADRAO).strip(),
        porta=int(os.getenv("TASY_PORTA", "9222")),
        ambiente=os.getenv("TASY_AMBIENTE", "Produção"),
        timeout=int(os.getenv("TASY_TIMEOUT", "60")),
    )
