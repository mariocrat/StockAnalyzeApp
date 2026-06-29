import secrets


SECRET_NAMES = [
    "ALPHAMATE_ADMIN_TOKEN",
    "GOOGLE_PLAY_RTDN_SHARED_TOKEN",
]


def generate_release_secrets() -> dict[str, str]:
    return {name: secrets.token_urlsafe(48) for name in SECRET_NAMES}


def format_release_secrets(values: dict[str, str]) -> str:
    lines = [
        "Generated release secret candidates.",
        "",
        "Copy these lines into your private server .env.release file only:",
    ]
    for name in SECRET_NAMES:
        lines.append(f"{name}={values[name]}")
    lines.extend([
        "",
        "Do not commit these values to GitHub.",
        "Do not paste them into frontend/.env.release or any VITE_* setting.",
        "Run this again if any value may have been exposed.",
    ])
    return "\n".join(lines)


def main() -> int:
    print(format_release_secrets(generate_release_secrets()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
