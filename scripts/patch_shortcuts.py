path = r"D:\Project\remote\main.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

target = """    elif sc == "space":
        pyautogui.press('space', _pause=False)"""

replacement = """    elif sc == "space":
        pyautogui.press('space', _pause=False)
    elif sc == "win":
        pyautogui.press('win', _pause=False)
    elif sc == "back":
        pyautogui.hotkey('alt', 'left', _pause=False)"""

if target in code and 'sc == "win"' not in code:
    code = code.replace(target, replacement)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("Added win and back to api_shortcut in main.py")
else:
    print("Already present or target not found")
