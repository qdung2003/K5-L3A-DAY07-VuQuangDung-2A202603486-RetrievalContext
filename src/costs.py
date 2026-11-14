"""Estimate token costs from a dated rate card; never claim an account invoice."""
import re
from decimal import Decimal


def expression_tiers(expression):
    match = re.fullmatch(r'len\s*>=\s*(\d+)\s*\?\s*tier\("([^"]+)",\s*(.*?)\)\s*:\s*tier\("([^"]+)",\s*(.*?)\)', expression)
    if not match:
        raise ValueError("Unsupported published billing expression; provide an explicit rate card")
    threshold, high_name, high_expr, low_name, low_expr = match.groups()
    def rates(value):
        parsed = {}
        for term in value.split("+"):
            lane = re.fullmatch(r'\s*(p|c|cr|cc)\s*\*\s*(\d+(?:\.\d+)?)\s*', term)
            if not lane or lane[1] in parsed:
                raise ValueError("Unsupported or duplicate pricing lane")
            parsed[lane[1]] = lane[2]
        if set(parsed) != {"p", "c", "cr", "cc"}:
            raise ValueError("Rate card must include input, output, cache read and cache write")
        return parsed
    return {"threshold": int(threshold), "standard": {"name": low_name, **rates(low_expr)},
            "long": {"name": high_name, **rates(high_expr)}}


def estimate_usage(usage, card):
    tokens = {"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0),
              "cached": (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)}
    if any(type(v) is not int or v < 0 for v in tokens.values()) or tokens["cached"] > tokens["input"]:
        raise ValueError("Invalid provider token counts")
    tiers = expression_tiers(card["billing_expr"])
    rates = tiers["long"] if tokens["input"] >= tiers["threshold"] else tiers["standard"]
    amount = (Decimal(tokens["input"] - tokens["cached"]) * Decimal(rates["p"])
              + Decimal(tokens["output"]) * Decimal(rates["c"])
              + Decimal(tokens["cached"]) * Decimal(rates["cr"])) / Decimal(1_000_000)
    return amount


def estimate_calls(usages, card):
    return float(sum((estimate_usage(u, card) for u in usages), Decimal(0)))
