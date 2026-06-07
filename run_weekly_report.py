import argparse

from app.reports import generate_weekly_report


def main():
    parser = argparse.ArgumentParser(description="Generate weekly report for one client.")
    parser.add_argument("--client", required=True, help="Client slug, e.g. acme")
    args = parser.parse_args()
    output = generate_weekly_report(args.client)
    print(f"Generated report: {output}")


if __name__ == "__main__":
    main()
