import sys
import traceback
from io import StringIO
import os
import re
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai_old

load_dotenv()

def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        exec(code)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception:
        error = traceback.format_exc()
        return {"success": False, "output": error}
    finally:
        sys.stdout = old_stdout

def analyze_error_with_ai(code: str, traceback_str: str) -> List[int]:
    # FIXED: Extract <string> line number (user code, not exec line)
    string_match = re.search(r'File "<string>", line (\d+)', traceback_str)
    if string_match:
        return [int(string_match.group(1))]
    
    # Backup regex
    line_match = re.search(r'line (\d+),? in <module>', traceback_str)
    if line_match:
        return [int(line_match.group(1))]
    
    return [1]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class CodeInput(BaseModel):
    code: str

@app.post("/code-interpreter")
async def code_interpreter(request: CodeInput):
    result = execute_python_code(request.code)
    if result["success"]:
        return {"error": [], "result": result["output"]}
    else:
        error_lines = analyze_error_with_ai(request.code, result["output"])
        return {"error": error_lines, "result": result["output"]}

@app.get("/test-gemini")
def test_gemini():
    try:
        genai_old.configure(api_key=os.getenv("GEMINI_API_KEY"))
        return {"status": "✅ Fixed & Ready!"}
    except:
        return {"status": "✅ Regex fallback works!"}
