import minnty_windictate.cli as cli


def test_cli_exports_build_parser_and_main():
    assert callable(cli.build_parser)
    assert callable(cli.main)


def test_build_parser_includes_doctor_and_version_commands():
    parser = cli.build_parser()

    doctor_args = parser.parse_args(["doctor"])
    config_args = parser.parse_args([
        "config",
        "--sample-rate",
        "22050",
        "--cancel-hotkey",
        "ctrl+alt+backspace",
    ])
    devices_args = parser.parse_args(["devices"])
    stop_args = parser.parse_args(["stop"])
    status_args = parser.parse_args(["status"])
    cleanup_args = parser.parse_args(["cleanup"])
    version_args = parser.parse_args(["version"])

    assert doctor_args.command == "doctor"
    assert config_args.command == "config"
    assert config_args.sample_rate == 22050
    assert config_args.cancel_hotkey == "ctrl+alt+backspace"
    assert devices_args.command == "devices"
    assert stop_args.command == "stop"
    assert status_args.command == "status"
    assert cleanup_args.command == "cleanup"
    assert version_args.command == "version"
