import io
from datetime import date
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class ReportPDFGenerator:
    @staticmethod
    def generate_daily_eod_pdf(report_data: Dict[str, Any], hotel_name: str = "HotelOS Property") -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#0284c7'),
            fontName='Helvetica-Bold'
        )
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748b'),
            leading=14
        )
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#0f172a'),
            fontName='Helvetica-Bold'
        )

        story.append(Paragraph(f"HotelOS — Daily Operations & Financial Report", title_style))
        story.append(Paragraph(f"Property: {hotel_name} | Date: {report_data.get('report_date')} | Timezone: Asia/Kolkata", subtitle_style))
        story.append(Spacer(1, 16))

        # Financial Summary Table
        fin = report_data.get("financials", {})
        story.append(Paragraph("1. Financial Summary (Accrual vs. Cash Flow)", section_style))
        story.append(Spacer(1, 6))

        fin_table_data = [
            ["Metric", "Amount (INR)", "Type / Notes"],
            ["Earned Revenue", f"INR {fin.get('today_earned_revenue_accrual', 0):,.2f}", "Accrual Tariff + Services"],
            ["Cash Collections", f"INR {fin.get('today_cash_collections', 0):,.2f}", "Actual UPI, Cash, Cards"],
            ["Recorded Expenses", f"INR {fin.get('today_recorded_expenses', 0):,.2f}", "Direct & Shared Operating Costs"],
            ["Operating Contribution", f"INR {fin.get('today_operating_contribution', 0):,.2f}", "Revenue minus Expenses (GOP Level)"],
        ]
        t_fin = Table(fin_table_data, colWidths=[200, 150, 180])
        t_fin.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#e0f2fe')),
            ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
        ]))
        story.append(t_fin)
        story.append(Spacer(1, 16))

        # Occupancy & Rooms Table
        occ = report_data.get("occupancy", {})
        story.append(Paragraph("2. Room Occupancy & Inventory Status", section_style))
        story.append(Spacer(1, 6))

        occ_table_data = [
            ["Status Category", "Room Count", "Percentage"],
            ["Total Rooms Available", str(occ.get("total_rooms", 0)), "100.0%"],
            ["Occupied Rooms", str(occ.get("occupied_rooms", 0)), f"{occ.get('occupancy_rate_percent', 0)}%"],
            ["Vacant Clean (Ready)", str(occ.get("vacant_clean", 0)), "-"],
            ["Vacant Dirty (Housekeeping)", str(occ.get("vacant_dirty", 0)), "-"],
            ["Blocked Maintenance", str(occ.get("blocked_maintenance", 0)), "-"],
        ]
        t_occ = Table(occ_table_data, colWidths=[200, 150, 180])
        t_occ.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(t_occ)
        story.append(Spacer(1, 16))

        # Operational Discrepancies
        ops = report_data.get("operations", {})
        story.append(Paragraph("3. Operational Action Items", section_style))
        story.append(Spacer(1, 6))
        ops_data = [
            ["Operational Queue", "Count", "Required Action"],
            ["Pending Maintenance Tickets", str(ops.get("pending_maintenance_tickets", 0)), "Technician dispatch required"],
            ["Pending Housekeeping Tasks", str(ops.get("pending_housekeeping_tasks", 0)), "Cleaning & Supervisor inspection"],
            ["Missing / Damaged Assets", str(ops.get("damaged_or_missing_assets", 0)), "Linen/Asset audit reconciliation"],
        ]
        t_ops = Table(ops_data, colWidths=[200, 150, 180])
        t_ops.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(t_ops)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

