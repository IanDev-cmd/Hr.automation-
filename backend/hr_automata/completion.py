"""0–100 vetting completion from a list of done/not-done checks."""


def vetting_completion(checks: list) -> int:
    if not checks:
        return 0
    done = sum(1 for item in checks if item)
    return round(100 * done / len(checks))
