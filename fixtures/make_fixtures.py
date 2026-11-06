"""Generate the sample .docx fixtures used by the eval cases.

Run:  python fixtures/make_fixtures.py

The agreement is fictional. It deliberately includes things that make
document edits hard: defined terms used across sections, cross-references
("Section 7.1"), a table, and a mix of heading and body styles.
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt

OUT = Path(__file__).parent

SECTIONS = [
    ("1. Definitions", [
        '1.1 "Company" means Northwind Logistics, LLC, an Illinois limited liability company.',
        '1.2 "Employee" means the individual identified on the signature page of this Agreement.',
        '1.3 "Confidential Information" means non-public business, customer, pricing, and personnel information of the Company.',
        '1.4 "Restricted Period" means the twelve (12) months following the termination of Employee\'s employment for any reason.',
    ]),
    ("2. Position and Duties", [
        "2.1 Position. Employee shall serve as Regional Operations Manager and report to the Vice President of Operations.",
        "2.2 Duties. Employee shall devote substantially all business time to the Company and perform duties customary for the position.",
    ]),
    ("3. Term", [
        "3.1 At-Will Employment. Employee's employment is at will and may be terminated by either party at any time, with or without cause.",
    ]),
    ("4. Compensation", [
        "4.1 Base Salary. The Company shall pay Employee the base salary set out in the table below, payable bi-weekly.",
        "4.2 Bonus. Employee is eligible for an annual discretionary bonus as determined by the Company.",
    ]),
    ("5. Confidentiality", [
        "5.1 Non-Disclosure. Employee shall not disclose Confidential Information to any third party during or after employment.",
        "5.2 Return of Materials. Upon termination, Employee shall return all Company property and Confidential Information.",
    ]),
    ("6. Termination", [
        "6.1 Notice. Either party should provide two (2) weeks' written notice of resignation or termination where practicable.",
        "6.2 Final Pay. The Company shall pay all earned wages in accordance with applicable law.",
    ]),
    ("7. Restrictive Covenants", [
        "7.1 Non-Competition. During the Restricted Period, Employee shall not perform services for a competitor of the Company within fifty (50) miles of any Company facility at which Employee worked.",
        "7.2 Non-Solicitation. During the Restricted Period, Employee shall not solicit any employee of the Company to leave the Company's employ.",
        "7.3 Reasonableness. Employee agrees the restrictions in Section 7.1 and Section 7.2 are reasonable and necessary to protect the Company's legitimate business interests.",
    ]),
    ("8. Dispute Resolution", [
        "8.1 Arbitration. Any dispute arising out of this Agreement shall be resolved by binding arbitration administered by the American Arbitration Association.",
        "8.2 Class Waiver. Claims shall be brought only in an individual capacity and not as a plaintiff or class member in any purported class or collective proceeding.",
    ]),
    ("9. General", [
        "9.1 Governing Law. This Agreement shall be governed by the laws of the State of Illinois.",
        "9.2 Entire Agreement. This Agreement is the entire agreement between the parties regarding its subject matter.",
    ]),
]


def build_agreement_a(path: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(11)

    doc.add_heading("EMPLOYMENT AGREEMENT", level=0)
    doc.add_paragraph(
        "This Employment Agreement (the \"Agreement\") is entered into between the Company and Employee "
        "as of the date of the last signature below."
    )

    for heading, paras in SECTIONS:
        doc.add_heading(heading, level=1)
        for text in paras:
            p = doc.add_paragraph()
            # Bold caption run + body run, so edits that flatten runs are detectable.
            num, _, rest = text.partition(" ")
            caption, dot, body = rest.partition(". ") if not rest.startswith('"') else ("", "", rest)
            p.add_run(f"{num} ")
            if dot:
                r = p.add_run(f"{caption}.")
                r.bold = True
                p.add_run(f" {body}")
            else:
                p.add_run(rest)
            if num == "4.1":
                table = doc.add_table(rows=3, cols=2)
                table.style = "Table Grid"
                for row, (a, b) in zip(table.rows, [("Component", "Amount"),
                                                     ("Base Salary", "$92,000 per year"),
                                                     ("Car Allowance", "$450 per month")]):
                    row.cells[0].text, row.cells[1].text = a, b

    doc.save(path)


if __name__ == "__main__":
    build_agreement_a(OUT / "employment_agreement_A.docx")
    print("Wrote", OUT / "employment_agreement_A.docx")
