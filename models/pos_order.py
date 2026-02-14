from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    # =========================================================
    # 🔒 FORZAR CLIENTE EN ÓRDENES POS
    # =========================================================
    @api.model
    def create(self, vals):
        """
        Garantiza que toda orden POS tenga partner.
        Si viene vacío, asigna Cliente Consumidor Final.
        """

        if not vals.get("partner_id"):

            partner = self.env["res.partner"].search(
                [
                    ("name", "=", "Cliente Consumidor Final"),
                    ("company_id", "in", [False, self.env.company.id]),
                ],
                order="company_id desc",
                limit=1,
            )

            if partner:
                vals["partner_id"] = partner.id

        return super().create(vals)

    # =========================================================
    # 🔹 LEGACY / FALLBACK
    # (Se mantiene por compatibilidad)
    # =========================================================
    def _create_invoice(self, move_vals):
        """
        Crear factura desde POS (LEGACY).
        """

        if not move_vals.get("partner_id"):
            partner = self.env["res.partner"].search(
                [
                    ("name", "=", "Cliente Consumidor Final"),
                    ("company_id", "in", [False, self.env.company.id]),
                ],
                order="company_id desc",
                limit=1,
            )
            if partner:
                move_vals["partner_id"] = partner.id

        move = super()._create_invoice(move_vals)

        if "lms_fiscal_pending_print" in move._fields:
            move.write({
                "lms_fiscal_pending_print": True,
                "lms_fiscal_printed": False,
            })

        move = move.with_context(no_report=True)

        return move

    # =========================================================
    # 🔒 VALIDACIÓN FISCAL: NCF DISPONIBLE
    # =========================================================
    def _lms_check_ncf_available(self, partner):

        ncf_type = "01" if partner.vat else "02"

        domain = [
            ("company_id", "=", self.company_id.id),
            ("ncf_type", "=", ncf_type),
            ("active", "=", True),
            ("available_numbers", ">", 0),
        ]

        ncf_range = self.env["l10n_do.ncf.range"].search(domain, limit=1)

        if not ncf_range:
            raise UserError(
                _(
                    "No hay NCF disponible para facturar esta venta.\n\n"
                    "Tipo requerido: %s\n"
                    "Solución: cargue un nuevo rango de NCF antes de continuar."
                ) % ("B01" if ncf_type == "01" else "B02")
            )

        return True

    # =========================================================
    # ✅ FACTURACIÓN FISCAL DESDE POS (CORREGIDO)
    # =========================================================
    def _lms_create_fiscal_invoice_from_pos(self):
        """
        Este método ahora trabaja sobre la orden específica
        que llama el controller.
        """

        for order in self:

            if order.account_move or order.state != "paid":
                continue

            partner = order.partner_id

            if not partner:
                partner = self.env["res.partner"].search(
                    [
                        ("name", "=", "Cliente Consumidor Final"),
                        ("company_id", "in", [False, order.company_id.id]),
                    ],
                    order="company_id desc",
                    limit=1,
                )
                if not partner:
                    raise UserError(
                        _("No existe el cliente 'Cliente Consumidor Final'.")
                    )

            # Validar disponibilidad NCF
            order._lms_check_ncf_available(partner)

            # 🔑 USAR FLUJO OFICIAL POS
            order._create_invoice()

            invoice = order.account_move
            if not invoice:
                continue

            # Asignar NCF si existe el método
            if hasattr(invoice, "lms_assign_ncf"):
                invoice.lms_assign_ncf()

            # Marcar pendiente impresión fiscal
            vals = {}
            if "lms_fiscal_pending_print" in invoice._fields:
                vals["lms_fiscal_pending_print"] = True
            if "lms_fiscal_printed" in invoice._fields:
                vals["lms_fiscal_printed"] = False
            if vals:
                invoice.write(vals)

            # Postear factura
            if invoice.state == "draft":
                invoice.action_post()

        return True
