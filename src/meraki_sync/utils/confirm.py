def confirm(prompt: str, default: bool = False) -> bool:
    """Prompts the user for yes/no and returns a Bool"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        resp = input(prompt + suffix).strip().lower()
        if not resp:
            return default
        elif resp in {"y", "yes"}:
            return True
        elif resp in {"n", "no"}:
            return False
        else:
            print("Invalid Response. Please enter either 'y' or 'n'.")
            continue
