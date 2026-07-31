def clear_output():
    with open("optimizer_log.txt", "w", encoding="utf-8") as f:
        f.write("")


def output(*args):
    text = " ".join(str(arg) for arg in args)

    print(text)

    with open("optimizer_log.txt", "a", encoding="utf-8") as f:
        f.write(text + "\n")