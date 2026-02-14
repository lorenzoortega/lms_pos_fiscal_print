# -*- coding: utf-8 -*-
import logging
import re

from odoo import models, api

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _cron_reconcile_pos_ncf_invoices(self):
        """
        CRON:
        - Concilia facturas con NCF creadas desde POS
        - 1) Solo si la sesión POS está cerrada
        - 2) Fallback: pagos manuales por NCF en texto (regex)
        """

        company = self.env.company

        invoices = self.search(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
                ("invoice_origin", "!=", False),
                ("ncf_number", "!=", False),
                ("company_id", "=", company.id),
            ],
            order="invoice_date asc",
            limit=20,
        )

        _logger.info(
            "[POS NCF CRON] Facturas candidatas encontradas: %s",
            len(invoices),
        )

        for invoice in invoices:
            try:
                reconciled = self._reconcile_by_pos_order(invoice)

                if not reconciled:
                    self._reconcile_by_manual_ncf(invoice)

            except Exception as e:
                _logger.exception(
                    "[POS NCF CRON] Error procesando factura %s (%s): %s",
                    invoice.name,
                    invoice.id,
                    e,
                )

    # ------------------------------------------------------------------
    # MÉTODO 1: Conciliación por POS Order (SOLO sesión cerrada)
    # ------------------------------------------------------------------

    def _reconcile_by_pos_order(self, invoice):
        PosOrder = self.env["pos.order"]

        pos_orders = PosOrder.search(
            [
                ("name", "=", invoice.invoice_origin),
                ("state", "in", ("paid", "done")),
                ("company_id", "=", invoice.company_id.id),
            ],
            limit=2,
        )

        if not pos_orders or len(pos_orders) != 1:
            return False

        pos_order = pos_orders[0]

        # 🔒 SOLO conciliar si la sesión está cerrada
        if pos_order.session_id.state != "closed":
            _logger.info(
                "[POS NCF CRON] Sesión abierta (%s). No se concilia factura %s",
                pos_order.session_id.name,
                invoice.name,
            )
            return False

        # Validación de montos
        if abs(pos_order.amount_total - invoice.amount_total) > 0.01:
            _logger.warning(
                "[POS NCF CRON] Diferencia de monto POS vs Factura. POS %s | Factura %s",
                pos_order.amount_total,
                invoice.amount_total,
            )
            return False

        # Obtener asiento contable del POS (Community)
        pos_move = pos_order.account_move
        if not pos_move:
            _logger.warning(
                "[POS NCF CRON] POS Order %s no tiene asiento contable aún",
                pos_order.name,
            )
            return False

        # Línea receivable factura
        invoice_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
        )

        if not invoice_line:
            return False

        # Línea receivable del asiento POS
        pos_receivable_lines = pos_move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
        )

        if not pos_receivable_lines:
            _logger.warning(
                "[POS NCF CRON] No hay línea receivable en asiento POS %s",
                pos_move.name,
            )
            return False

        (invoice_line + pos_receivable_lines).reconcile()

        _logger.info(
            "[POS NCF CRON] Factura %s conciliada tras cierre de sesión %s",
            invoice.name,
            pos_order.session_id.name,
        )

        return True

    # ------------------------------------------------------------------
    # MÉTODO 2: Conciliación manual por NCF en texto (REGEX)
    # ------------------------------------------------------------------

    def _reconcile_by_manual_ncf(self, invoice):
        Payment = self.env["account.move"]

        ncf_invoice = invoice.ncf_number
        if not ncf_invoice:
            return False

        payments = Payment.search(
            [
                ("move_type", "=", "out_payment"),
                ("state", "=", "posted"),
                ("company_id", "=", invoice.company_id.id),
                ("line_ids.reconciled", "=", False),
                "|",
                ("ref", "!=", False),
                ("narration", "!=", False),
            ],
            limit=20,
        )

        for payment in payments:
            text = " ".join(filter(None, [payment.ref, payment.narration]))

            match = re.search(r"(B\d{2}\d{8,})", text)
            if not match:
                continue

            ncf_found = match.group(1)

            if ncf_found != ncf_invoice:
                continue

            pay_line = payment.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
            )

            inv_line = invoice.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
            )

            if not pay_line or not inv_line:
                continue

            if abs(payment.amount_total - invoice.amount_residual) > 0.01:
                _logger.warning(
                    "[POS NCF CRON] Monto no coincide para NCF %s. Pago %s | Residual %s",
                    ncf_invoice,
                    payment.amount_total,
                    invoice.amount_residual,
                )
                continue

            (pay_line + inv_line).reconcile()

            _logger.info(
                "[POS NCF CRON] Factura %s conciliada por pago manual NCF %s",
                invoice.name,
                ncf_invoice,
            )

            return True

        return False
