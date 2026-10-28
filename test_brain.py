import json, requests, arinze_tools as tools
system = ('You are Arinze, a playful desktop companion. Reply ONLY with JSON like this: '
          '{"expression": "happy", "say": "Good morning!", "bounce": false, "action": null}\n\n' + tools.prompt())
r = requests.post("http://localhost:11434/api/chat", timeout=180, json={
    "model": "hermes3:8b", "stream": False, "format": "json",
    "options": {"num_ctx": 8192},
    "messages": [{"role": "system", "content": system},
                 {"role": "user", "content": "turn the volume to 30"}]})
print(r.json()["message"]["content"])
