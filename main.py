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

# NEW IMPORTS for Gemini (google-genai SDK)
from google import genai
from google.genai import types

load_dotenv()

# Part 1: Code Execution Tool (unchanged - works perfectly)
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

# Part 2: AI Error Analysis (NEW - correct Gemini SDK)
class ErrorAnalysis(BaseModel):
    error_lines: List[int]

def analyze_error_with_ai(code: str, traceback_str: str) -> List[int]:
    try:
        # Correct client creation (reads GEMINI_API_KEY automatically)
        client = genai.Client()
        
        prompt = f"""
        Analyze this Python code and its error traceback.
        Identify ONLY the exact line number(s) where the error occurred.
        
        CODE:
        {code}
        
        TRACEBACK:
        {traceback_str}
        
        Respond with JSON containing ONLY error line numbers.
        """
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-exp",  # Fast & works great
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "error_lines": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.INTEGER)
                        )
                    },
                    required=["error_lines"]
                )
            )
        )
        
        result = ErrorAnalysis.model_validate_json(response.text)
        return result.error_lines
        
    except Exception as e:
        # Fallback: Extract line number from traceback (your regex)
        line_match = re.search(r'line (\d+)', traceback_str)
        if line_match:
            return [int(line_match.group(1))]
        return [1]  # Safety fallback

# FastAPI App Setup
app = FastAPI(title="Code Interpreter with AI Error Analysis")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class CodeInput(BaseModel):
    code: str

class CodeResponse(BaseModel):
    error: List[int]
    result: str

# Main Endpoint (assignment requirement)
@app.post("/code-interpreter", response_model=CodeResponse)
async def code_interpreter(request: CodeInput):
    # Step 1: Execute code
    result = execute_python_code(request.code)
    
    # Step 2: Check success
    if result["success"]:
        return {"error": [], "result": result["output"]}
    
    # Step 3: AI analyzes error (only when needed)
    error_lines = analyze_error_with_ai(request.code, result["output"])
    
    # Step 4: Return structured response
    return {"error": error_lines, "result": result["output"]}

# Test endpoint (check if Gemini works)
@app.get("/test-gemini")
def test_gemini():
    try:
        client = genai.Client()
        return {"status": "✅ Gemini client works!", "api_key_set": bool(os.getenv("GEMINI_API_KEY"))}
    except Exception as e:
        return {"error": str(e)}

# Health check
@app.get("/")
def root():
    return {"message": "Code Interpreter API is running! POST to /code-interpreter"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
