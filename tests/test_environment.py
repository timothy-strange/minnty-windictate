from minnty_windictate.environment import CheckResult, format_checks


def test_format_checks_lists_one_line_per_check():
    checks = [
        CheckResult("Windows", True, "required for the port"),
        CheckResult("python_runtime", False, "use Python 3.12 or 3.13 for faster-whisper stability; current 3.14.4"),
        CheckResult("model_path", False, "expected local model at C:/Users/danhu/Documents/whisper/faster-whisper-large-v3"),
    ]

    formatted = format_checks(checks)

    assert formatted.splitlines() == [
        "Windows: ok (required for the port)",
        "python_runtime: missing (use Python 3.12 or 3.13 for faster-whisper stability; current 3.14.4)",
        "model_path: missing (expected local model at C:/Users/danhu/Documents/whisper/faster-whisper-large-v3)",
    ]
