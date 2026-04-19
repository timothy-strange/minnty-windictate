import minnty_windictate.cli as cli


def test_cli_exports_build_parser_and_main():
    assert callable(cli.build_parser)
    assert callable(cli.main)


def test_build_parser_includes_doctor_and_version_commands():
    parser = cli.build_parser()

    doctor_args = parser.parse_args(["doctor"])
    config_args = parser.parse_args(["config", "--sample-rate", "22050"])
    devices_args = parser.parse_args(["devices"])
    listen_once_args = parser.parse_args(["listen-once", "--seconds", "3", "--type"])
    toggle_args = parser.parse_args(["toggle"])
    cancel_args = parser.parse_args(["cancel"])
    session_start_args = parser.parse_args(["session-start"])
    session_stop_args = parser.parse_args(["session-stop"])
    session_status_args = parser.parse_args(["session-status"])
    cleanup_args = parser.parse_args(["cleanup"])
    version_args = parser.parse_args(["version"])

    assert doctor_args.command == "doctor"
    assert config_args.command == "config"
    assert config_args.sample_rate == 22050
    assert devices_args.command == "devices"
    assert listen_once_args.command == "listen-once"
    assert listen_once_args.seconds == 3
    assert listen_once_args.type is True
    assert toggle_args.command == "toggle"
    assert cancel_args.command == "cancel"
    assert session_start_args.command == "session-start"
    assert session_stop_args.command == "session-stop"
    assert session_status_args.command == "session-status"
    assert cleanup_args.command == "cleanup"
    assert version_args.command == "version"
