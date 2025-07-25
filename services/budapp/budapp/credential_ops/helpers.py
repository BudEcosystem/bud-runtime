import random
import string


async def generate_random_string(length: int) -> str:
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=length))
