# PDF to BlueBook

Local self-app for turning SAT Reading and Writing PDFs into editable, offline practice tests.

> This project is built for one teacher's day-to-day workflow: prepare material quickly, fix extraction errors, and use the generated test while teaching.

## Highlights

- Convert a text-based SAT PDF into structured passages, questions, choices, images, and answer keys.
- Use Gemini to parse questions while correcting obvious extraction spelling and spacing errors.
- Preserve useful source formatting such as bold, italic, underline, bullets, and vector-drawn answer blanks.
- Review and edit every parsed question before creating the practice test.
- Export a self-contained HTML test with a timer, passage scrolling, highlight mode, review marks, question navigation, and progress state.
- Submit the test and review each question from a color-coded result grid: green for correct and red for incorrect or unanswered.
- Keep everything local except the Gemini request used during PDF analysis.

## Overview

PDF to BlueBook is a personal teaching tool rather than a general-purpose publishing platform. SAT worksheets often contain layout, formatting, images, tables, underlined evidence, and answer blanks that are difficult to reuse directly in class. This app turns that material into a browser-based practice experience so the teacher can spend less time reformatting files and more time teaching.

The workflow is intentionally simple:

1. Upload a SAT PDF in the Streamlit app.
2. Let PyMuPDF extract the source content and Gemini identify the questions.
3. Review and correct the parsed content in the editing screen.
4. Export the practice test as an offline HTML file.
5. Open the HTML file in a browser and use it during a lesson.

### Authors

Built and maintained as a personal self-app for teaching and lesson preparation.

## Usage

Start the local app from PowerShell:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Then enter a Gemini API key, upload a SAT PDF, choose the time limit, review the extracted questions, and select **Render HTML offline**. Open the downloaded HTML file in a browser to run the practice test.

The generated test supports:

- passage scrolling and optional highlight mode;
- marking questions for review;
- switching between all, answered, marked, and unanswered questions;
- a timer configured before rendering;
- answer submission and per-question result review;
- an unscored mode when the source PDF has no answer key.

## Installation

Windows is currently the supported platform. Python 3.10 or newer and a Gemini API key are recommended.

Create or activate the project virtual environment, then install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The main dependencies are Streamlit, PyMuPDF, Pillow, and the Google GenAI SDK. The API key is entered in the app for the current session and is not written to the project files.

## Feedback and Contributing

This is currently a single-user teaching tool. If you find an extraction error or want to improve the classroom workflow, record the PDF pattern, the incorrect result, and the expected result in an issue or change request. Contributions that improve PDF fidelity, editing reliability, offline HTML behavior, and lesson usability are especially welcome.

## Current Limitations

- Scanned PDFs without a usable text layer are not yet supported reliably.
- Gemini is required for question parsing and graph detection.
- Extraction quality still depends on the source PDF's layout and text layer; review the generated questions before class.
- Highlight marks and review state live inside the open browser session and are not saved back to the source PDF.
