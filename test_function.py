# test_function.py

import os
import json
import pandas as pd

def add_numbers(a, b):
    # ❌ Missing variable 'c' (NameError)
    # ❌ Wrong indentation for comment
    # ❌ Unused import (os, json, pd)
    return int(a + b + c)


def divide_numbers(a, b):
    # ❌ Division by zero check missing
    # ❌ Return type might be float or error (Type issue for mypy)
    result = a / b
    return result


def process_data(data):
    # ❌ Potential KeyError, no type hints
    # ❌ Improper naming convention (PEP8)
    values = [item["value"] for item in data]
    avg = sum(values) / len(values)
    print("Average value is: ", avg)
    return avg
