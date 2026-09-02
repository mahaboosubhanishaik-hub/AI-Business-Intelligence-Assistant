import os
import pandas as pd

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls"
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit


def allowed_file(filename):
    """Check if file extension is allowed."""
    if not filename or "." not in filename:
        return False
    extension = os.path.splitext(filename)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def load_dataset(filepath, nrows=None):
    """
    Safely load CSV or Excel dataset into a Pandas DataFrame.
    Validates file existence, non-zero file size, supported extension, and content readability.
    """
    if not os.path.exists(filepath):
        raise ValueError("Dataset file does not exist on disk.")

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")

    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size ({file_size / (1024*1024):.1f} MB) exceeds maximum allowed limit of 50 MB."
        )

    extension = os.path.splitext(filepath)[1].lower()

    if extension == ".csv":
        # Attempt reading CSV with multiple encoding fallbacks
        encodings_to_try = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
        df = None
        last_error = None

        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(filepath, encoding=encoding, nrows=nrows)
                break
            except (UnicodeDecodeError, pd.errors.ParserError) as err:
                last_error = err
                continue
            except Exception as err:
                last_error = err
                break

        if df is None:
            raise ValueError(f"Unable to parse CSV file: {str(last_error)}")

    elif extension in {".xlsx", ".xls"}:
        try:
            df = pd.read_excel(filepath, nrows=nrows)
        except Exception as err:
            raise ValueError(f"Unable to parse Excel file: {str(err)}")

    else:
        raise ValueError("Unsupported file format. Please upload CSV or Excel files.")

    if df is None or df.empty or len(df.columns) == 0:
        raise ValueError("The uploaded dataset contains no valid data or columns.")

    return df