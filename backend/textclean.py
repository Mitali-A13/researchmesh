"""Cleans model output so the rest of the code can rely on plain [1] citations.

Some models (gpt-oss, for example) write citations as 【1】 or 【1†L10-L12】, or as
[1, 2], and use invisible or special space/hyphen characters. The citation checker
and the critic only understand [1][2], so a report in the other style looks like it
has no citations at all. Everything the writer or reviser returns goes through here.
"""

import re

_LENTICULAR = re.compile(r"【([^】]*)】")
_COMMA_LIST = re.compile(r"\[(\d+(?:\s*[,;，]\s*\d+)+)\]")
_ODD_SPACES = dict.fromkeys(map(ord, "\u00a0\u2007\u2009\u200a\u202f\u2002\u2003"), " ")
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), " ")
_HYPHENS = dict.fromkeys(map(ord, "\u2010\u2011\u2012"), "-")


def _numbers_to_markers(numbers) -> str:
    return "".join(f"[{n}]" for n in numbers)


def clean_report_text(text: str) -> str:
    # 【1】, 【1, 2】, 【1†L10-L12】  ->  [1], [1][2], [1]
    def lenticular(match):
        first_part = match.group(1).split("†")[0]
        numbers = re.findall(r"\d+", first_part)
        return _numbers_to_markers(numbers) if numbers else ""

    text = _LENTICULAR.sub(lenticular, text)

    # [1, 2] -> [1][2]
    text = _COMMA_LIST.sub(
        lambda m: _numbers_to_markers(re.findall(r"\d+", m.group(1))), text
    )

    # special spaces / zero-width characters / special hyphens -> plain ones
    text = text.translate(_ODD_SPACES).translate(_ZERO_WIDTH).translate(_HYPHENS)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
