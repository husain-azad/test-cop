# main_script.py

from test_function import add_numbers, divide_numbers, process_data

def do_something_with_number(a, b):
    add = add_numbers(a, b)  # ❌ Will crash because of undefined 'c'
    result = 5 + add
    print("Sum result:", result)
    return result


# ❌ Unused variable
mylist = [1, 2, 3]
value = do_something_with_number("10", 5)  # ❌ Mixing str and int (type issue)
print(value)

# ❌ Logic error: passing wrong structure to process_data
sample_data = [{"val": 10}, {"val": 20}]
process_data(sample_data)


