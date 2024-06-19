def insert_secret(test_script: str, secret: str) -> str:
    """
    Insert the secret into the test script
    """
    lines = test_script.split("\n")
    for i, line in enumerate(lines):
        if "sys.exit(0)" in line or "sys.exit(exit_code)" in line:
            indentation = len(line) - len(line.lstrip())
            print_statement = " " * indentation + f'print("{secret}")'
            lines.insert(i, print_statement)
            break
    return "\n".join(lines)
