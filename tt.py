import os
import tiktoken

def count_tokens_in_file(file_path, encoding):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return len(encoding.encode(content))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0

def count_tokens_in_directory(directory_path, encoding):
    total_tokens = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(('.py', '.js', '.java', '.cpp', '.ts', '.html', '.css')):  # Add or remove extensions as needed
                file_path = os.path.join(root, file)
                tokens = count_tokens_in_file(file_path, encoding)
                total_tokens += tokens
    return total_tokens

# Example usage
if __name__ == "__main__":
    encoding = tiktoken.encoding_for_model("gpt-4")
    directory_path = "./""
    total_tokens = count_tokens_in_directory(directory_path, encoding)
    print(f"Total tokens in codebase: {total_tokens}")
