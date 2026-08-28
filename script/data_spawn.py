import os
import re
import time
import uuid
import shutil
import subprocess
from openai import OpenAI
from fastapi import FastAPI, Request, Form, Body,APIRouter
from fastapi.responses import JSONResponse, FileResponse
from config import name_to_model,templates
data_spawn_router=APIRouter()

@data_spawn_router.get("/data_spawn")
def data_spawn_page(request:Request):
    return templates.TemplateResponse(request,"data_spawn.html",{"request":request})

def clean_ai_code(raw: str) -> str:
    raw = re.sub(r'^```(?:cpp)?\s*\n', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\n```\s*$', '', raw, flags=re.MULTILINE)
    return raw
def check(code: str) -> bool:
    """
    检测 C++ 代码中是否包含危险的系统调用或文件操作。
    返回 True 表示存在潜在风险，需要人工审查或拒绝执行。
    """
    # 1. system 调用（包括 std::system、::system、system 等）
    system_pattern = r'(?:std::|::)?\bsystem\s*\('

    # 2. C 风格文件操作（可能用于删除、重命名、读写）
    c_file_ops = [
        r'\bfopen\s*\(',
        r'\bfreopen\s*\(',
        r'\bremove\s*\(',
        r'\brename\s*\(',
        r'\bunlink\s*\(',
        r'\brmdir\s*\(',
        r'\b_mkdir\s*\(',
        r'\b_mkdir\s*\(',
    ]

    # 3. C++ 文件流操作（仅检测 open 成员函数调用，构造函数难以完全静态检测）
    cpp_file_ops = [
        r'\.open\s*\(',            # 如 ifs.open("file")
        r'\bstd::ifstream\s*\(',
        r'\bstd::ofstream\s*\(',
        r'\bstd::fstream\s*\(',
        r'\bstd::filesystem::remove\s*\(',
        r'\bstd::filesystem::remove_all\s*\(',
        r'\bstd::filesystem::rename\s*\(',
        r'\bstd::filesystem::copy\s*\(',
        r'\bstd::filesystem::create_directory\s*\(',
        r'\bstd::filesystem::create_directories\s*\(',
    ]

    # 合并所有危险模式
    all_patterns = [system_pattern] + c_file_ops + cpp_file_ops
    combined = '|'.join(all_patterns)

    # 搜索代码（忽略大小写？C++ 区分大小写，但函数名都是小写，这里不设 re.I）
    if re.search(combined, code):
        return True

    # 额外检测：对 std::ofstream 等通过构造函数直接打开文件（例如 std::ofstream("a.txt")）
    # 构造函数带文件名参数的模式
    constructor_pattern = r'\bstd::(?:ifstream|ofstream|fstream)\s*\(\s*["\']'
    if re.search(constructor_pattern, code):
        return True
    return False
@data_spawn_router.post("/api/data_spawn")
def data_spawn(request: Request, title: str = Form(...), answer: str = Form(""), sum: int = Form(...)):
    if(check(answer)):
        return JSONResponse({"error": "参考答案包含潜在危险的系统调用或文件操作，请检查后重试。"}, status_code=400)
    original_cwd = os.getcwd()
    # title 为题目, answer 为参考答案, sum 为样例数。前端以 application/x-www-form-urlencoded 发送表单。
    using_model = name_to_model["deepseekV4Pro(深度思考)"]
    client = OpenAI(
        api_key=using_model.get("api_key"),
        base_url=using_model.get("model_url"))
    messages = [{"role": "system", "content": """
【系统指令】你是一个严格的 C++ 题目数据生成器。你必须遵守以下规则，违反任何一条都会导致编译失败，进而使整个任务无效：
你的任务是输出一份 C++ 代码，这份代码在运行后会生成测试数据1.in"""+str(sum)+""".in。测试数据的格式如下：
1. 你的整个输出必须**仅包含**可直接编译运行的 C++ 代码。不允许输出任何其他字符，包括但不限于：
   - Markdown 代码块标记（如 ```cpp 或 ```）
   - 行号
   - 解释性文字
   - 注释（代码内部的 // 或 /* */ 除外）
   - 空行（除了代码逻辑需要的空行）

2. 你的输出必须以以下之一开头：
   - #include
   - using namespace std;
   - int main
   绝不能以 ``` 或任何其他字符开头。

3. 你的输出必须以 `}` 结尾（且该 `}` 应匹配 main 函数或代码逻辑的结尾）。

4. 如果输出中出现了 ```` 或任何非代码字符，系统将直接丢弃你的输出并报错，导致用户无法得到任何结果。

5. 请直接输出代码本身，就好像你正在把代码粘贴到一个 .cpp 文件中一样。

现在，请根据用户提供的题目要求，输出纯 C++ 代码（使用 mt19937，C++17，只使用标准库）。
    """}]
    messages.append({"role": "user", "content": title})
    print("正在生成代码.ing...")
    response = client.chat.completions.create(
        model=using_model.get("model_name"),
        messages=messages,
        stream=False,
        reasoning_effort=using_model.get("reasoning_effort"),
        extra_body=using_model.get("model_extra_body"),
    )
    temp_uuid=uuid.uuid4()
    path=os.path.abspath("code/"+str(temp_uuid))
    os.mkdir(path)
    rand_path=os.path.abspath(path+"/"+"random.cpp")
    answer_path=os.path.abspath(path+"/"+"answer.cpp")
    rand_exe_path=os.path.abspath(path+"/"+"random.exe")
    answer_exe_path=os.path.abspath(path+"/"+"answer.exe")
    compile_path=os.path.abspath("mingw64/bin/g++.exe")
    with open(rand_path,"w") as f:
        f.write(clean_ai_code(response.choices[0].message.content))
    with open(answer_path,"w") as f:
        f.write(answer)
    print("尝试编译.ing...")
    try:
        subprocess.run([compile_path,rand_path,"-static","-o",rand_exe_path],check=True)
        subprocess.run([compile_path,answer_path,"-static","-o",answer_exe_path],check=True)
    except Exception as e:
        return JSONResponse({"error": "编译错误"}, status_code=400)
    print("编译完成，正在生成测试数据.ing...")
    rand_exe_path=os.path.abspath(path+"/"+"random.exe")
    answer_exe_path=os.path.abspath(path+"/"+"answer.exe")
    os.chdir(path)
    subprocess.run([rand_exe_path],timeout=5)
    for i in range(1,sum+1):
        print(f"正在生成第{i}组测试数据.ing...")
        with open(f"{i}.in","r") as f_in:
            with open(f"{i}.out","w") as f_out:
                subprocess.run([answer_exe_path],stdin=f_in,stdout=f_out,timeout=5)
    shutil.make_archive(path, 'zip', path)
    print("测试数据生成完成，正在清理临时文件.ing...")
    
    os.chdir(original_cwd)
    while(1):
        try:
            shutil.rmtree(path)
            break
        except Exception as e:
            time.sleep(0.1)
    print("已完成")
    return FileResponse(
        path=os.path.abspath(path+".zip"),
        filename=str(temp_uuid)+".zip",
        media_type="application/zip"
    )