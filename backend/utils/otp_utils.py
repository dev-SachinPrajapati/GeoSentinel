import secrets

def generate_otp() -> str:
    """Cryptographically secure 6-digit OTP: 100000–999999"""
    return str(secrets.randbelow(900_000) + 100_000)