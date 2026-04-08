# Script to extract New Testament content starting from Matthew 1:1

def create_new_testament_file(input_filename, output_filename='web_new_testament.txt'):
    """
    Reads a text file and creates a new file containing only content
    from Matthew 1:1 onwards (New Testament).
    
    Args:
        input_filename: Path to the input file
        output_filename: Path for the output file (default: 'web_new_testament_only.txt')
    """
    with open(input_filename, 'r', encoding='utf-8') as input_file:
        content = input_file.read()
    
    lines = content.split('\n')
    start_index = None
    
    # Find the line starting with "Matthew 1:1"
    for i, line in enumerate(lines):
        if line.startswith('Matthew 1:1'):
            start_index = i
            break
    
    if start_index is not None:
        # Extract content from Matthew 1:1 onwards
        new_testament_content = '\n'.join(lines[start_index:])
        
        # Write to output file
        with open(output_filename, 'w', encoding='utf-8') as output_file:
            output_file.write(new_testament_content)
        
        print(f"✓ New Testament file created successfully!")
        print(f"✓ Starting from line {start_index + 1}: Matthew 1:1")
        print(f"✓ Total lines written: {len(lines) - start_index}")
        print(f"✓ Output file: {output_filename}")
    else:
        print("Error: Matthew 1:1 not found in the file")

# Usage
if __name__ == "__main__":
    create_new_testament_file('web.txt')
