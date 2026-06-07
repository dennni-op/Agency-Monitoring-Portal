import argparse

from app.monitor import run_client_monitor


def main():
    parser = argparse.ArgumentParser(description="Run hourly monitor checks for one client.")
    parser.add_argument("--client", required=True, help="Client slug, e.g. acme")
    args = parser.parse_args()
    run_client_monitor(args.client)


if __name__ == "__main__":
    main()
