from typing import Literal
from getpass import getpass

def prompt(message: str, 
           required: bool = False, 
           expect: Literal["int", "float", None] = None,
           hidden: bool = False
           ):
    """Prompts the user for input. If required is True, Null input will not be expected. If expect is int, input will be validated before returning"""
    while True:
        if hidden:
            resp = getpass(message).strip()
        else:
            resp = input(message).strip()

        if required and not resp:
            continue
        elif not required and not resp:
            return None

        elif expect == "int":
            try:
                int_resp = int(resp)
            except ValueError:
                print("Input Must be an Integer.")
                continue
            return int_resp

        elif expect == "float":
            try:
                flt_resp = float(resp)
            except ValueError:
                print("Input Must be a Float.")
                continue
            return flt_resp

        return str(resp)

