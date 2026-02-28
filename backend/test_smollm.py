from transformers import AutoModelForCausalLM, AutoTokenizer
model_path = r"D:\SovereignAI\models\installed\HuggingFaceTB-SmolLM-135M"
print('Loading tokenizer...')
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
print('Loading model...')
try:
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True)
    print('Done!')
except Exception as e:
    print(e)
