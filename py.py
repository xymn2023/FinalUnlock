#!/usr/bin/env python3
"""
FinalShell 激活码生成核心模块

支持版本:
- FinalShell < 3.9.6
- FinalShell >= 3.9.6
- FinalShell 4.5
- FinalShell 4.6
"""

from Crypto.Hash import MD5, keccak
import argparse
import sys
import json
import html
from typing import Dict, List, Optional
from pathlib import Path


# ==================== 版本配置 ====================
# 将版本信息结构化，便于维护和扩展
VERSIONS = [
    {
        "name": "FinalShell < 3.9.6",
        "hash_type": "md5",
        "codes": [
            {"name": "高级版", "emoji": "🟡", "prefix": "61305", "suffix": "8552", "start": 8, "end": 24},
            {"name": "专业版", "emoji": "🟢", "prefix": "2356", "suffix": "13593", "start": 8, "end": 24},
        ]
    },
    {
        "name": "FinalShell ≥ 3.9.6",
        "hash_type": "keccak384",
        "codes": [
            {"name": "高级版", "emoji": "🟡", "prefix": "", "suffix": "hSf(78cvVlS5E", "start": 12, "end": 28},
            {"name": "专业版", "emoji": "🟢", "prefix": "", "suffix": "FF3Go(*Xvbb5s2", "start": 12, "end": 28},
        ]
    },
    {
        "name": "FinalShell 4.5",
        "hash_type": "keccak384",
        "codes": [
            {"name": "高级版", "emoji": "🟡", "prefix": "", "suffix": "wcegS3gzA$", "start": 12, "end": 28},
            {"name": "专业版", "emoji": "🟢", "prefix": "", "suffix": "b(xxkHn%z);x", "start": 12, "end": 28},
        ]
    },
    {
        "name": "FinalShell 4.6",
        "hash_type": "keccak384",
        "codes": [
            {"name": "高级版", "emoji": "🟡", "prefix": "", "suffix": "csSf5*xlkgYSX,y", "start": 12, "end": 28},
            {"name": "专业版", "emoji": "🟢", "prefix": "", "suffix": "Scfg*ZkvJZc,s,Y", "start": 12, "end": 28},
        ]
    },
]


# ==================== 核心算法函数 ====================

def calc_md5(data: str) -> str:
    """
    计算字符串的 MD5 哈希值
    
    Args:
        data: 输入字符串
        
    Returns:
        MD5 哈希值的十六进制字符串
    """
    return MD5.new(data.encode()).hexdigest()


def calc_keccak384(data: str) -> str:
    """
    计算字符串的 Keccak-384 哈希值
    
    Args:
        data: 输入字符串
        
    Returns:
        Keccak-384 哈希值的十六进制字符串
    """
    return keccak.new(data=data.encode(), digest_bits=384).hexdigest()


def generate_activation_code(machine_id: str, version_config: Dict) -> List[Dict[str, str]]:
    """
    为指定版本生成激活码
    
    Args:
        machine_id: 机器码
        version_config: 版本配置字典
        
    Returns:
        激活码列表，每个元素包含名称和代码
    """
    hash_type = version_config["hash_type"]
    codes = []
    
    for code_config in version_config["codes"]:
        # 构建输入字符串
        input_str = f"{code_config['prefix']}{machine_id}{code_config['suffix']}"
        
        # 计算哈希
        if hash_type == "md5":
            hash_result = calc_md5(input_str)
        else:  # keccak384
            hash_result = calc_keccak384(input_str)
        
        # 提取指定范围的字符作为激活码
        activation_code = hash_result[code_config["start"]:code_config["end"]]
        
        codes.append({
            "name": code_config["name"],
            "emoji": code_config["emoji"],
            "code": activation_code
        })
    
    return codes


def show_activation_codes(machine_id: str) -> None:
    """
    显示所有版本的激活码（保持与原函数兼容）
    
    Args:
        machine_id: 机器码
    """
    for version_config in VERSIONS:
        print(f"{version_config['name']}")
        codes = generate_activation_code(machine_id, version_config)
        for code_info in codes:
            print(f"{code_info['emoji']} {code_info['name']}: {code_info['code']}")


def get_activation_codes_text(machine_id: str, output_format: str = "text") -> str:
    """
    生成所有版本的激活码文本（推荐用于 bot.py）
    
    Args:
        machine_id: 机器码
        output_format: 输出格式 ("text", "telegram", "html")
        
    Returns:
        格式化的激活码文本
    """
    result = generate_all_codes(machine_id)
    
    if output_format == "html":
        return _format_html(result)
    elif output_format == "telegram":
        return format_output(result, "telegram")
    else:
        return format_output(result, "text")


def _format_html(result: Dict) -> str:
    """
    生成 HTML 格式的输出（用于 Telegram HTML parse_mode）
    激活码用 <code> 标签包裹，支持点击复制
    """
    lines = []
    lines.append("🎉 <b>激活码生成成功</b>：\n")
    
    for version in result["versions"]:
        # 转义版本字符串中的 HTML 特殊字符（如 < > &）
        version_name = html.escape(version['version'])
        lines.append(f"📌 <b>{version_name}</b>")
        for code in version["codes"]:            
            # 使用 <code> 标签，Telegram 中可点击复制
            # 激活码是十六进制字符串，无需转义
            lines.append(f"{code['emoji']} {code['name']}: <code>{code['code']}</code>")
        lines.append("")  # 空行分隔
        
    return "\n".join(lines).strip()


# ==================== 高级功能函数 ====================

def validate_machine_id(machine_id: str) -> bool:
    """
    验证机器码格式
    
    Args:
        machine_id: 机器码
        
    Returns:
        是否有效
    """
    if not machine_id:
        return False
    # 机器码通常是十六进制字符串，至少5个字符
    if len(machine_id) < 5:
        return False
    # 可以添加更多验证逻辑
    return True


def generate_all_codes(machine_id: str, version_name: Optional[str] = None) -> Dict:
    """
    生成激活码并返回结构化数据
    
    Args:
        machine_id: 机器码
        version_name: 指定版本名称，None 表示所有版本
        
    Returns:
        包含所有激活码信息的字典
    """
    result = {
        "machine_id": machine_id,
        "versions": []
    }
    
    for version_config in VERSIONS:
        # 如果指定了版本，只生成该版本的激活码
        if version_name and version_config["name"] != version_name:
            continue
            
        codes = generate_activation_code(machine_id, version_config)
        version_result = {
            "version": version_config["name"],
            "codes": codes
        }
        result["versions"].append(version_result)
    
    return result


def format_output(result: Dict, output_format: str = "text") -> str:
    """
    格式化输出结果
    
    Args:
        result: generate_all_codes 的返回结果
        output_format: 输出格式 ("text", "json", "simple", "telegram")
        
    Returns:
        格式化后的字符串
    """
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    elif output_format == "simple":
        lines = []
        for version in result["versions"]:
            for code in version["codes"]:
                lines.append(code["code"])
        return "\n".join(lines)
    
    elif output_format == "telegram":
        # Telegram 专用格式：使用 pre 代码块，支持点击复制
        lines = []
        for version in result["versions"]:
            lines.append(f"📌 {version['version']}")
            for code in version["codes"]:
                # 使用 pre 格式，Telegram 中可点击复制
                lines.append(f"{code['emoji']} {code['name']}:\n`{code['code']}`")
            lines.append("")  # 空行分隔
        return "\n".join(lines).strip()
    
    else:  # text format (兼容原格式)
        lines = []
        for version in result["versions"]:
            lines.append(f"{version['version']}")
            for code in version["codes"]:
                lines.append(f"{code['emoji']} {code['name']}: {code['code']}")
        return "\n".join(lines)


def batch_generate(input_file: str, output_file: Optional[str] = None, 
                   output_format: str = "text") -> None:
    """
    批量生成激活码
    
    Args:
        input_file: 输入文件路径，每行一个机器码
        output_file: 输出文件路径，None 表示输出到标准输出
        output_format: 输出格式
    """
    results = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        machine_ids = [line.strip() for line in f if line.strip()]
    
    for machine_id in machine_ids:
        if not validate_machine_id(machine_id):
            print(f"警告: 跳过无效机器码: {machine_id}", file=sys.stderr)
            continue
        
        result = generate_all_codes(machine_id)
        results.append(result)
    
    # 格式化输出
    if output_format == "json":
        output = json.dumps(results, ensure_ascii=False, indent=2)
    else:
        output = "\n\n".join(format_output(r, output_format) for r in results)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 已生成 {len(results)} 个激活码，保存到: {output_file}")
    else:
        print(output)


# ==================== 命令行入口 ====================

def main():
    """命令行主函数"""
    parser = argparse.ArgumentParser(
        description="FinalShell 激活码生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互式输入机器码
  python py.py
  
  # 直接指定机器码
  python py.py -m YOUR_MACHINE_ID
  
  # 生成 JSON 格式输出
  python py.py -m YOUR_MACHINE_ID -f json
  
  # 只生成指定版本的激活码
  python py.py -m YOUR_MACHINE_ID -v "FinalShell 4.5"
  
  # 批量生成（从文件读取机器码）
  python py.py -i machines.txt -o codes.txt
  
  # 批量生成 JSON 格式
  python py.py -i machines.txt -o codes.json -f json
        """
    )
    
    parser.add_argument("-m", "--machine-id", type=str, help="机器码")
    parser.add_argument("-f", "--format", type=str, choices=["text", "json", "simple"],
                        default="text", help="输出格式 (默认: text)")
    parser.add_argument("-v", "--version", type=str, help="指定版本 (例如: 'FinalShell 4.5')")
    parser.add_argument("-i", "--input", type=str, help="批量处理: 输入文件")
    parser.add_argument("-o", "--output", type=str, help="批量处理: 输出文件")
    
    args = parser.parse_args()
    
    # 批量处理模式
    if args.input:
        if not Path(args.input).exists():
            print(f"❌ 错误: 输入文件不存在: {args.input}", file=sys.stderr)
            sys.exit(1)
        batch_generate(args.input, args.output, args.format)
        return
    
    # 单个机器码模式
    if args.machine_id:
        machine_id = args.machine_id.strip()
    else:
        # 交互式输入
        try:
            machine_id = input('请输入机器码: ').strip()
        except EOFError:
            print("❌ 错误: 需要输入机器码", file=sys.stderr)
            sys.exit(1)
    
    # 验证机器码
    if not validate_machine_id(machine_id):
        print(f"❌ 错误: 无效的机器码: {machine_id}", file=sys.stderr)
        print("机器码不能为空且长度至少为 5 个字符", file=sys.stderr)
        sys.exit(1)
    
    # 生成激活码
    try:
        if args.format == "json" or args.version:
            # 使用结构化输出
            result = generate_all_codes(machine_id, args.version)
            print(format_output(result, args.format))
        else:
            # 使用原始格式（保持兼容）
            show_activation_codes(machine_id)
    except Exception as e:
        print(f"❌ 错误: 生成激活码失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
