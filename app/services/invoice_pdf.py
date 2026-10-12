from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import Invoice


def render_invoice_pdf(invoice: Invoice, *, customer_name: str = "Customer") -> BytesIO:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    y = height - 48

    pdf.setTitle(f"Invoice {invoice.invoice_number}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(48, y, f"Invoice {invoice.invoice_number}")
    y -= 26
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, y, f"Customer: {customer_name}")
    y -= 16
    pdf.drawString(48, y, f"Invoice date: {invoice.invoice_date.isoformat()}")
    y -= 16
    pdf.drawString(48, y, f"Due date: {invoice.due_date.isoformat()}")
    y -= 28

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48, y, "Service")
    pdf.drawRightString(400, y, "Qty")
    pdf.drawRightString(480, y, "Unit")
    pdf.drawRightString(550, y, "Total")
    y -= 16
    pdf.setFont("Helvetica", 9)

    for line in invoice.lines:
        if y < 70:
            pdf.showPage()
            y = height - 48
        pdf.drawString(48, y, line.description[:52])
        pdf.drawRightString(400, y, f"{line.quantity:.2f}")
        pdf.drawRightString(480, y, f"{line.unit_price:.2f}")
        pdf.drawRightString(550, y, f"{line.line_total:.2f}")
        y -= 14

    y -= 10
    pdf.line(360, y + 8, 550, y + 8)
    pdf.drawRightString(480, y, f"Subtotal: {invoice.subtotal:.2f} {invoice.currency}")
    y -= 14
    pdf.drawRightString(480, y, f"Discount ({invoice.discount_percent:.2f}%): -{invoice.discount_amount:.2f} {invoice.currency}")
    y -= 14
    pdf.drawRightString(480, y, f"Tax ({invoice.tax_percent:.2f}%): {invoice.tax_amount:.2f} {invoice.currency}")
    y -= 16
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(550, y, f"Total: {invoice.total_amount:.2f} {invoice.currency}")

    if invoice.notes:
        y -= 28
        pdf.setFont("Helvetica", 9)
        pdf.drawString(48, y, "Notes:")
        y -= 14
        for line in invoice.notes.splitlines()[:20]:
            pdf.drawString(48, y, line[:110])
            y -= 12

    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output
