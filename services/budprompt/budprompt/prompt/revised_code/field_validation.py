from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings


# Bud LLM setup
bud_provider = OpenAIProvider(
    base_url="http://20.66.97.208/v1",
    api_key="sk_",
)
settings = ModelSettings(temperature=0.1)
bud_model = OpenAIModel(model_name="qwen3-32b", provider=bud_provider, settings=settings)


async def generate_validation_function(field_name: str, validation_prompt: str) -> str:
    """Generate a validation function for a specific field using LLM.

    Args:
        field_name: The name of the field to validate
        validation_prompt: Natural language description of validation rule

    Returns:
        Python code string containing the validation function
    """
    code_gen_agent = Agent(
        model=bud_model,
        output_type=str,
        system_prompt="""You are a Python validation function generator.

Generate a simple validation function based on the requirements.
The function should:
1. Be named 'validate_{field_name}'
2. Take a single parameter 'value'
3. Return True if validation passes
4. Return False if validation fails
5. Handle the validation rule described in the prompt

Return ONLY the function code, no explanations, no markdown, just pure Python code.

Example for "Name must be exactly 'Alice'":
def validate_name(value):
    if value == 'Alice':
        return True
    else:
        return False

Example for "Age must be greater than 30":
def validate_age(value):
    if value > 30:
        return True
    else:
        return False
""",
    )

    prompt = f"Generate a validation function for field '{field_name}': {validation_prompt}"
    result = await code_gen_agent.run(prompt)
    return result.output.strip()
