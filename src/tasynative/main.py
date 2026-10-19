import logging
import time
from datetime import datetime
from pathlib import Path

from tasynative.utils.config import carregar_config
from tasynative.utils.log import configurar_log
from tasynative.utils.tasy import Tasy

# pasta_logs = Path("logs")
# pasta_logs.mkdir(exist_ok=True)
# arquivo_log = pasta_logs / f"robo_{datetime.now():%Y-%m-%d}.log"

log = logging.getLogger(__name__)

def main():
    configurar_log()

    config = carregar_config()

    with Tasy(config) as tasy:
        page = tasy.login()
        log.info("Usuário logado: %s", tasy.nome_usuario())
        # Procura pelo elemento de busca
        busca = page.locator("input:visible").first
        # Digita o nome da função
        busca.fill("Administração do Sistema")

        # Clica no ícone da função
        page.get_by_text("Administração do Sistema", exact=True).first.click()
        
        name = page.get_by_role("textbox", name="Nome")
        name.fill("David luis da Silva")
        
        tasy.clicar("Filtrar")
        
        
        
        time.sleep(10)
        page.pause()

        # Fecha a função aberta 
        tasy.fechar_funcao("Administração do Sistema")

        tasy.sair()
        
        # Próximas etapas do robô a partir daqui, usando `page`
        # ex.: page.get_by_text("Agenda").click()


if __name__ == "__main__":
    main()
