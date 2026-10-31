"""Realistic OCR document text fixtures for classification and structured extraction tests."""

STANDARD_INVOICE_TEXT = """
ACME CORPORATION
123 Innovation Way, Tech City, CA 94016
Tel: (800) 555-0199 | billing@acmecorp.com

TAX INVOICE
Invoice Number: INV-2026-8891
Invoice Date: 2026-03-15
Due Date: 2026-04-15
Payment Terms: Net 30

Bill To:
Global Solutions LLC
456 Enterprise Blvd, Suite 200
Metropolis, NY 10001

Description                      Qty    Unit Price    Total
Cloud Hosting Pro Plan            2       $250.00   $500.00
Technical Consulting Support     10        $75.00   $750.00

Subtotal: $1,250.00
Tax (10%): $125.00
Discount: $50.00
Total Amount Due: $1,325.00

Currency: USD
Thank you for your business! Remit payment via wire transfer.
"""

INVOICE_MISSING_FIELDS_TEXT = """
VERTEX DIGITAL SERVICES
Invoice # 90422
Date: 12/05/2025

Billed To:
John Doe
55 Sunset Blvd

Total Due: $450.00
"""

INVOICE_EURO_FORMAT_TEXT = """
BERLIN LOGISTICS GMBH
Alexanderplatz 1, 10178 Berlin, Germany
USt-IdNr: DE123456789

RECHNUNG / INVOICE
Invoice No: EU-99381
Date of Issue: 24/08/2025
Due Date: 15/09/2025

Bill To:
Nordic Freight AS
Oslo, Norway

Item Description                 Quantity  Unit Price  Total
Freight Transport Standard              1   1.200,00  1.200,00

Subtotal: 1.200,00 €
VAT (19%): 228,00 €
Discount: 0,00 €
Grand Total: 1.428,00 €
"""

INVOICE_BRITISH_POUND_TEXT = """
OXFORD SCIENTIFIC INSTRUMENTS LTD
Cambridge Road, London, UK
VAT Reg: GB 987 6543 21

INVOICE
Invoice ID: UK-77102
Bill Date: 10-Oct-2025
Payment Due: 10-Nov-2025

Bill To:
Edinburgh Research Lab
Scotland, UK

Description                      Qty    Price        Total
Spectrometer Calibration           1    £850.00      £850.00

Sub-Total: £850.00
Tax: £170.00
Discount: £20.00
Total: £1,000.00
"""

NOISY_OCR_INVOICE_TEXT = """
ACME  C0RPORAT1ON
TAX   1NVOICE
1nvoice No:   INV-99014
lnvoice Date : 2026-01-20
Due Date : 2026-02-20

Blll To:
Omega Corp

Subtotal : $2,000.00
Tax : $200.00
Total Amount : $2,200.00
"""

PURCHASE_ORDER_TEXT = """
GLOBAL MANUFACTURING CORP
PURCHASE ORDER
PO Number: PO-2026-4401
PO Date: 2026-02-10
Requisition No: REQ-0092

Vendor:
Precision Steel Works Inc
88 Industrial Parkway, Gary, IN

Ship To:
Global Assembly Plant #4
77 Logistics Way, Detroit, MI
Shipping Method: Ground Freight

Item Description                 Qty    Unit Price   Total
Steel Rods Grade A               100       $15.00   $1,500.00
Fastener Assemblies              500        $2.50   $1,250.00

Subtotal: $2,750.00
Sales Tax: $220.00
Total Amount: $2,970.00
Buyer: Sarah Jenkins
"""

STANDARD_FORM_TEXT = """
PATIENT MEDICAL INTAKE FORM
Form ID: FORM-MED-2026-004
Date: 2026-05-12

Applicant Information:
Full Name: Dr. Emily R. Thorne
Email Address: emily.thorne@hospital.org
Phone Number: (555) 342-8890
Residential Address: 742 Evergreen Terrace, Springfield, OR 97477

Options & Declarations:
[x] Consent to medical data sharing
[x] Agreed to telehealth terms
[ ] Request physical paper records

Signature: Emily Thorne
Date Signed: 2026-05-12
"""

MINIMAL_FORM_TEXT = """
EVENT REGISTRATION FORM
Reference No: EVT-992
Name: Michael Vance
Email: mvance@techsummit.io
Phone: +1-555-882-1920
Date: 15 June 2026
"""

CONTRACT_SAMPLE_TEXT = """
MASTER SERVICES AGREEMENT
This agreement is entered between Alpha Tech Solutions LLC and Beta Enterprises Inc.
Effective Date: 2026-01-01
Expiry Date: 2027-01-01
Renewal Date: 2026-11-01
Contract Value: $150,000.00
Payment Terms: Net 30 Days
Governing Law: State of New York
"""

RECEIPT_SAMPLE_TEXT = """
METRO CAFE & BAKERY
100 Main Street, Seattle, WA
Tel: (206) 555-0144

SALES RECEIPT
Receipt Date: 2026-04-10
Payment Method: Visa Card

Coffee & Pastry              2        $5.00    $10.00
Tax: $0.95
Total: $10.95
Thank you for visiting!
"""
