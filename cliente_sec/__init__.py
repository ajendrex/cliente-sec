import re
from collections import namedtuple
from datetime import date

from bs4 import BeautifulSoup
from django.utils.datetime_safe import datetime
from requests import Session


class ResumenInscripcion:
    def __init__(
            self,
            folio: int,
            fecha_inscripcion: date,
            tipo: str,
            ubicacion: str,
            estado: str,
            nombre_declarador: str,
            rut_declarador: str,
            adjuntos: list = None,
    ):
        self.folio = folio
        self.fecha_inscripcion = fecha_inscripcion
        self.tipo = tipo
        self.ubicacion = ubicacion
        self.estado = estado
        self.nombre_declarador = nombre_declarador
        self.rut_declarador = rut_declarador
        self.adjuntos = adjuntos or []

    def __repr__(self):
        return f'Instalación ubicada en {self.ubicacion}'

    def agregar_adjunto(self, adjunto):
        self.adjuntos.append(adjunto)


class Inscripcion:
    def __init__(
            self, folio, fecha_inscripcion, tipo, medio, presentacion, cliente: 'ClienteSEC'):
        self.folio = folio
        self.fecha_inscripcion = fecha_inscripcion
        self.tipo = tipo
        self.medio = medio
        self.presentacion = presentacion
        self._cliente = cliente
        self._resumen = None
        self._certificado_html = None
        self._certificado_pdf = None

    def __repr__(self):
        return f'{self.tipo} folio {self.folio} inscrita el {self.fecha_inscripcion}'

    @property
    def resumen(self):
        if self._resumen is None:
            self._resumen = self._cliente.resumen_inscripcion(self.folio)
        return self._resumen

    @property
    def certificado_html(self):
        if self._certificado_html is None:
            self._obtener_certificados()
        return self._certificado_html

    @property
    def certificado_pdf(self):
        if self._certificado_pdf is None:
            self._obtener_certificados()
        return self._certificado_pdf

    def _obtener_certificados(self):
        result = self._cliente.certificados_inscripcion(self.folio)
        self._certificado_html, self._certificado_pdf = result


FilaInscripcion = namedtuple(
    'FilaInscripcion', ['folio', 'inscripcion', 'tipo', 'medio', 'presentacion'])


class Adjunto:
    def __init__(self, nombre_archivo: str, tamano_archivo: str, url: str, cliente: 'ClienteSEC'):
        self.nombre_archivo = nombre_archivo
        self.tamano_archivo = tamano_archivo
        self.url = url
        self._cliente = cliente
        self._archivo = None

    def __repr__(self):
        return self.nombre_archivo

    @property
    def archivo(self):
        if self._archivo is None:
            self._archivo = self._cliente.get(self._cliente.dominio + self.url).content
        return self._archivo


class ClienteSEC(Session):
    dominio = 'https://wlhttp.sec.cl/edeclarador/'
    url_login = 'autentificacion.do'
    url_inscripciones = 'usuarioDeclarador.do'
    url_pdf_inscripcion = 'Firma'

    def __init__(self, rut: str, password: str):
        super().__init__()
        self.login(rut, password)
        self.rut = rut

    def __repr__(self):
        return f'Cliente SEC para rut {self.rut}'

    def _get(self, url, params=None):
        if params is None:
            params = {}
        self._last_result = self.get(self.dominio + url, params=params)
        return BeautifulSoup(self._last_result.text, features='html.parser')

    def _post(self, url, params=None, data=None):
        if data is None:
            data = {}
        if params is None:
            params = {}
        self._last_result = self.post(self.dominio + url, params=params, data=data)
        return BeautifulSoup(self._last_result.text, features='html.parser')

    def login(self, rut, password):
        login_params = {
            'accion': 'ingresar_usuario',
            'accion2': 'persona',
            'tipoUsuario': 6,
            'declaRut': rut,
            'password': password,
        }
        self._login_result = self._post(self.url_login, params=login_params)

    def _obtener_inscripciones_desde_pagina(self, pagina):
        tabla = pagina.find(id='kakits')
        if tabla is None:
            return
        filas = tabla.find_all('tr', recursive=False)[1:]
        for row in filas:
            insc = FilaInscripcion(*(td.text.strip() for td in row.find_all('td')[:-1]))
            yield Inscripcion(
                insc.folio, insc.inscripcion, insc.tipo, insc.medio, insc.presentacion, self)

    def obtener_inscripciones(self):
        n_pagina = 0
        params = {
            'accion': 'menu.usuarioDeclarador.declaracionesInscritas',
            'accionEspecifica': 'menu.usuarioDeclarador.declaracionesInscritas.buscar',
            'pagActual': n_pagina,
            'tipoTramiteINP': '0',
            'folioInscripcionINP': ''
        }
        pagina = self._get(self.url_inscripciones, params)
        visitar_siguiente = False
        for inscripcion in self._obtener_inscripciones_desde_pagina(pagina):
            visitar_siguiente = True
            yield inscripcion
        while visitar_siguiente:
            n_pagina += 1
            params = {
                'accion': 'menu.usuarioDeclarador.declaracionesInscritas.paginar',
                'pagActual': str(n_pagina),
                'tipoOrden': 'asc',
                'columnaOrden': '-1',
            }
            pagina = self._get(self.url_inscripciones, params)
            visitar_siguiente = False
            for inscripcion in self._obtener_inscripciones_desde_pagina(pagina):
                visitar_siguiente = True
                yield inscripcion

    def buscar_en_sopa(self, sopa, etiqueta, tag='td'):
        tag = sopa.find(tag, string=re.compile(etiqueta))
        return tag.next_sibling.next_sibling.text.strip()

    def resumen_inscripcion(self, folio):
        params = {
            'accion': 'menu.usuarioDeclarador.declaracionesInscritas.visualizar',
            'folio': folio,
            'medio': 'ELECTRÓNICO',
        }
        sopa = self._get(self.url_inscripciones, params)

        tfolio, tfec = sopa.find_all(id='table2')
        fecha_inscripcion = tfec.tr.find_all('td')[1].text.strip()
        summary = ResumenInscripcion(
            folio=tfolio.tr.find_all('td')[1].text.strip(),
            fecha_inscripcion=datetime.strptime(fecha_inscripcion, '%d/%m/%Y').date(),
            tipo=self.buscar_en_sopa(sopa, 'Tipo de Trámite'),
            ubicacion=self.buscar_en_sopa(sopa, 'Ubicación'),
            estado=self.buscar_en_sopa(sopa, 'Estado'),
            nombre_declarador=self.buscar_en_sopa(sopa, 'Nombre Declarador'),
            rut_declarador=self.buscar_en_sopa(sopa, 'R.U.T. Declarador:'),
        )
        tabla_adjuntos = sopa.find('table', id='adjuntos').table.table
        for row in tabla_adjuntos.find_all('tr')[1:]:
            tds = row.find_all('td')
            summary.agregar_adjunto(Adjunto(
                nombre_archivo=tds[0].text.strip(),
                tamano_archivo=tds[1].text.strip(),
                url=tds[2].a['href'],
                cliente=self,
            ))
        return summary

    def certificados_inscripcion(self, folio):
        params = {
            'accion': 'verInscripcionPopUp',
            'folioPresentacion': folio,
        }
        cert = self._get(self.url_inscripciones, params)
        pdf = self.get(self.dominio + self.url_pdf_inscripcion, params={'sub': 'PRINT'})
        return cert, pdf.content
