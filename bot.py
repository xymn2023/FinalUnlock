#!/usr/bin/env python3
"""
FinalUnlock Telegram Bot 
功能：FinalShell激活码自动生成机器人
优化版：改进响应速度，使用异步并发
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Set

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, RetryAfter
from dotenv import load_dotenv

# 导入核心算法
from py import get_activation_codes_text, validate_machine_id

# 基础配置
BASE_DIR = Path(__file__).parent
PID_FILE = BASE_DIR / 'bot.pid'
LOG_FILE = BASE_DIR / 'bot.log'
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

# 加载环境变量
load_dotenv(BASE_DIR / '.env')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

if not BOT_TOKEN or not CHAT_ID:
    print("错误：请先配置 .env 文件中的 BOT_TOKEN 和 CHAT_ID")
    sys.exit(1)

# 日志配置 - 优化：只在重要事件时写入文件
logging.basicConfig(
    level=logging.WARNING,  # 改为 WARNING，减少日志量
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)
# 单独设置控制台日志级别为 INFO
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# ==================== 优化的数据管理器 ====================

class DataManager:
    """
    优化的数据管理器
    - 减少文件 I/O 次数
    - 使用缓存避免重复读取
    """
    def __init__(self):
        self.stats_file = DATA_DIR / 'stats.json'
        self.users_file = DATA_DIR / 'users.json'
        self.banned_file = DATA_DIR / 'banned.json'
        
        # 缓存
        self._stats_cache = None
        self._users_cache = None
        self._banned_cache = None
        self._cache_time = {}
        
    def _is_cache_valid(self, key: str, max_age: int = 5) -> bool:
        """检查缓存是否有效（默认5秒）"""
        if key not in self._cache_time:
            return False
        age = (datetime.now() - self._cache_time[key]).total_seconds()
        return age < max_age
    
    def load_json(self, file_path, default=None):
        if default is None:
            default = {}
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
        return default
    
    def save_json(self, file_path, data):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def get_stats(self):
        if self._is_cache_valid('stats'):
            return self._stats_cache
        data = self.load_json(self.stats_file, {})
        self._stats_cache = data
        self._cache_time['stats'] = datetime.now()
        return data
    
    def save_stats(self, stats):
        self._stats_cache = stats
        self._cache_time['stats'] = datetime.now()
        self.save_json(self.stats_file, stats)
    
    def get_users(self):
        if self._is_cache_valid('users'):
            return self._users_cache
        data = self.load_json(self.users_file, {})
        self._users_cache = data
        self._cache_time['users'] = datetime.now()
        return data
    
    def save_users(self, users):
        self._users_cache = users
        self._cache_time['users'] = datetime.now()
        self.save_json(self.users_file, users)
    
    def get_banned(self) -> Set[str]:
        if self._is_cache_valid('banned'):
            return self._banned_cache
        data = set(self.load_json(self.banned_file, []))
        self._banned_cache = data
        self._cache_time['banned'] = datetime.now()
        return data
    
    def save_banned(self, banned_set: Set[str]):
        self._banned_cache = banned_set
        self._cache_time['banned'] = datetime.now()
        self.save_json(self.banned_file, list(banned_set))

# 全局数据管理器
dm = DataManager()

# 管理员检查
def is_admin(user_id):
    return str(user_id) == CHAT_ID

# ==================== 命令处理器 ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令 - 优化：使用更简洁的回复"""
    await update.message.reply_text(
        "🎉 欢迎使用 FinalShell 激活码生成机器人！\n\n"
        "📝 直接发送机器码即可获取激活码\n"
        "💡 支持 FinalShell 全版本\n\n"
        "🚀 请合理使用 滥用拉黑永久不解！"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_text = "🤖 FinalShell 激活码机器人使用帮助\n\n"
    help_text += "👤 用户命令：\n"
    help_text += "/start - 开始使用\n"
    help_text += "/help - 显示帮助\n"
    help_text += "直接发送机器码 - 生成激活码\n\n"
    
    if is_admin(update.effective_user.id):
        help_text += "👑 管理员命令：\n"
        help_text += "/stats - 查看统计\n"
        help_text += "/users - 用户列表\n"
        help_text += "/ban <用户ID> - 拉黑用户\n"
        help_text += "/unban <用户ID> - 解除拉黑\n"
        help_text += "/say <消息> - 广播消息\n"
    
    await update.message.reply_text(help_text)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """统计命令 - 优化：减少计算和 I/O"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    
    users = dm.get_users()
    banned = dm.get_banned()
    
    # 优化：只计算一次
    total_requests = sum(user.get('total_requests', 0) for user in users.values())
    
    text = f"📊 机器人统计信息\n\n"
    text += f"👥 总用户数：{len(users)}\n"
    text += f"🚫 被拉黑用户：{len(banned)}\n"
    text += f"📈 总请求数：{total_requests}\n"
    text += f"📅 统计时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await update.message.reply_text(text)

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户列表命令"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    
    users = dm.get_users()
    if not users:
        await update.message.reply_text("📭 暂无用户数据")
        return
    
    text = "👥 用户列表（最近10个）：\n\n"
    for i, (uid, info) in enumerate(list(users.items())[-10:], 1):
        name = info.get('first_name', '未知')
        count = info.get('total_requests', 0)
        banned = '🚫' if info.get('is_banned', False) else '✅'
        text += f"{i}. {name} ({uid})\n   请求：{count}次 状态：{banned}\n\n"
    
    await update.message.reply_text(text)

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """拉黑命令"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    
    if not context.args:
        await update.message.reply_text("用法：/ban <用户ID>")
        return
    
    user_id = context.args[0]
    banned = dm.get_banned()
    banned.add(user_id)
    dm.save_banned(banned)
    
    await update.message.reply_text(f"✅ 已拉黑用户 {user_id}")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """解除拉黑命令"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    
    if not context.args:
        await update.message.reply_text("用法：/unban <用户ID>")
        return
    
    user_id = context.args[0]
    banned = dm.get_banned()
    banned.discard(user_id)
    dm.save_banned(banned)
    
    await update.message.reply_text(f"✅ 已解除拉黑用户 {user_id}")

async def say_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    广播命令 - 优化：使用 asyncio.gather 并发发送
    大幅提升广播速度
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    
    if not context.args:
        await update.message.reply_text("用法：/say <要广播的消息>")
        return
    
    message = ' '.join(context.args)
    users = dm.get_users()
    
    if not users:
        await update.message.reply_text("📭 暂无用户可广播")
        return
    
    # 发送进度提示
    progress_msg = await update.message.reply_text(f"📢 正在广播消息到 {len(users)} 个用户...")
    
    sent = 0
    failed = 0
    
    # 优化：分批并发发送，避免触发限流
    batch_size = 25  # Telegram 建议的并发数
    user_ids = list(users.keys())
    
    for i in range(0, len(user_ids), batch_size):
        batch = user_ids[i:i+batch_size]
        
        # 创建并发任务
        tasks = []
        for uid in batch:
            task = self._send_message_safe(context.bot, uid, message)
            tasks.append(task)
        
        # 并发执行当前批次
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                # 如果是限流错误，等待后重试
                if isinstance(result, RetryAfter):
                    await asyncio.sleep(result.retry_after)
            else:
                sent += 1
        
        # 批次间短暂延迟，避免触发限流
        if i + batch_size < len(user_ids):
            await asyncio.sleep(1)
    
    # 更新进度消息
    await progress_msg.edit_text(f"📢 广播完成\n✅ 成功：{sent}\n❌ 失败：{failed}")

async def _send_message_safe(bot, chat_id: str, text: str) -> bool:
    """
    安全发送消息的辅助函数
    返回 True/False 而不是抛出异常
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except RetryAfter as e:
        # 限流错误，等待后重试一次
        await asyncio.sleep(e.retry_after)
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            return True
        except:
            return False
    except Exception:
        return False

# ==================== 主要消息处理 ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理消息 - 优化版
    - 使用直接函数调用，避免 stdout 捕获
    - 减少不必要的 I/O 操作
    """
    user_id = str(update.effective_user.id)
    user_info = update.effective_user
    machine_id = update.message.text.strip()
    
    # 检查拉黑（使用缓存）
    banned = dm.get_banned()
    if user_id in banned:
        await update.message.reply_text("❌ 你已被拉黑，无法使用此服务")
        return
    
    # 优化：异步更新用户信息，不阻塞主流程
    asyncio.create_task(update_user_info(user_id, user_info))
    
    # 验证机器码
    if not machine_id or len(machine_id) < 5:
        await update.message.reply_text("❌ 请输入有效的机器码")
        return
    
    # 生成激活码 - 优化：直接调用函数，无需捕获 stdout
    try:
        # 使用 HTML 格式，激活码用 <code> 标签包裹，可点击复制
        result_html = get_activation_codes_text(machine_id, output_format="html")
        
        if result_html:
            # 使用 HTML parse_mode，支持 <code> 标签点击复制
            await update.message.reply_text(result_html, parse_mode='HTML')
            logger.info(f"用户 {user_id} 生成激活码成功")
        else:
            await update.message.reply_text("❌ 生成激活码失败，请检查机器码格式")
            
    except Exception as e:
        # 记录详细错误信息，便于排查
        logger.error(f"生成激活码出错: {e}", exc_info=True)
        await update.message.reply_text("❌ 服务暂时不可用，请稍后重试")

async def update_user_info(user_id: str, user_info):
    """
    异步更新用户信息 - 不阻塞主流程
    """
    try:
        users = dm.get_users()
        users[user_id] = {
            'first_name': user_info.first_name or '',
            'last_name': user_info.last_name or '',
            'username': user_info.username or '',
            'first_seen': users.get(user_id, {}).get('first_seen', datetime.now().isoformat()),
            'last_seen': datetime.now().isoformat(),
            'total_requests': users.get(user_id, {}).get('total_requests', 0) + 1,
            'is_banned': False
        }
        dm.save_users(users)
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}")

# ==================== 错误处理 ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """全局错误处理器"""
    logger.error(f"更新处理出错: {context.error}")

# ==================== PID 管理 ====================

def create_pid():
    """创建 PID 文件"""
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID文件已创建: {PID_FILE}")
    except Exception as e:
        logger.error(f"创建PID文件失败: {e}")

def remove_pid():
    """删除 PID 文件"""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info("PID文件已删除")
    except Exception as e:
        logger.error(f"删除PID文件失败: {e}")

# ==================== 主函数 ====================

def main():
    """主函数"""
    logger.info("FinalUnlock Bot 启动中...")
    
    # 创建PID文件
    create_pid()
    
    try:
        # 创建应用 - 优化：设置连接池大小
        app = Application.builder().token(BOT_TOKEN).build()
        
        # 添加处理器
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('help', help_cmd))
        app.add_handler(CommandHandler('stats', stats_cmd))
        app.add_handler(CommandHandler('users', users_cmd))
        app.add_handler(CommandHandler('ban', ban_cmd))
        app.add_handler(CommandHandler('unban', unban_cmd))
        app.add_handler(CommandHandler('say', say_cmd))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)
        
        logger.info("Bot 启动成功，开始轮询...")
        
        # 运行 - 优化：使用更高效的轮询设置
        app.run_polling(
            drop_pending_updates=True,
            # 优化：减少超时时间，提高响应速度
            read_timeout=10,
            write_timeout=10,
            connect_timeout=10,
            pool_timeout=10,
        )
        
    except KeyboardInterrupt:
        logger.info("收到停止信号")
    except Exception as e:
        logger.error(f"Bot运行出错: {e}")
    finally:
        remove_pid()

if __name__ == '__main__':
    main()
