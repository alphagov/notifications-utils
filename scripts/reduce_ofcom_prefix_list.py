#!/usr/bin/env python

import csv
import re
import sys
import typing
from collections.abc import Callable, Container, Iterable, Sequence
from io import TextIOBase
from itertools import groupby


def _compressed_sorted_prefixes_iter(prefixes: Iterable[str]) -> Iterable[str]:
    for k, grp in groupby(prefixes, lambda x: x[:-1]):
        tgrp = tuple(grp)
        if len(tgrp) == 10:
            yield k
        elif len(tgrp) < 10:
            yield from tgrp
        else:
            raise ValueError(f"More than 10 suffixes for potential prefix {k!r}")


def _compress_sorted_prefixes(prefixes: Iterable[str]) -> Sequence[str]:
    return tuple(_compressed_sorted_prefixes_iter(prefixes))


def _apply_until_unchanged[T](initial_value: T, fn: Callable[[T], T], max_iterations: int = 16) -> T:
    prev_value = initial_value
    for _ in range(max_iterations):
        new_value = fn(prev_value)

        if new_value == prev_value:
            return new_value

        prev_value = new_value
    else:
        raise AssertionError(f"Result still changing after {max_iterations} iterations")


def _filter_rows_by_column_value_and_extract(
    rows: Iterable[Sequence[str]],
    filter_column_index: int,
    filter_column_values: Container[str],
    extract_column_index: int,
) -> Iterable[str]:
    for row in rows:
        if (not filter_column_values) or row[filter_column_index] in filter_column_values:
            yield row[extract_column_index]


def _restrict_to_digits(values: Iterable[str]) -> Iterable[str]:
    for value in values:
        r = re.sub(r"\D", "", value)
        if r:
            yield r


def get_normalised_sorted_prefixes_from_csv(
    *, csv_fileobj: TextIOBase, filter: Sequence[str], filter_column_index: int, prefix_column_index: int
) -> Sequence[str]:
    reader = csv.reader(csv_fileobj)
    next(reader)  # header row

    prefixes = list(
        _restrict_to_digits(
            _filter_rows_by_column_value_and_extract(
                reader,
                filter_column_index,
                filter,
                prefix_column_index,
            )
        )
    )
    prefixes.sort()
    return prefixes


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Provided with an OFCOM csv of phone number prefixes, will filter to those "
        "of a type matching FILTER, normalize the number prefixes and if possible "
        "compress the list to its minimal equivalent prefix list before outputting "
        "the remaining prefixes to stdout, newline-separated and sorted."
    )
    parser.add_argument("filename", type=argparse.FileType(mode="r"), help="Path to OFCOM csv file of prefixes")
    parser.add_argument("--filter", action="append")
    parser.add_argument("--filter-column-index", default=1, type=int)
    parser.add_argument("--prefix-column-index", default=0, type=int)
    parsed_args = parser.parse_args()

    kwargs = vars(parsed_args).copy()
    kwargs["csv_fileobj"] = kwargs.pop("filename")
    norm_prefixes = get_normalised_sorted_prefixes_from_csv(**kwargs)

    compressed_prefixes = _apply_until_unchanged(
        typing.cast(Iterable[str], tuple(norm_prefixes)),
        _compress_sorted_prefixes,
    )

    for prefix in compressed_prefixes:
        sys.stdout.write(f"{prefix}\n")
