/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/**
 * Valida RNC / Cédula dominicana
 */
function isValidRnc(vat) {
    if (!vat) return false;
    const v = vat.replace(/\D/g, "");
    return v.length === 9 || v.length === 11;
}

patch(PaymentScreen.prototype, {

    setup() {
        super.setup();

        // 🔁 Tick reactivo OWL (única fuente de re-render)
        this._ncfTick = 0;

        // 🔴 Mensaje de error fiscal (inyectado desde pos_auto_print.js)
        this._ncfErrorMessage = null;
    },

    /* =====================================================
       MENSAJE EXISTENTE (NO SE TOCA)
       ===================================================== */

    get ncfSuggestion() {
        this._ncfTick;

        const order = this.env.services.pos.get_order();
        if (!order) return null;

        const partner = order.get_partner();
        if (partner && isValidRnc(partner.vat)) {
            return "🟦 NCF sugerido: B01 – Crédito Fiscal";
        }

        return "🟨 NCF sugerido: B02 – Consumo";
    },

    /* =====================================================
       🆕 MENSAJE DE ERROR FISCAL (ESTE ERA EL QUE FALTABA)
       ===================================================== */

    get ncfError() {
        this._ncfTick;
        return this._ncfErrorMessage;
    },

    /* =====================================================
       MENSAJES UNIFICADOS (SE MANTIENEN, NO SE ROMPEN)
       ===================================================== */

    get ncfMessages() {
        this._ncfTick;

        const messages = [];

        // 1️⃣ Mensaje sugerido (siempre visible)
        const suggestion = this.ncfSuggestion;
        if (suggestion) {
            messages.push({
                type: "suggestion",
                text: suggestion,
            });
        }

        // 2️⃣ Mensaje de error fiscal (si existe)
        if (this._ncfErrorMessage) {
            messages.push({
                type: "error",
                text: this._ncfErrorMessage,
            });
        }

        return messages;
    },
});
