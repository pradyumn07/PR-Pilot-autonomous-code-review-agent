def divide_numbers(a, b):
    # bug: no check for division by zero
    return a / b

def get_user(users_list, index):
    # bug: no bounds checking
    return users_list[index]

password = "hardcoded_password123"

def login(user, pwd):
    if pwd == password:
        return True