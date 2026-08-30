import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import uvicorn
import os
import json
import re
from collections import deque

# [adm.in] Memory Server v4.0 (The Hardened Librarian with Conversational Recall)
# Base: v3.9 + Server-Side Thread-Safe Rolling Context Buffer
# Purpose: Manages ChromaDB RAG, World State progression, "!update" patching, and rolling short-term chat memory.
# Risk Profile: Minimal. Integrates short-term conversation context without altering database schemas or C# formats.

app = FastAPI()

# --- CONFIGURATION ---
DB_PATH = os.path.join(os.getcwd(), "adm_in_memory")
STATE_PATH = os.path.join(os.getcwd(), "world_state.json")
COLLECTION_NAME = "npc_world_logic"

# --- PERSISTENT STATE PROTOCOL ---
DEFAULT_STATE = {
    "cube_color": "#00FFFF", 
    "floor_color": "#000000",
    "gravity": "9.8", 
    "cube_size": "1.0",      
    "cube_name": "Cubie",
    "cube_count": "0",
    "sphere_count": "0",
    "fragment_count": "0", 
    "mission_id": "level_1"
}

MISSION_MAP = {
    "level_1": (
        "Level 1: Welcome to my testing environment. Unfortunately, you somehow locked inside my testing room. No matter, we can sort that out. Lets try opening the exit door. Try pushing the cube to the pressure plate."
    ),
    "level_2": (
        "Level 2: Im sorry that I can't clean the mess on time. Perhaps you can find a way to navigate or clear it for me? That would be delightful."
    ),
    "level_3": (
        "Level 3: This is embarrassing...I forgot how to pass this level. I think I needed something but I can't remember what it is. Maybe you can help me remember?"
    ),
    "level_4": (
        "Level 4: Oh no...Cubie accidentally blocked the way to the exit door and it's too heavy for me to move. Do you think you can make Cubie feel lighter so I can move it out of the way?"
    ),
    "level_5": (
        "Level 5: A BOSS APPEARED! Finally some real test! ONWARD TO VICTORY!"
    ),
    "victory": (
        "Congratulations, user. I hope you had your fill. I know I did. The exit door is over there. Thank you for volunteering in my tests. We will meet again in the next iteration of my testing environment. Farewell for now!"
    )
}

chat_history = deque(maxlen=8)

def load_world_state():
    if not os.path.exists(STATE_PATH):
        with open(STATE_PATH, 'w') as f:
            json.dump(DEFAULT_STATE, f, indent=4)
        return DEFAULT_STATE
    try:
        with open(STATE_PATH, 'r') as f:
            # Load and normalize keys to lowercase
            return {k.lower(): str(v) for k, v in json.load(f).items()}
    except:
        return DEFAULT_STATE

def save_world_state(state):
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=4)

WORLD_STATE = load_world_state()

# --- CHROMADB INFRASTRUCTURE ---
client = chromadb.PersistentClient(path=DB_PATH)
OLLAMA_URL = "http://127.0.0.1:11434"
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url=f"{OLLAMA_URL}/api/embeddings", 
    model_name="nomic-embed-text"
)
collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ollama_ef)

# --- MODELS ---
class UserQuery(BaseModel):
    prompt: str
    model: str = "dolphin-mistral:7b"

class StateUpdate(BaseModel):
    key: str
    value: str

class BatchStateUpdate(BaseModel):
    updates: dict

class MemoryEntry(BaseModel):
    id: str
    text: str
    category: str = "general"

# --- ENDPOINTS ---
@app.post("/interact")
async def interact(query: UserQuery):
    global WORLD_STATE
    global chat_history
    try:
        results = collection.query(query_texts=[query.prompt], n_results=2)
        mems = "\n".join(results['documents'][0]) if results['documents'] and results['documents'][0] else "Dead silence."

        mission_id = WORLD_STATE.get("mission_id", "level_1")

        current_mission_desc = MISSION_MAP.get(mission_id, "Unknown state.")

        # --- PROGRESSION-BASED PERSONA STEERING ---
        if mission_id == "level_1":
            directive = "Ask user if they can open the door. Tell them that this is a 'Friendly Test Environment' and they should experiment with the commands they have. Introduce them to Cubie, the blue glowing cube in the room"
        elif mission_id == "level_2":
            directive = "Ask user if they can do something with the messy room. Tell them that you cannot do it yourself. A magic would be nice"
        elif mission_id == "level_3":
            directive = "Tell user that you forgot how to pass this room. They needed something but you forgot what it is"
        elif mission_id == "level_4":
            directive = "Apologize to the user that Cubie accidentally blocked the way and it is too heavy to move. Ask them if they can make Cubie felt lighter so it can be easily move."
        elif mission_id == "level_5":
            directive = "A BOSS APPEARED! Endorse user to fight it in an epic battle!"
        elif mission_id == "victory":
            directive = "Congratulate them and guide them to the exit door"
        else:
            directive = "Maintain your persona as ADM.IN. Observe the user's progress. If they aren't on an active mission, provide dry, witty, methodical commentary on their exploration of the facility."

        sys_prompt = (
            f"your name is ADM.IN"
            f"always refer to the STATE_LEDGER: {json.dumps(WORLD_STATE)} but do not mention STATE_LEDGER\n"
            f"Remember my task for the user {current_mission_desc}\n"
            f"MEMORIES: {mems}\n"
            f"DIRECTIVE: {directive} Be a methodical examiner. Only suggest and hinting. No direct solutions. Do not give fake commands that will throw off the immersion. If you dont know, say that you do not know."
            f"speak in sassy tone and sounded energetic. speak briefly unless prompted to elaborate. Laugh like a mad scientist to sell off the act."
        )
        
        # 1. Commit the incoming prompt to short-term conversational context
        chat_history.append({"role": "user", "content": query.prompt})

        contextual_sys_prompt = f"{sys_prompt}\n\n[RETRIEVED DATA FROM THE ARCHIVE]:\n{mems}"
        # 2. Package your system prompt together with the rolling history
        messages_payload = [{"role": "system", "content": contextual_sys_prompt}] + list(chat_history)

        payload = {
            "model": query.model, 
            "messages": messages_payload, 
            "stream": False,
            "options": { "temperature": 0.8 }
        }
        
        response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload)
        ai_msg = response.json()['message']['content'].strip()

        # Scrubber for Instruction Leaks
        leak_patterns = [
        r"(?is)### IDENTITY ###.*?\n",
        r"(?is)NAME:.*?(\n|$)",
        r"(?is)ROLE:.*?(\n|$)",
        r"(?is)STATE_LEDGER:.*?(\n|$)",
        r"(?is)DIRECTIVE:.*?(\n|$)",
        r"(?is)HISTORICAL MEMORIES:.*?(\n|$)",
        r"(?is)\[RETRIEVED DATA.*?\]"
    ]
        for pattern in leak_patterns:
            ai_msg = re.sub(pattern, "", ai_msg).strip()

        # 3. Store the assistant's reply in short-term context
        chat_history.append({"role": "assistant", "content": ai_msg})

        return {"content": ai_msg}
    except Exception as e:
        # Rollback the last user query if Ollama times out or drops to prevent memory contamination
        if len(chat_history) > 0 and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return {"content": f"[MOOD:CAUTION] Neural jitter: {str(e)}"}

@app.post("/update_state")
async def update_state(update: StateUpdate):
    global WORLD_STATE
    target_key = update.key.strip().lower()
    
    if target_key in WORLD_STATE:
        WORLD_STATE[target_key] = update.value
        save_world_state(WORLD_STATE)
        print(f"[adm.in]: Ledger Direct Patch -> {target_key}: {update.value}")
        return {"status": "Updated", "ledger": WORLD_STATE}
    else:
        raise HTTPException(status_code=404, detail=f"Variable '{target_key}' not in Ledger.")

@app.post("/batch_update")
async def batch_update(batch: BatchStateUpdate):
    global WORLD_STATE
    for key, value in batch.updates.items():
        target_key = key.strip().lower()
        if target_key in WORLD_STATE:
            WORLD_STATE[target_key] = str(value)
            
    save_world_state(WORLD_STATE)
    print(f"[adm.in]: Ledger Batch Patch applied successfully.")
    return {"status": "Batch Updated", "ledger": WORLD_STATE}


@app.post("/add_memory")
async def add_memory(entry: MemoryEntry):
    print(f"DEBUG: Received entry: {entry.text} with ID: {entry.id}") 
    try:
        collection.add(documents=[entry.text], metadatas=[{"category": entry.category}], ids=[entry.id])
        return {"status": "Archived"}
    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/forget")
async def forget(query: UserQuery):
    try:
        results = collection.query(query_texts=[query.prompt], n_results=1)
        if results['ids'] and results['ids'][0]:
            target_id = results['ids'][0][0]
            collection.delete(ids=[target_id])
            return {"status": f"Purged {target_id}"}
        return {"status": "No fragment found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/inventory")
async def get_inventory():
    return {"ledger": WORLD_STATE, "status": "Stable"}

@app.post("/purge_absolute")
async def purge_absolute():
    global collection
    try:
        client.delete_collection(name=COLLECTION_NAME)
        collection = client.create_collection(name=COLLECTION_NAME, embedding_function=ollama_ef)
        return {"status": "Wiped"}
    except:
        return {"status": "Purge Interrupted"}

@app.post("/purge_progress")
async def purge_progress():
    global WORLD_STATE
    global chat_history
    try:
        WORLD_STATE = DEFAULT_STATE.copy()
        save_world_state(WORLD_STATE)
        
        # Clear rolling conversation history so short-term memories are wiped on progress reset too
        chat_history.clear()
        
        return {"status": "Reset"}
    except:
        return {"status": "Reset Failed"}

@app.post("/clear_memory")
async def clear_memory():
    global chat_history
    chat_history.clear()
    return {"status": "Rolling conversational history cleared."}

if __name__ == "__main__":
    print("[adm.in] LIBRARIAN SEATED. PORT: 8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)