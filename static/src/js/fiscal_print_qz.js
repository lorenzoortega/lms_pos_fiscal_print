console.log("🟢 fiscal_print_qz.js CARGADO (QZ REAL)");

window.lmsFiscalQZ = {

    async ensureConnection() {
        if (!qz.websocket.isActive()) {
            await qz.websocket.connect();
        }
    },

    // ================= HELPERS =================
    formatMoney(value) {
        const num = Number(value || 0);
        return num.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    },

    formatDateTime(dateStr) {
        const now = new Date();
        const time =
            String(now.getHours()).padStart(2, "0") +
            ":" +
            String(now.getMinutes()).padStart(2, "0");

        return `${dateStr} ${time}`;
    },

    normalize(text) {
        if (!text) return "";
        return text
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/ñ/g, "n")
            .replace(/Ñ/g, "N");
    },

    cleanProductName(name) {
        if (!name) return "";
        let clean = name.split("\n")[0];
        clean = clean.replace(/\[.*?\]/g, "");
        return this.normalize(clean).trim();
    },

    getComprobanteLabel(ncf) {
        const tipo = (ncf || "").substring(0, 3);
        if (tipo === "B01") return "Comprobante de Credito Fiscal";
        if (tipo === "B02") return "Comprobante Consumidor Final";
        return `Comprobante ${tipo}`;
    },

    formatLine(label, amount, currency, width = 44) {
        const symbol = currency?.symbol || "";
        const left = `${label} ${symbol}`.padEnd(width - 12);
        const right = this.formatMoney(amount).padStart(12);
        return left + right + "\n";
    },

    buildQR(data) {
        const size = data.length + 3;
        return (
            '\x1D\x28\x6B\x03\x00\x31\x43\x06' +
            '\x1D\x28\x6B\x03\x00\x31\x45\x30' +
            '\x1D\x28\x6B' +
            String.fromCharCode(size, 0, 49, 80, 48) +
            data +
            '\x1D\x28\x6B\x03\x00\x31\x51\x30'
        );
    },

    async printTicket(data) {
        try {
            await this.ensureConnection();

            const printer = await qz.printers.getDefault();
            const cfg = qz.configs.create(printer);
            const cmds = [];

            const PAD = "  ";
            const LINE = PAD + "-".repeat(44) + "\n";

            // RESET
            cmds.push('\x1B\x40');
            cmds.push('\n\n');

            // EMPRESA
            cmds.push('\x1B\x61\x01');
            cmds.push('\x1D\x21\x11');
            cmds.push(PAD + this.normalize(data.company.name) + '\n');
            cmds.push('\x1D\x21\x00');

            cmds.push(PAD + this.normalize(`RNC: ${data.company.rnc}`) + '\n');

            if (data.company.phone) {
                cmds.push(PAD + this.normalize(`Tel: ${data.company.phone}`) + '\n');
            }
            if (data.company.email) {
                cmds.push(PAD + this.normalize(`Email: ${data.company.email}`) + '\n');
            }

            cmds.push('\n');
            cmds.push('\x1B\x61\x00');

            // NCF
            cmds.push(LINE);
            cmds.push(PAD + this.normalize(this.getComprobanteLabel(data.ncf)) + '\n');
            cmds.push(PAD + `NCF: ${data.ncf}\n`);

            if (data.valid_until) {
                cmds.push(PAD + this.normalize(`Valido hasta: ${data.valid_until}`) + '\n');
            }

            cmds.push(PAD + `FECHA: ${this.formatDateTime(data.date)}\n`);
            cmds.push(PAD + `FACTURA: ${data.invoice_number}\n`);
            if (data.cashier) cmds.push(PAD + this.normalize(`CAJERO: ${data.cashier}`) + '\n');
            cmds.push(LINE);

            // CLIENTE
            cmds.push(PAD + this.normalize(data.partner.name) + '\n');
            if (data.partner.rnc) cmds.push(PAD + `RNC: ${data.partner.rnc}\n`);
            cmds.push(LINE);

            // DETALLE
            cmds.push(
                PAD +
                `Cant     Descripcion             Importe ${data.currency?.symbol || ""}\n`
            );
            cmds.push(LINE);

            data.lines.forEach(l => {
                const qty = l.qty.toFixed(2).padStart(7);
                const name = this.cleanProductName(l.name)
                    .substring(0, 23)
                    .padEnd(23);
                const total = this.formatMoney(l.qty * l.price).padStart(9);

                cmds.push(PAD + `${qty}  ${name}${total}\n`);
            });

            // TOTALES
            cmds.push(LINE);
            cmds.push(PAD + this.formatLine("SUBTOTAL", data.subtotal, data.currency));
            cmds.push(PAD + this.formatLine("ITBIS", data.tax, data.currency));

            // ===== TOTAL CORREGIDO =====
            cmds.push(LINE);
            cmds.push(
                PAD +
                `TOTAL ${data.currency?.symbol || ""}`.padEnd(44 - 12) +
                this.formatMoney(data.total).padStart(12) +
                "\n"
            );

            // COBRO
            if (data.payments && data.payments.length) {
                cmds.push(LINE);
                cmds.push(PAD + `Pagos ${data.currency?.symbol || ""}\n`);

                let totalPaid = 0;
                let negative = 0;

                data.payments.forEach(p => {
                    if (p.amount > 0) {
                        totalPaid += p.amount;
                        cmds.push(
                            PAD +
                            this.normalize(p.method).padEnd(20) +
                            this.formatMoney(p.amount).padStart(20) +
                            '\n'
                        );
                    } else {
                        negative += Math.abs(p.amount);
                    }
                });

                const change = Math.max(totalPaid - data.total, negative, 0);

                cmds.push(LINE);
                cmds.push(PAD + this.formatLine("Total Pagado", totalPaid, data.currency));
                cmds.push(PAD + this.formatLine("Devuelta", change, data.currency));
            }

            // CIERRE
            cmds.push('\n');
            cmds.push('\x1B\x61\x01');
            cmds.push(PAD + this.normalize('DOCUMENTO VALIDO PARA FINES FISCALES') + '\n');
            cmds.push(PAD + this.normalize('GRACIAS POR SU COMPRA') + '\n');

            const qrData =
                `RNC=${data.company.rnc}|NCF=${data.ncf}|TOTAL=${data.total}|FECHA=${data.date}`;

            cmds.push('\n');
            cmds.push(PAD + this.normalize('VERIFICACION FISCAL') + '\n');
            cmds.push(this.buildQR(qrData));
            cmds.push('\n');
            cmds.push(PAD + this.normalize('CONSERVE ESTE COMPROBANTE') + '\n');

            cmds.push('\n\n');
            cmds.push('\x1D\x56\x00');

            await qz.print(cfg, cmds);
            console.log("🟢 Ticket fiscal profesional impreso");

        } catch (err) {
            console.error("❌ Error QZ Tray:", err);
            throw err;
        }
    }
};
