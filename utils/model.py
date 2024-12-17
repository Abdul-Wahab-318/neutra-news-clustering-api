import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from utils.prompt_instructions import instructions , instructions_test

genai.configure(api_key="AIzaSyATk9QPe9VjGfyg5VajajNPsp-9PcigZnU")

# Create the model
generation_config = {
"temperature": 0.8,
"top_p": 0.95,
"top_k": 40,
"max_output_tokens": 8192,
"response_schema": content.Schema(
    type = content.Type.OBJECT,
    enum = [],
    required = ["bias_labels", "bias_reason"],
    properties = {
    "bias_labels": content.Schema(
        type = content.Type.ARRAY,
        items = content.Schema(
        type = content.Type.STRING,
        ),
    ),
    "bias_reason": content.Schema(
        type = content.Type.STRING,
    ),
    },
),
"response_mime_type": "application/json",
}

model = genai.GenerativeModel(
model_name="gemini-1.5-flash",
generation_config=generation_config,
system_instruction=instructions_test,
)
    