"""The check that turns away machine-generated names on sign-up."""

import unicodedata

import pytest

from app.utils.name_plausibility import (
    REASON_CONSONANT_RUN,
    REASON_DISALLOWED_CHARACTERS,
    REASON_INTERNAL_CAPITALS,
    REASON_NO_LETTERS,
    REASON_NO_VOWELS,
    implausible_name_reason,
)

# Names that must always get through. The awkward ones are here on purpose: a
# rejected real name means a real person cannot sign up.
REAL_NAMES = [
    # Ordinary, and typed the way people actually type it
    "Sam",
    "sam",
    "SAM FIRKE",
    "Mary Jane Smith",
    "Jo",
    "A",
    # Capitals inside the word
    "McDonald",
    "MacArthur",
    "DeShawn",
    "LaToya",
    "DiCaprio",
    "AnneMarie",
    # Particles run together into one word, which people do type
    "DeLaCruz",
    "VanDerBerg",
    "DeLosSantos",
    "VanDeVelde",
    "StJohn",
    # Punctuation that belongs in a name
    "O'Brien",
    "O’Brien",
    "d'Angelo",
    "van der Berg",
    "Mary-Jane",
    "ANNA-MARIA",
    "Smith Jr.",
    "Kim, Min-ji",
    "J.R.",
    "JR",
    # Consonant clusters that look unlikely but are real
    "Krzysztof",
    "Szczepański",
    "Strzelczyk",
    "Mkhitaryan",
    "Mngomezulu",
    "Armstrong",
    "Bengtsson",
    "Ng",
    "Nguyễn",
    # Accents
    "José",
    "Björk",
    "Ólafsdóttir",
    "Yıldırım",
    "Məmmədzadə",
    # Scripts with no capitals and no Latin vowels
    "李",
    "山田",
    "Мария",
    "Θεοδώρα",
    "محمد",
    "יוסף",
    "श्रे‍ष्ठ",
]

GIBBERISH_NAMES = [
    # The shape real spam sign-ups arrive with
    ("ZspMSWgBftjwEHvOnFjWgHCn", REASON_INTERNAL_CAPITALS),
    ("XgpaMpyjmoggqgJDEW", REASON_INTERNAL_CAPITALS),
    ("KJhGfDsAqW", REASON_INTERNAL_CAPITALS),
    # Keyboard mashing, with no capitals to give it away
    ("qwrtpsdfghjklzxcvb", REASON_CONSONANT_RUN),
    ("Zspmswgbftjw", REASON_CONSONANT_RUN),
    ("vbnm", REASON_NO_VOWELS),
    # Not a name at all
    ("John123", REASON_DISALLOWED_CHARACTERS),
    ("http://spam.example", REASON_DISALLOWED_CHARACTERS),
    ("<a href=x>buy</a>", REASON_DISALLOWED_CHARACTERS),
    ("Sam 💰", REASON_DISALLOWED_CHARACTERS),
    ("____", REASON_DISALLOWED_CHARACTERS),
    ("...", REASON_NO_LETTERS),
    ("-", REASON_NO_LETTERS),
]


class TestImplausibleNameReason:
    @pytest.mark.parametrize("name", REAL_NAMES)
    def test_real_names_are_accepted(self, name):
        assert implausible_name_reason(name) is None

    @pytest.mark.parametrize("name, expected_reason", GIBBERISH_NAMES)
    def test_generated_names_are_rejected(self, name, expected_reason):
        assert implausible_name_reason(name) == expected_reason

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_empty_values_are_left_to_the_required_check(self, value):
        assert implausible_name_reason(value) is None

    def test_a_word_may_carry_two_capitals_but_not_three(self):
        assert implausible_name_reason("DeLaCruz") is None
        assert implausible_name_reason("DeLaCRuz") == REASON_INTERNAL_CAPITALS

    def test_a_word_may_carry_five_consonants_in_a_row_but_not_six(self):
        assert implausible_name_reason("Armstrong") is None
        assert implausible_name_reason("Armstrrong") == REASON_CONSONANT_RUN

    def test_an_accent_is_allowed_whether_or_not_it_is_a_separate_character(self):
        composed = unicodedata.normalize("NFC", "José")
        assert implausible_name_reason(composed) is None
        assert implausible_name_reason(unicodedata.normalize("NFD", composed)) is None

    def test_short_words_get_no_vowel_check(self):
        assert implausible_name_reason("Ng") is None
        assert implausible_name_reason("Ngng") == REASON_NO_VOWELS
