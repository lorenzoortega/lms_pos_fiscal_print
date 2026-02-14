from odoo import models, fields


class AccountMove(models.Model):
    _inherit = "account.move"

    # =========================================
    # CAMPOS FISCALES
    # =========================================
    lms_fiscal_pending_print = fields.Boolean(default=False)
    lms_fiscal_printed = fields.Boolean(default=False)

    # =========================================
    # BLOQUEO SECUNDARIO (MANUAL)
    # =========================================
    def action_invoice_print(self):
        """
        Evita la generación MANUAL del PDF
        SOLO para facturas creadas desde el POS.
        (Botón "Imprimir factura")
        """

        pos_moves = self.filtered(
            lambda m: m.move_type == "out_invoice" and m.pos_order_ids
        )

        if pos_moves:
            # 🔕 Saltamos impresión PDF manual
            return False

        return super().action_invoice_print()

    # =========================================
    # BLOQUEO REAL (AUTOMÁTICO DESDE POS) 🔒
    # =========================================
    def _generate_and_attach_pdf(self):
        """
        Bloquea la generación AUTOMÁTICA del PDF estándar de Odoo
        SOLO para facturas creadas desde POS cuando usamos
        impresión fiscal propia.
        """

        pos_moves = self.filtered(
            lambda m:
                m.move_type == "out_invoice"
                and (
                    m.pos_order_ids
                    or self.env.context.get("lms_disable_odoo_pdf")
                    or self.env.context.get("from_pos")
                )
        )

        # ⛔ POS → NO generar PDF
        if pos_moves:
            return False

        # 📄 Facturas NO POS → flujo estándar
        return super()._generate_and_attach_pdf()
