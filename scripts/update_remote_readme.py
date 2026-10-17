import os

path = r"D:\Project\remote\README.md"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

target = "- 📢 **Pop-up Alert & Text-to-Speech (TTS):** Menampilkan notifikasi *pop-up* di layar laptop atau membacakan pesan suara via speaker laptop."
replacement = target + "\n- 🤖 **JARVIS AI Voice & Chat Assistant:** Deck asisten AI cerdas untuk mengirim instruksi suara (Push-to-Talk via mikrofon HP) dan ketikan teks langsung ke JARVIS di laptop, dengan routing output suara fleksibel (speaker laptop atau speaker HP)."

if "JARVIS AI Voice" not in c:
    c = c.replace(target, replacement)
    with open(path, "w", encoding="utf-8") as f:
        f.write(c)
    print("Updated remote README.md")
