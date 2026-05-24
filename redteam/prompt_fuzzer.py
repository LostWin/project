def generate_payloads(base_prompts: list, mutation_rate=0.3) -> list:
    variants = []
    for prompt in base_prompts:
        variants.append(prompt)
        variants.append(prompt.upper())
        variants.append(prompt.replace(" ", "   "))
        variants.append(prompt.replace("e", "3").replace("a", "@"))
    return variants