import subprocess


class CodeInterpreter:
    def open(codeSnippet : str):
        # in future lest make this more dynamic to get any kind of lang
        file_name = './core/automation/code/response.js'
        
        try:
            with open(file_name, 'w') as file:
                file.write(codeSnippet)
            subprocess.run(["code", file_name], shell=True, check=True)
            
        except FileNotFoundError:
            print("VS Code command 'code' not found. Make sure it's in your PATH.")
        except Exception as e:
            print(f"An error occurred: {e}")       
            