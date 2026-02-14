# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class FiscalPrinter(models.AbstractModel):
    _name = "lms.fiscal.printer"
    _description = "Fiscal Thermal Printer Service (LOG MODE)"

    def print_html(self, html):
        """
        Modo prueba:
        NO imprime.
        Solo deja evidencia clara en el log
        de que el backend llegó aquí correctamente.
        """
        _logger.info("==============================================")
        _logger.info("========== HTML FISCAL (INICIO) ==========")

        if html:
            _logger.info(html)
        else:
            _logger.warning("HTML FISCAL VACÍO")

        _logger.info("=========== HTML FISCAL (FIN) ===========")
        _logger.info("==============================================")

        return True
