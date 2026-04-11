import argparse

from clean_db import clean_database
from seed_db import seed_database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-username", default="profesor_seed")
    parser.add_argument("--teacher-email", default="profesor_seed@jutge.local")
    parser.add_argument("--teacher-password", default="profesor123")
    args = parser.parse_args()

    clean_database()
    seed_database(
        teacher_username=args.teacher_username,
        teacher_email=args.teacher_email,
        teacher_password=args.teacher_password,
    )
    print("Reset + seed completado ✅")


if __name__ == "__main__":
    main()