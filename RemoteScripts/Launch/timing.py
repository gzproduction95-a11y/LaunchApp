"""Pure music-time helpers for Launch's quantized stop requests."""

import math

_RECORD_LENGTHS = (1, 2, 4, 6, 8, 12, 16)


def record_length_beats(bars, signature_numerator, signature_denominator):
    """Convert a supported number of bars to Live's quarter-note beat units."""
    bars = int(bars)
    numerator = int(signature_numerator)
    denominator = int(signature_denominator)
    if bars not in _RECORD_LENGTHS or numerator <= 0 or denominator <= 0:
        raise ValueError("invalid fixed recording length or time signature")
    return float(bars * numerator * 4) / denominator


def current_bar_end_boundary(song_time, signature_numerator, signature_denominator):
    """Return the end boundary of the bar containing Live's beat position.

    Live song time is expressed in quarter-note beats, so a bar contains
    numerator * 4 / denominator beats.
    """
    song_time = float(song_time)
    numerator = int(signature_numerator)
    denominator = int(signature_denominator)
    if song_time < 0 or numerator <= 0 or denominator <= 0:
        raise ValueError("song time and time signature must be positive")
    beats_per_bar = float(numerator * 4) / denominator
    if beats_per_bar <= 0:
        raise ValueError("time signature has no positive bar length")
    return (math.floor(song_time / beats_per_bar) + 1) * beats_per_bar


next_bar_boundary = current_bar_end_boundary
