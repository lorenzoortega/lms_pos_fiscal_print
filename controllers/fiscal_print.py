from odoo import http, _
from odoo.http import request


class FiscalPrintController(http.Controller):

    # =========================================================
    # ENDPOINT EXISTENTE – NO TOCADO
    # =========================================================

    @http.route(
        "/lms/pos/last_fiscal_invoice",
        type="json",
        auth="user",
        csrf=False
    )
    def last_fiscal_invoice(self):
        """
        Devuelve la última factura POS creada por el usuario actual,
        con TODOS los datos fiscales reales.
        """

        user = request.env.user

        order = request.env["pos.order"].search(
            [
                ("user_id", "=", user.id),
                ("account_move", "!=", False),
            ],
            order="id desc",
            limit=1,
        )

        if not order:
            return {"error": "No hay factura POS aún"}

        invoice = order.account_move
        company = invoice.company_id
        partner = invoice.partner_id
        currency = invoice.currency_id

        valid_until = ""
        if invoice.ncf_range_id and invoice.ncf_range_id.date_end:
            try:
                valid_until = invoice.ncf_range_id.date_end.strftime("%d/%m/%Y")
            except Exception:
                valid_until = ""

        payments = []
        total_paid = 0.0
        for payment in order.payment_ids:
            payments.append({
                "method": payment.payment_method_id.name,
                "amount": payment.amount,
            })
            total_paid += payment.amount

        change = max(total_paid - invoice.amount_total, 0)

        return {
            "company": {
                "name": company.name,
                "rnc": company.vat,
                "phone": company.phone,
                "city": company.city,
                "address": company.street,
            },
            "invoice_id": invoice.id,
            "invoice_number": invoice.name,
            "ncf": invoice.ncf_number,
            "date": invoice.invoice_date.strftime("%d/%m/%Y") if invoice.invoice_date else "",
            "valid_until": valid_until,
            "currency": {
                "symbol": currency.symbol,
                "position": currency.position,
            },
            "cashier": order.user_id.name,
            "partner": {
                "name": partner.name or "CONSUMIDOR FINAL",
                "rnc": partner.vat,
            },
            "subtotal": invoice.amount_untaxed,
            "tax": invoice.amount_tax,
            "total": invoice.amount_total,
            "payments": payments,
            "amount_paid": total_paid,
            "change": change,
            "lines": [
                {
                    "name": line.name,
                    "qty": line.quantity,
                    "price": line.price_unit,
                }
                for line in invoice.invoice_line_ids
            ],
        }

    # =========================================================
    # ENDPOINT EXISTENTE – NO TOCADO
    # =========================================================

    @http.route(
        "/lms/pos/fiscal_invoice_by_reference",
        type="json",
        auth="user",
        csrf=False
    )
    def fiscal_invoice_by_reference(self, pos_reference):

        if not pos_reference:
            return {"ready": False}

        order = request.env["pos.order"].sudo().search(
            [
                ("pos_reference", "=", pos_reference),
                ("account_move", "!=", False),
            ],
            limit=1,
            order="id desc",
        )

        if not order:
            return {"ready": False}

        invoice = order.account_move
        company = invoice.company_id
        partner = invoice.partner_id
        currency = invoice.currency_id

        valid_until = ""
        if invoice.ncf_range_id and invoice.ncf_range_id.date_end:
            try:
                valid_until = invoice.ncf_range_id.date_end.strftime("%d/%m/%Y")
            except Exception:
                valid_until = ""

        payments = []
        total_paid = 0.0
        for payment in order.payment_ids:
            payments.append({
                "method": payment.payment_method_id.name,
                "amount": payment.amount,
            })
            total_paid += payment.amount

        change = max(total_paid - invoice.amount_total, 0)

        return {
            "ready": True,
            "company": {
                "name": company.name,
                "rnc": company.vat,
                "phone": company.phone,
                "city": company.city,
                "address": company.street,
            },
            "invoice_id": invoice.id,
            "invoice_number": invoice.name,
            "ncf": invoice.ncf_number,
            "date": invoice.invoice_date.strftime("%d/%m/%Y") if invoice.invoice_date else "",
            "valid_until": valid_until,
            "currency": {
                "symbol": currency.symbol,
                "position": currency.position,
            },
            "cashier": order.user_id.name,
            "partner": {
                "name": partner.name or "CONSUMIDOR FINAL",
                "rnc": partner.vat,
            },
            "subtotal": invoice.amount_untaxed,
            "tax": invoice.amount_tax,
            "total": invoice.amount_total,
            "payments": payments,
            "amount_paid": total_paid,
            "change": change,
            "lines": [
                {
                    "name": line.name,
                    "qty": line.quantity,
                    "price": line.price_unit,
                }
                for line in invoice.invoice_line_ids
            ],
        }

    # =========================================================
    # ENDPOINT EXISTENTE – NO TOCADO
    # =========================================================

    @http.route(
        "/lms/pos/next_fiscal_invoice",
        type="json",
        auth="user",
        csrf=False
    )
    def next_fiscal_invoice(self):

        user = request.env.user

        order = request.env["pos.order"].sudo().search(
            [
                ("user_id", "=", user.id),
                ("state", "=", "paid"),
                ("account_move", "!=", False),
            ],
            order="id desc",
            limit=1,
        )

        if not order:
            return {"ready": False}

        invoice = order.account_move

        if (
            not invoice
            or not invoice.lms_fiscal_pending_print
            or invoice.lms_fiscal_printed
        ):
            return {"ready": False}

        return self.fiscal_invoice_by_reference(order.pos_reference)

    # =========================================================
    # 🆕 DISPARO INMEDIATO (ANTI-CRON)
    # =========================================================

    @http.route(
        "/lms/pos/trigger_fiscal_invoice",
        type="json",
        auth="user",
        csrf=False
    )
    def trigger_fiscal_invoice(self, pos_reference):

        if not pos_reference:
            return {"ok": False}

        order = request.env["pos.order"].sudo().search(
            [
                ("pos_reference", "=", pos_reference),
                ("state", "=", "paid"),
                ("account_move", "=", False),
            ],
            limit=1,
        )

        if not order:
            return {"ok": False}

        order._lms_create_fiscal_invoice_from_pos()

        return {"ok": True}

    # =========================================================
    # ENDPOINT EXISTENTE – NO TOCADO
    # =========================================================

    @http.route(
        "/lms/pos/mark_fiscal_printed",
        type="json",
        auth="user",
        csrf=False
    )
    def mark_fiscal_printed(self, invoice_id):

        if not invoice_id:
            return {"ok": False}

        invoice = request.env["account.move"].sudo().browse(invoice_id)
        if not invoice.exists():
            return {"ok": False}

        invoice.write({
            "lms_fiscal_printed": True,
            "lms_fiscal_pending_print": False,
        })

        return {"ok": True}

    # =========================================================
    # 🆕 VALIDACIÓN NCF + ALERTA POR UMBRAL (SIN ROMPER POS)
    # =========================================================

    @http.route(
        "/lms/pos/check_ncf_available",
        type="json",
        auth="user",
        csrf=False
    )
    def check_ncf_available(self, partner_id=None):
        """
        Verifica disponibilidad de NCF y alerta preventiva
        cuando el rango entra en umbral bajo.
        """

        company = request.env.company

        partner = None
        if partner_id:
            partner = request.env["res.partner"].sudo().browse(partner_id)

        # Cliente con RNC → B01 | Consumidor final → B02
        ncf_type = "01" if (partner and partner.vat) else "02"

        ncf_range = request.env["l10n_do.ncf.range"].sudo().search([
            ("company_id", "=", company.id),
            ("ncf_type", "=", ncf_type),
            ("active", "=", True),
        ], limit=1)

        # 🔴 SIN NCF → BLOQUEO POS
        if not ncf_range or ncf_range.available_numbers <= 0:
            return {
                "ok": False,
                "message": _(
                    "No hay NCF disponible para este tipo de cliente.\n"
                    f"(Tipo requerido: B{ncf_type})\n"
                    "Contacte al administrador."
                )
            }

        # ⚠️ ALERTA PREVENTIVA (NO BLOQUEA)
        if ncf_range.is_low_ncf:
            return {
                "ok": True,
                "warning": True,
                "available": ncf_range.available_numbers,
                "threshold": company.ncf_low_threshold,
                "message": _(
                    f"Quedan {ncf_range.available_numbers} NCF disponibles "
                    f"para este tipo de cliente (B{ncf_type}). "
                    "Contacte al administrador."
                )
            }

        # 🟢 TODO OK
        return {"ok": True}
