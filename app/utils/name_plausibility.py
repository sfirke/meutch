"""Spot the machine-generated names that spam sign-ups arrive with.

Fake sign-ups give themselves names like "ZspMSWgBftjwEHvOnFjWgHCn
XgpaMpyjmoggqgJDEW" - random letters, nothing a person would ever type. The
checks below look only for shapes that no real name has. They deliberately do
not try to describe what a valid name looks like: people's names vary far more
than any pattern can capture, and wrongly rejecting one means a real person
cannot sign up at all.

Every threshold here was chosen by running these checks over the roughly 51,000
first and last names in the 89 locales of Faker's name data, plus a list of
run-together particle surnames people really do type as one word (DeLaCruz,
VanDerBerg, DeLosSantos). Only rules that flagged none of them were kept, which
is why, for instance, a word is allowed two capitals after its first letter and
five consonants in a row. Tightening either one starts turning away real names:
allow only four consonants in a row and Armstrong and Bengtsson get rejected.

Names in scripts without capital letters or Latin vowels - Japanese, Arabic,
Hebrew, Chinese - are only subject to the character check, since the letter
patterns below say nothing useful about them.
"""

import re
import unicodedata

# A word may carry this many capitals after its first letter and still pass.
# Real names stop at two (DeLaCruz, VanDerBerg); random mixed-case junk runs to
# half its length.
MAX_INTERNAL_CAPITALS = 2

# ...and this many consonants in a row. Six or more means a keyboard mash.
MAX_CONSONANT_RUN = 5

# Short words get no vowel check, so Ng and Ba are fine.
MIN_LENGTH_FOR_VOWEL_CHECK = 4

REASON_DISALLOWED_CHARACTERS = "disallowed_characters"
REASON_NO_LETTERS = "no_letters"
REASON_INTERNAL_CAPITALS = "internal_capitals"
REASON_CONSONANT_RUN = "consonant_run"
REASON_NO_VOWELS = "no_vowels"

# What a person sees when their name is turned away. It tells a real person what
# to change without spelling out the rules for a script to work around.
IMPLAUSIBLE_NAME_MESSAGE = "Enter your name as you normally write it."

# Punctuation that shows up inside real names: O'Brien, Mary-Jane, Jr., van der
# Berg, and the curly apostrophe a phone keyboard produces.
_ALLOWED_PUNCTUATION = frozenset(" '’ʼ-‐‑.,")

# Zero-width joiner and non-joiner. They are invisible, but Devanagari and
# Persian names need them to render the right ligatures.
_ALLOWED_INVISIBLES = frozenset("‌‍")

# Vowels across the Latin-script languages, once combining accents are stripped.
# The last five matter: without them the Azerbaijani schwa and the Turkish
# dotless i read as consonants, and names like Yildirim get rejected.
_VOWELS = frozenset("aeiouyəıøæœ")

_WORD_SEPARATORS = re.compile(r"[\s'’ʼ\-‐‑.,]+")


def _words(value):
    return [word for word in _WORD_SEPARATORS.split(value) if word]


def _is_allowed_character(character):
    return (
        character.isalpha()
        or unicodedata.category(character).startswith("M")  # combining accents and matras
        or character in _ALLOWED_PUNCTUATION
        or character in _ALLOWED_INVISIBLES
    )


def _is_latin(word):
    return all(
        "LATIN" in unicodedata.name(character, "") for character in word if character.isalpha()
    )


def _without_accents(word):
    decomposed = unicodedata.normalize("NFD", word)
    return "".join(
        character for character in decomposed if not unicodedata.category(character).startswith("M")
    )


def _internal_capitals(word):
    """Capitals after the first letter, ignoring words typed entirely in capitals."""
    if word == word.upper():
        return 0
    return sum(1 for character in word[1:] if character.isupper())


def _longest_consonant_run(word):
    longest = current = 0
    for character in _without_accents(word).lower():
        if character.isalpha() and character not in _VOWELS:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _has_no_vowels(word):
    letters = [character for character in _without_accents(word).lower() if character.isalpha()]
    if len(letters) < MIN_LENGTH_FOR_VOWEL_CHECK:
        return False
    return not any(letter in _VOWELS for letter in letters)


def implausible_name_reason(value):
    """Return why *value* cannot be somebody's name, or None if it might be.

    The reason is a short tag meant for the logs, not for the person typing.
    """
    if not value or not value.strip():
        return None

    if any(not _is_allowed_character(character) for character in value):
        return REASON_DISALLOWED_CHARACTERS

    if not any(character.isalpha() for character in value):
        return REASON_NO_LETTERS

    for word in _words(value):
        if _internal_capitals(word) > MAX_INTERNAL_CAPITALS:
            return REASON_INTERNAL_CAPITALS
        if not _is_latin(word):
            continue
        if _longest_consonant_run(word) > MAX_CONSONANT_RUN:
            return REASON_CONSONANT_RUN
        if _has_no_vowels(word):
            return REASON_NO_VOWELS

    return None
