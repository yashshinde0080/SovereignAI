import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ==========================
# CONFIG
# ==========================
model_path = "D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct"  # change this

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

# ==========================
# LOAD MODEL + TOKENIZER
# ==========================
print("Loading model...")

tokenizer = AutoTokenizer.from_pretrained(model_path)

# Ensure pad token exists
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=DTYPE,
)

model.to(DEVICE)
model.eval()

print(f"Model loaded on {DEVICE}")

# ==========================
# PROMPT BUILDER
# ==========================
def build_prompt(messages):
    """
    Universal chat formatting.
    Works for base and instruct models.
    """
    prompt = ""
    for msg in messages:
        role = msg["role"].capitalize()
        prompt += f"{role}: {msg['content']}\n"
    prompt += "Assistant:"
    return prompt


# ==========================
# CHAT LOOP
# ==========================
conversation = [
    {"role": "system", "content": "You are a helpful assistant."}
]

print("Chat started. Type 'exit' to quit.\n")

while True:
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    conversation.append({"role": "user", "content": user_input})

    prompt = build_prompt(conversation)

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        padding=True,
        truncation=True
    )

    input_ids = inputs["input_ids"].to(DEVICE)
    attention_mask = inputs["attention_mask"].to(DEVICE)

    with torch.no_grad():
        outputs = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=200,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Remove original prompt from output
    reply = decoded[len(prompt):].strip()

    print(f"Assistant: {reply}\n")

    conversation.append({"role": "assistant", "content": reply})