# Bulk Download Pharcar CV

This script automates the bulk downloading of Consolidated Merit Review attachments and CVs recursively across different Years and Programs.

## How to Use

1. **Install Dependencies**: 
   ```bash
   pip install selenium webdriver-manager
   ```
2. **Setup Credentials**: Ensure your `config.py` is configured properly.
3. **Run the Script**:
   ```bash
   python Pharfac_CV_download.py
   ```
4. Files are saved in an organized folder structure: `downloads/<Year>/<Program>/<Instructor Name>/`.

## Passing Credentials

Create a `config.py` file in the project's root directory containing:

```python
USERNAME = "your_username"
PASSWORD = "your_password"
```

## Logging

Unlike the other projects, this script uses Python's standard `logging` module.
- The logger is configured to output `INFO`, `WARNING`, and `ERROR` levels.
- Messages are formatted with timestamps and severity levels (e.g., `2026-02-23 21:00:00 - INFO - Starting script...`).
- Logs are output simultaneously to the terminal (StreamHandler) and appended to `run.log` (FileHandler).

## Error Handling

- **Robust Try/Except Coverage**: The script uses extensive Exception handling for specific Selenium errors like `TimeoutException` and `StaleElementReferenceException`.
- **Download Retries**: File downloads are attempted up to **2 times**. If an exception occurs on the first try, a Warning is logged, it sleeps for 2 seconds, and retries. Complete failures log an Error.
- **Graceful Degradation**: If an entire year or program encounters an unrecoverable error, the script navigates back to a safe tool URL and continues processing rather than crashing. 
- A `finally` block ensures the browser driver is gracefully shut down regardless of script success or critical failure.
