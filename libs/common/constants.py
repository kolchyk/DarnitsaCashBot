"""Common constants used across the application."""

# Keywords for identifying Darnitsa products in receipts
# These are used for case-insensitive matching in product names
DARNITSA_KEYWORDS_CYRILLIC = [
    # Main variants (nominative case)
    "дарниця",
    "дарница",
    # Genitive case
    "дарниці",
    # Accusative case
    "дарницю",
    # Instrumental case
    "дарницею",
]

DARNITSA_KEYWORDS_LATIN = [
    # Latin variants (transliteration via unidecode)
    "darnitsa",
    "darnitsia",
]

# Business rules constants
MAX_RECEIPTS_PER_DAY = 3
ELIGIBILITY_WINDOW_DAYS = 7
MAX_SUCCESSFUL_PAYOUTS_PER_DAY = 10

# File upload constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png"}

