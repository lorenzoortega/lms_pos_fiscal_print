/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

/* =========================================================
   CONTROL GLOBAL
   ========================================================= */

let fiscalPrintInProgress = false;
let lastPrintedInvoiceId = null;

/* =========================================================
   PATCH PAYMENT SCREEN
   ========================================================= */

patch(PaymentScreen.prototype, {

    setup() {
        super.setup();
        this._ncfWarningCache = null;
        this._ncfWarningPartnerId = null;
    },

    /* =====================================================
       🔁 GETTER REACTIVO (CLAVE REAL)
       ===================================================== */

    get ncfWarningMessage() {
        const order = this.env.services.pos.get_order();
        const partner = order?.get_partner();
        const partnerId = partner ? partner.id : "CF";

        // 🔁 Si cambió el cliente → recalcular
        if (this._ncfWarningPartnerId !== partnerId) {
            this._ncfWarningPartnerId = partnerId;
            this._fetchNCFWarning(partnerId);
        }

        return this._ncfWarningCache;
    },

    async _fetchNCFWarning(partnerId) {
        try {
            const response = await fetch("/lms/pos/check_ncf_available", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        partner_id: partnerId !== "CF" ? partnerId : false,
                    },
                    id: Date.now(),
                }),
            });

            const data = await response.json();

            if (data?.result?.warning) {
                this._ncfWarningCache = data.result.message;
            } else {
                this._ncfWarningCache = null;
            }

        } catch {
            this._ncfWarningCache = null;
        }

        // 🔁 fuerza repaint natural OWL
        this.render();
    },

    /* =====================================================
       VALIDACIÓN FINAL (BLOQUEO REAL)
       ===================================================== */

    async validateOrder(isForceValidate) {

        const order = this.env.services.pos.get_order();
        const partner = order?.get_partner();

        try {
            const response = await fetch("/lms/pos/check_ncf_available", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        partner_id: partner ? partner.id : false,
                    },
                    id: Date.now(),
                }),
            });

            const data = await response.json();

            // 🔴 BLOQUEO TOTAL
            if (!data?.result?.ok) {
                this._ncfWarningCache = data.result.message;
                this.render();
                return false;
            }

        } catch {
            this._ncfWarningCache = "Error verificando disponibilidad de NCF";
            this.render();
            return false;
        }

        const result = await super.validateOrder(isForceValidate);

        if (order && order.pos_reference) {
            fetch("/lms/pos/trigger_fiscal_invoice", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: { pos_reference: order.pos_reference },
                    id: Date.now(),
                }),
            }).catch(() => {});
        }

        return result;
    },
});

/* =========================================================
   POLLING IMPRESIÓN (SIN CAMBIOS)
   ========================================================= */

async function pollFiscalBackend() {

    if (fiscalPrintInProgress) return;

    try {
        const response = await fetch("/lms/pos/next_fiscal_invoice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {},
                id: Date.now(),
            }),
        });

        const data = await response.json();
        if (!data?.result?.ready) return;

        const invoiceId = data.result.invoice_id;
        if (lastPrintedInvoiceId === invoiceId) return;

        fiscalPrintInProgress = true;

        await window.lmsFiscalQZ.printTicket(data.result);

        await fetch("/lms/pos/mark_fiscal_printed", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { invoice_id: invoiceId },
                id: Date.now(),
            }),
        });

        lastPrintedInvoiceId = invoiceId;

    } catch (err) {
        console.error("❌ Error impresión fiscal:", err);
    } finally {
        fiscalPrintInProgress = false;
    }
}

setInterval(pollFiscalBackend, 2000);
