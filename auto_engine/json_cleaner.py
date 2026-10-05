"""
json_cleaner.py - TVBox 专用非标准 JSON 清洗与安全解析工具
能够处理 // 注释、/* */ 块注释、尾随逗号、BOM 以及常见转义问题
"""
import re
import json
import base64

def strip_comments(text: str) -> str:
    """去除 C/JS 风格的行注释和块注释，同时保护字符串内的 // 和 /* """
    result = []
    i = 0
    n = len(text)
    in_string = False
    string_char = ''
    
    while i < n:
        char = text[i]
        
        # 处理字符串内的转义
        if in_string:
            result.append(char)
            if char == '\\' and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            elif char == string_char:
                in_string = False
            i += 1
            continue
            
        # 字符串起始
        if char in ('"', "'"):
            in_string = True
            string_char = char
            result.append(char)
            i += 1
            continue
            
        # 行注释 //
        if char == '/' and i + 1 < n and text[i + 1] == '/':
            # 跳到行尾
            i += 2
            while i < n and text[i] not in ('\r', '\n'):
                i += 1
            continue
            
        # 块注释 /* */
        if char == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2 # 跳过 */
            continue
            
        # 井号注释 # (TVBox 也常有人写 # 开头的注释)
        if char == '#' and (i == 0 or text[i - 1] in ('\r', '\n', ' ', '\t')):
            i += 1
            while i < n and text[i] not in ('\r', '\n'):
                i += 1
            continue
            
        result.append(char)
        i += 1
        
    return "".join(result)

def remove_trailing_commas(text: str) -> str:
    """去除对象和数组末尾的多余逗号，如 [1, 2,] 或 {"a": 1,}"""
    # 匹配逗号后面紧跟着空白和 closing bracket
    text = re.sub(r',\s*([\]\}])', r'\1', text)
    return text

def try_decode_base64(text: str) -> str:
    """如果文本是整段 Base64 编码，尝试解密还原"""
    stripped = text.strip()
    # 排除原本就是标准 json 的情况
    if stripped.startswith("{") or stripped.startswith("["):
        return text
    
    # 尝试 base64 解码
    try:
        raw_bytes = base64.b64decode(stripped, validate=True)
        decoded = raw_bytes.decode('utf-8', errors='ignore')
        if decoded.strip().startswith("{") or decoded.strip().startswith("["):
            return decoded
    except Exception:
        pass
    return text

def parse_tvbox_json(raw_text: str):
    """
    通用容错解析：
    1. 去除 BOM
    2. 尝试 Base64 解码
    3. 清洗注释与尾部逗号
    4. 尝试 json.loads 解析，若失败则做进一步字符修复
    """
    if not raw_text:
        return None
        
    # 移除 BOM
    cleaned = raw_text.lstrip('\ufeff').strip()
    
    # 尝试解密
    cleaned = try_decode_base64(cleaned)
    
    # 第一次尝试原生解析
    try:
        return json.loads(cleaned)
    except Exception:
        pass
        
    # 清除注释
    cleaned = strip_comments(cleaned)
    # 清除多余逗号
    cleaned = remove_trailing_commas(cleaned)
    
    try:
        return json.loads(cleaned)
    except Exception:
        pass
        
    # 如果还是失败，尝试自动修复键名缺失前置引号的问题（如 ,key": 或 {key":）
    try:
        repaired = re.sub(r'([,{]\s*)([a-zA-Z0-9_]+)":', r'\1"\2":', cleaned)
        repaired = remove_trailing_commas(repaired)
        return json.loads(repaired)
    except Exception:
        pass

    # 如果还是失败，尝试修复单引号为双引号
    try:
        repaired = re.sub(r"([{,]\s*)'([^']+)'\s*:", r'\1"\2":', cleaned)
        repaired = remove_trailing_commas(repaired)
        return json.loads(repaired)
    except Exception:
        return None
