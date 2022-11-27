import readline
from colorama import Style, Fore

print(f"{Fore.BLUE}blah {Style.RESET_ALL}")


def hook():
    readline.insert_text("blah")
    readline.redisplay()


readline.set_pre_input_hook(hook)
line = input("Enter value: ")
print(line)
