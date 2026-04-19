from minnty_windictate.environment import CheckResult, format_checks


def test_format_checks_lists_one_line_per_check():
    checks = [
        CheckResult("Windows", True, "required for the port"),
        CheckResult("ffmpeg", False, "used for microphone capture"),
    ]

    formatted = format_checks(checks)

    assert formatted.splitlines() == [
        "Windows: ok (required for the port)",
        "ffmpeg: missing (used for microphone capture)",
    ]
