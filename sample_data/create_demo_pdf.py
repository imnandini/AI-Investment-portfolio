"""Create a clearly labeled synthetic fixture. No real company financial data."""
from pathlib import Path
import pymupdf

path = Path(__file__).with_name("synthetic_report.pdf")
with pymupdf.open() as pdf:
    page = pdf.new_page()
    page.insert_textbox(pymupdf.Rect(45, 50, 550, 800),
        "SYNTHETIC DEMO DATA - NOT A REAL COMPANY REPORT\n\n"
        "AAA annual research fixture - FY2026\n\n"
        "Revenue was 120 illustrative units. Profit was 20 illustrative units.\n"
        "Debt was 30 illustrative units. Liquidity risk and customer concentration\n"
        "require further research. These figures exist solely for application testing.\n\n"
        "This document is not investment advice or evidence about a listed issuer.", fontsize=12)
    pdf.save(path)
print(path)
