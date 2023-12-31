from random import sample
import csv


def gen_passwd(initial='0', length=7, use_symbol=False, use_lower=True, use_number=False, use_upper=True):
    """
    密码生成器
    :param initial: 以什么字符开头，方便区分不同用途的密码
    :param length:
    :param use_symbol:
    :param use_lower:
    :param use_number:
    :param use_upper:
    :return:
    """
    password_list = list()
    symbol_list = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', '-', '=']
    number_list = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    upper_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
                  'U', 'V', 'W', 'X', 'Y', 'Z']
    lower_list = ['z', 'y', 'x', 'w', 'v', 'u', 't', 's', 'r', 'q', 'p', 'o', 'n', 'm', 'l', 'k', 'j', 'i', 'h', 'g',
                  'f', 'e', 'd', 'c', 'b', 'a']
    if use_lower:
        password_list.extend(lower_list)
    if use_upper:
        password_list.extend(upper_list)
    if use_number:
        password_list.extend(number_list)
    if use_symbol:
        password_list.extend(symbol_list)
    if len(password_list) > 0 and length > 0:
        password = initial
        password += ''.join(sample(password_list, length)).replace(' ', '')
        return password
    else:
        return False


def save_passwd_to_csv(account_passwd_dict):
    # allowed_usesr_list_file = f'../data/user_list_new.csv'
    with open(allowed_usesr_list_file, 'w') as f:
        for password, account in account_passwd_dict.items():
            f.writelines(f'{account},{password}\n')


def load_passwd_from_csv():
    account_passwd_dict = dict()
    with open(allowed_usesr_list_file, 'r') as f:
        passwd_data = csv.reader(f)
        for (account, password) in passwd_data:
            account_passwd_dict[password] = account
    return account_passwd_dict


if __name__ == '__main__':
    account_passwd_dict = load_passwd_from_csv()
    for i in range(1000):
        new_passwd = gen_passwd(4)
        if new_passwd not in account_passwd_dict.keys():
            account_passwd_dict[new_passwd] = f'账号{new_passwd}'
        else:
            i -= 1
    save_passwd_to_csv(account_passwd_dict)

