from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas


def generate_certificate(path: Path, title: str, recipient: str, event: str, issuer: str, issue_date: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=landscape(letter))
    width, height = landscape(letter)
    pdf.setTitle(f"{title} - {recipient}")
    pdf.setStrokeColor(colors.HexColor("#B08D57"))
    pdf.setLineWidth(3)
    pdf.rect(28, 28, width - 56, height - 56)
    pdf.setStrokeColor(colors.HexColor("#D9C69A"))
    pdf.setLineWidth(1)
    pdf.rect(38, 38, width - 76, height - 76)
    pdf.setFillColor(colors.HexColor("#19324D"))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width / 2, height - 125, title)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(width / 2, height - 190, "This certificate is proudly presented to")
    pdf.setFillColor(colors.HexColor("#173D5E"))
    pdf.setFont("Helvetica-Bold", 32)
    pdf.drawCentredString(width / 2, height - 245, recipient)
    pdf.setStrokeColor(colors.HexColor("#B08D57"))
    pdf.line(width * .27, height - 260, width * .73, height - 260)
    pdf.setFillColor(colors.HexColor("#444444"))
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(width / 2, height - 305, f"for successful completion of {event}")
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2, 100, f"Issued by {issuer}  |  {issue_date.isoformat()}")
    pdf.save()
