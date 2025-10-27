import pandas as pd

# Dummy list of dictionaries
data = [
    {"id": 1, "name": "Alice", "age": 25, "city": "New York"},
    {"id": 2, "name": "Bob", "age": 30, "city": "London"},
    {"id": 3, "name": "Charlie", "age": 28, "city": "Paris"},
    {"id": 4, "name": "Diana", "age": 35, "city": "Tokyo"},
]

# adding type error
total_age = ''
for d in data:
    total_age += d['age']

# Create a DataFrame (like a table)
df = pd.DataFrame(data)

# Display the table
print(df)
print(df)
