# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    def action_pos_session_close(
        self,
        balancing_account=False,
        amount_to_balance=0.0,
        bank_payment_method_diffs=None,
    ):

        res = super().action_pos_session_close(
            balancing_account,
            amount_to_balance,
            bank_payment_method_diffs,
        )

        for session in self:

            pos_move = session.move_id
            if not pos_move:
                continue

            # 🔹 Buscar cliente consumidor final
            partner = self.env["res.partner"].search(
                [
                    ("name", "=", "Cliente Consumidor Final"),
                    ("company_id", "in", [False, session.company_id.id]),
                ],
                limit=1,
            )

            if not partner:
                continue

            # 🔹 Forzar partner en líneas CxC del asiento POS
            receivable_lines = pos_move.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable"
            )

            for line in receivable_lines:
                if not line.partner_id:
                    line.write({"partner_id": partner.id})

            # 🔹 Ahora sí intentar conciliación
            invoices = self.env["account.move"].search(
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "!=", "paid"),
                    ("invoice_origin", "in", session.order_ids.mapped("name")),
                    ("company_id", "=", session.company_id.id),
                ]
            )

            for invoice in invoices:

                invoice_line = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type == "asset_receivable"
                    and not l.reconciled
                )

                pos_line = pos_move.line_ids.filtered(
                    lambda l: l.account_id.account_type == "asset_receivable"
                    and not l.reconciled
                )

                if not invoice_line or not pos_line:
                    continue

                try:
                    (invoice_line + pos_line).reconcile()

                    _logger.info(
                        "Factura %s conciliada automáticamente",
                        invoice.name,
                    )

                except Exception as e:
                    _logger.exception(
                        "Error conciliando factura %s: %s",
                        invoice.name,
                        e,
                    )

        return res
