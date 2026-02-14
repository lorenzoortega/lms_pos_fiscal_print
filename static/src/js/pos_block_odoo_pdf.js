import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/*
 =========================================================
 ⛔ BLOQUEO DEFINITIVO DE FACTURA PDF EN POS (ODOO 18)
 - B01 y B02
 - Evita to_invoice = true
 - NO rompe impresión térmica
 - Backend sigue facturando
 =========================================================
*/

patch(PaymentScreen.prototype, {

    setup() {
        super.setup();

        const order = this.env.services.pos.get_order();
        if (order) {
            // 🔒 CLAVE: el POS NUNCA debe facturar
            order.set_to_invoice(false);
        }
    },

    async validateOrder(isForceValidate) {
        const order = this.env.services.pos.get_order();
        if (order) {
            // 🔒 Refuerzo: evitar que Odoo vuelva a marcarla
            order.set_to_invoice(false);
        }

        return await super.validateOrder(isForceValidate);
    },
});
