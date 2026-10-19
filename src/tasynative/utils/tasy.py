"""Controle do Tasy Native (app Electron) via Playwright e Chrome DevTools Protocol.

Uso:

    with Tasy(config) as tasy:
        tasy.login()
        tasy.trocar_perfil("Faturamento")
        tasy.abrir_funcao("Entrada Unica de Pacientes")
        tasy.fechar_funcao("Entrada Unica")
"""
import logging
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Literal

from playwright.sync_api import Browser, Locator, Page, Playwright, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tasynative.utils.config import Config

log = logging.getLogger(__name__)

NOME_PROCESSO = "TasyNative.exe"

# Seletores (ids únicos, obtidos no diagnóstico)
SEL_USUARIO = "#loginUsername"
SEL_SENHA = "#loginPassword"
SEL_BUSCA = "input:visible"
SEL_BOTAO_FECHAR = "[class*='close']:visible, [class*='fechar']:visible, button:visible"
SEL_ATALHO_INICIAL = ".w-feature-app__name"
SEL_MENU_USUARIO = "#userData-dropdown-options"   # junto às outras constantes

class Tasy:
    def __init__(self, config: Config, fechar_ao_sair: bool = False):
        self.config = config
        self.fechar_ao_sair = fechar_ao_sair
        self._pw: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    # ================================================================== contexto

    def __enter__(self) -> "Tasy":
        self.abrir()
        self._pw = sync_playwright().start()
        self.browser = self._conectar()
        return self

    def __exit__(self, *exc) -> Literal[False] | None:
        if self._pw:
            self._pw.stop()
        if self.fechar_ao_sair:
            self.fechar()
        return False  # não engole exceções

    # ================================================================== processo

    def abrir(self) -> None:
        """Encerra instâncias anteriores e inicia o Tasy com a porta de depuração."""
        caminho = Path(self.config.caminho)
        if not caminho.exists():
            raise FileNotFoundError(f"Executável não encontrado: {caminho}")

        self.fechar()
        log.info("Abrindo o Tasy...")
        subprocess.Popen(
            [str(caminho), f"--remote-debugging-port={self.config.porta}"],
            cwd=caminho.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def fechar(self) -> None:
        """Encerra o processo do Tasy."""
        subprocess.run(["taskkill", "/IM", NOME_PROCESSO, "/F"], capture_output=True)
        time.sleep(1)  # tempo para liberar a porta e a pasta de cache

    # ================================================================== conexão

    def _conectar(self) -> Browser:
        url = f"http://localhost:{self.config.porta}"
        fim = time.monotonic() + self.config.timeout

        # Espera a porta de depuração responder antes de conectar
        while time.monotonic() < fim:
            try:
                urllib.request.urlopen(f"{url}/json/version", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise TimeoutError("A porta de depuração do Tasy não respondeu.")

        log.info("Conectado ao Tasy na porta %s", self.config.porta)
        return self._pw.chromium.connect_over_cdp(url)

    def _reconectar(self) -> None:
        """Descarta a conexão atual e conecta de novo.

        Necessário apenas após escolher o ambiente, quando o Tasy reinicia por dentro.
        Invalida todas as páginas obtidas antes da chamada.
        """
        try:
            self.browser.close()
        except Exception:
            pass  # a conexão antiga pode já estar morta
        self.page = None
        time.sleep(2)
        self.browser = self._conectar()

    # ================================================================== páginas

    @property
    def pagina(self) -> Page:
        """Página atual do Tasy; reencontra automaticamente se a anterior fechou."""
        if self.page is None or self.page.is_closed():
            self.page = self._pagina_aberta()
        return self.page

    def _pagina_aberta(self, timeout: float | None = None) -> Page:
        fim = time.monotonic() + (timeout or self.config.timeout)
        while time.monotonic() < fim:
            for ctx in self.browser.contexts:
                for pg in reversed(ctx.pages):  # a janela mais recente primeiro
                    try:
                        if not pg.is_closed() and pg.url.startswith("http"):
                            return pg
                    except Exception:
                        pass
            time.sleep(0.5)
        raise TimeoutError("Nenhuma janela do Tasy encontrada.")

    def esperar(self, *seletores: str, timeout: float | None = None) -> tuple[Page, str]:
        """Espera algum dos seletores ficar visível em qualquer janela do app.

        Retorna a página onde apareceu e qual seletor foi encontrado.
        Janelas que fecham durante a busca (ex.: splash) são ignoradas.
        """
        fim = time.monotonic() + (timeout or self.config.timeout)
        while time.monotonic() < fim:
            for ctx in self.browser.contexts:
                for pg in ctx.pages:
                    for sel in seletores:
                        try:
                            if not pg.is_closed() and pg.locator(sel).first.is_visible():
                                return pg, sel
                        except Exception:
                            pass
            time.sleep(0.5)
        raise TimeoutError(f"Nenhum destes elementos apareceu: {seletores}")

    def texto_visivel(self, texto: str, exato: bool = False) -> Locator:
        """Primeiro elemento VISÍVEL com o texto (ignora elementos escondidos no HTML)."""
        return self.pagina.get_by_text(texto, exact=exato).locator("visible=true").first

    # ================================================================== login

    def login(self) -> Page:
        sel_ambiente = f"text={self.config.ambiente}"

        # A tela de ambiente pode ou não aparecer; espera por qualquer uma das duas
        page, encontrado = self.esperar(sel_ambiente, SEL_USUARIO)
        if encontrado == sel_ambiente:
            log.info("Selecionando ambiente: %s", self.config.ambiente)
            page.locator(sel_ambiente).first.click()
            self._reconectar()
            page, _ = self.esperar(SEL_USUARIO)

        log.info("Fazendo login como %s", self.config.usuario)
        page.locator(SEL_USUARIO).fill(self.config.usuario)
        page.locator(SEL_SENHA).fill(self.config.senha)
        page.locator(SEL_SENHA).press("Enter")

        try:
            page.wait_for_url(
                lambda url: "#/login" not in url,
                timeout=self.config.timeout * 1000,
            )
        except PlaywrightTimeoutError:
            raise RuntimeError(
                "Login não concluído. Verifique usuário e senha, "
                "ou se há autenticação em dois fatores."
            ) from None

        self.page = page
        log.info("Login realizado: %s", page.url)
        return page

    # ================================================================== funções

    def abrir_funcao(self, nome: str) -> None:
        """Pesquisa a função pelo nome e abre o resultado."""
        log.info("Abrindo função: %s", nome)
        self.pagina.locator(SEL_BUSCA).first.fill(nome)
        self.texto_visivel(nome, exato=True).click()

    def fechar_funcao(self, nome: str) -> None:
        """Fecha a aba da função clicando no X ao lado do nome.

        `nome` pode ser só um trecho do título da aba (ex.: "Entrada Unica").
        """
        log.info("Fechando a função: %s", nome)
        page = self.pagina
        # Texto visível que NÃO seja um atalho da tela inicial
        texto = (
            page.get_by_text(nome)
            .locator("visible=true")
            .and_(page.locator(f":not({SEL_ATALHO_INICIAL})"))
            .first
        )

        try:
            texto.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeoutError:
            raise RuntimeError(f"Aba da função '{nome}' não encontrada na tela.") from None

        # Procura o X visível mais próximo, subindo no máximo 4 níveis a partir do nome
        for nivel in range(1, 5):
            botao = texto.locator(f"xpath=ancestor::*[{nivel}]").locator(SEL_BOTAO_FECHAR).first
            if botao.count() > 0:
                botao.click()
                break
        else:
            # Plano B: clica à direita do nome, onde fica o X
            caixa = texto.bounding_box()
            if caixa is None:
                raise RuntimeError(f"Não foi possível localizar o X da aba '{nome}'.")
            page.mouse.click(caixa["x"] + caixa["width"] + 18, caixa["y"] + caixa["height"] / 2)

        texto.wait_for(state="detached", timeout=10000)
        log.info("Função fechada: %s", nome)

    def clicar(self, texto: str, exato: bool = True) -> None:
        """Clica no elemento visível com o texto (botões, links, abas)."""
        log.info("Clicando em: %s", texto)
        self.texto_visivel(texto, exato).click()

    def clicar_icone_ao_lado(self, texto: str) -> None:
        """Clica no ícone que fica logo à direita de um texto (ex.: funil do filtro)."""
        log.info("Clicando no ícone ao lado de: %s", texto)
        rotulo = self.texto_visivel(texto, exato=True)

        icone = rotulo.locator("xpath=following-sibling::*[1]")
        if icone.count() > 0 and icone.is_visible():
            icone.click()
            return

        # Plano B: clica logo à direita do texto, onde fica o ícone
        caixa = rotulo.bounding_box()
        if caixa is None:
            raise RuntimeError(f"Ícone ao lado de '{texto}' não encontrado.")
        self.pagina.mouse.click(caixa["x"] + caixa["width"] + 22, caixa["y"] + caixa["height"] / 2) 
    # ================================================================== menu do usuário

    def _trocar_opcao_menu(self, rotulo: str, valor: str) -> None:
        """Troca Perfil ou Setor pelo menu do usuário."""
        page = self.pagina
        self._abrir_menu_usuario()

        linha = self.texto_visivel(f"{rotulo}:")
        atual = linha.locator("xpath=..").inner_text()
        if valor in atual:
            log.info("%s já é %s", rotulo, valor)
            page.keyboard.press("Escape")
            return

        log.info("Trocando %s para: %s", rotulo, valor)
        linha.hover()
        page.get_by_text(valor, exact=True).last.click()
        page.wait_for_load_state("networkidle")

    def trocar_perfil(self, perfil: str) -> None:
        self._trocar_opcao_menu("Perfil", perfil)

    def trocar_setor(self, setor: str) -> None:
        self._trocar_opcao_menu("Setor", setor)

    def sair(self) -> None:
        """Faz logout pelo menu do usuário."""
        log.info("Saindo do sistema")
        self._abrir_menu_usuario()
        self.texto_visivel("Sair", exato=True).click()

    def _abrir_menu_usuario(self) -> None:
        self.pagina.locator(SEL_MENU_USUARIO).click()

    def nome_usuario(self) -> str:
        """Nome do usuário logado, como aparece no canto superior direito."""
        return self.pagina.locator(SEL_MENU_USUARIO).inner_text().strip()