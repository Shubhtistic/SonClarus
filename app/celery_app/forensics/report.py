from fpdf import FPDF
import os

# we create a class ForensicReport that inherits from FPDF.
# So we can customize the header and footer

# A4 SIZE
PAGE_WIDTH = 210
PAGE_HEIGHT = 297


class ForensicReport(FPDF):
    def header(self):
        # set font ->  arial bold size 16
        self.set_font("Arial", "B", 16)

        # draw title -> Cell(width, height, text, border, newline, align)
        # width=0 means stretch to right margin
        self.cell(0, 10, "Sonclarus Forensic Analysis", 0, 1, "C")

        # add a line break
        self.ln(10)

    def footer(self):
        # 1.5cm from bottom
        self.set_y(-15)

        # font set to  arial italic and size 8
        self.set_font("Arial", "I", 8)

        # print page
        # {nb} is a placeholder for total page
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, "C")

    def add_file_metadata(self, metadata: dict, file_hash: str):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "File Information", 0, 1)
        self.set_font("Arial", "", 10)

        # Data to display
        info = [
            ("File Name", metadata.get("filename", "Unknown")),
            ("Duration", f"{metadata.get('duration_sec', 0)} seconds"),
            ("Sample Rate", f"{metadata.get('sample_rate', 0)} Hz"),
            ("File Size", f"{metadata.get('filesize_mb', 0)} MB"),
            ("SHA-256 Hash", file_hash[:32] + "..."),  # Show first 32 chars
        ]

        # Draw Table
        for key, value in info:
            self.set_font("Arial", "B", 10)
            self.cell(40, 8, key, 1)

            self.set_font("Arial", "", 10)
            self.cell(0, 8, str(value), 1, 1)

        self.ln(10)

    def add_visual_analysis(self, waveform_path: str, spectrogram_path: str):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Visual Analysis", 0, 1)
        self.ln(5)

        # add wveform image
        if os.path.exists(waveform_path):
            self.set_font("Arial", "", 10)
            self.cell(0, 5, "Amplitude Waveform (Time Domain)", 0, 1)
            # x=10 (margin), w=190 (full width)
            self.image(waveform_path, x=10, w=190)
            self.ln(5)

        # add spectrogram image
        if os.path.exists(spectrogram_path):
            self.cell(0, 5, "Spectrogram (Frequency Domain)", 0, 1)
            self.image(spectrogram_path, x=10, w=190)


def generate_pdf_report(
    metadata: dict,
    file_hash: str,
    waveform_path: str,
    spectrogram_path: str,
    output_pdf_path: str,
):
    """
    Main function to create pdf
    """

    pdf = ForensicReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.add_file_metadata(metadata, file_hash)
    pdf.add_visual_analysis(waveform_path, spectrogram_path)

    pdf.output(output_pdf_path)

    return output_pdf_path
