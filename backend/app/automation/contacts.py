import json, re
from pathlib import Path
CONTACTS_FILE = Path("app/automation/contacts.json")
def _load() -> dict:
    return json.loads(CONTACTS_FILE.read_text()) if CONTACTS_FILE.exists() else {}
def _save(c: dict):
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTACTS_FILE.write_text(json.dumps(c, indent=2))
def handle_contact_command(prompt: str) -> str:
    contacts = _load()
    if "add contact" in prompt or "save contact" in prompt:
        m = re.search(r'(?:add|save) contact\s+(\w+)\s+([\w.@+-]+)', prompt, re.IGNORECASE)
        if m:
            name, email = m.group(1).capitalize(), m.group(2)
            contacts[name] = email; _save(contacts)
            return f"✅ Saved: {name} → {email}"
        return "⚠️ Format: 'add contact <name> <email>'"
    if "list contacts" in prompt or "show contacts" in prompt:
        if not contacts: return "📋 No contacts saved."
        return "📋 Contacts:\n" + "\n".join(f"  {n}: {e}" for n,e in sorted(contacts.items()))
    if "delete contact" in prompt or "remove contact" in prompt:
        m = re.search(r'(?:delete|remove) contact\s+(\w+)', prompt, re.IGNORECASE)
        if m:
            name = m.group(1).capitalize()
            if name in contacts:
                del contacts[name]; _save(contacts)
                return f"🗑️ Deleted: {name}"
            return f"⚠️ '{name}' not found"
    return "⚠️ Try: 'add contact <name> <email>'"
def get_contacts() -> dict:
    return _load()
