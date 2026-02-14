from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    # =========================================================
    # 🔹 LEGACY / FALLBACK
    # =========================================================
    def _create_invoice(self, move_vals):
        """
        Crear factura desde POS (LEGACY).
        Se conserva por compatibilidad futura.
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
    # 🔒 VALIDACIÓN FISCAL
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
    # ✅ FACTURACIÓN FISCAL
    # Compatible con CRON y Controller
    # =========================================================
    def _lms_create_fiscal_invoice_from_pos(self):

        company = self.env.company

        # 🔹 Si se llama desde controller → usar self
        if self:
            orders = self.filtered(
                lambda o: o.state == "paid"
                and not o.account_move
                and o.amount_total > 0
                and o.company_id.id == company.id
            )
        else:
            # 🔹 Si lo llama CRON (model-level)
            orders = self.search(
                [
                    ("state", "=", "paid"),
                    ("account_move", "=", False),
                    ("company_id", "=", company.id),
                    ("amount_total", ">", 0),
                ],
                order="date_order asc",
                limit=10,
            )

        if not orders:
            return True

        for order in orders:

            if order.account_move:
                continue

            partner = order.partner_id
            if not partner:
                partner = self.env["res.partner"].search(
                    [
                        ("name", "=", "Cliente Consumidor Final"),
                        ("company_id", "in", [False, company.id]),
                    ],
                    order="company_id desc",
                    limit=1,
                )
                if not partner:
                    raise UserError(
                        _("No existe el cliente 'Cliente Consumidor Final'.")
                    )

            order._lms_check_ncf_available(partner)

            invoice_lines = []
            for line in order.lines:
                invoice_lines.append(
                    (0, 0, {
                        "product_id": line.product_id.id,
                        "name": line.product_id.display_name,
                        "quantity": line.qty,
                        "price_unit": line.price_unit,
                        "tax_ids": [(6, 0, line.tax_ids.ids)],
                    })
                )

            move_vals = {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.context_today(order),
                "invoice_origin": order.name,
                "company_id": order.company_id.id,
                "invoice_line_ids": invoice_lines,
            }

            invoice = self.env["account.move"].create(move_vals)

            order.write({"account_move": invoice.id})

            if hasattr(invoice, "lms_assign_ncf"):
                invoice.lms_assign_ncf()

            vals = {}
            if "lms_fiscal_pending_print" in invoice._fields:
                vals["lms_fiscal_pending_print"] = True
            if "lms_fiscal_printed" in invoice._fields:
                vals["lms_fiscal_printed"] = False
            if vals:
                invoice.write(vals)

            invoice.action_post()

        return True
